##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.AMQP')

import json
from functools import partial

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks

import zope.component
from zope.component import adapts, getUtility
from zope.interface import implements

from Products.Five import zcml
from Products.ZenEvents import ZenEventClasses
import Products.ZenMessaging.queuemessaging

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import (
    PythonDataSource, PythonDataSourcePlugin, PythonDataSourceInfo,
    IPythonDataSourceInfo)

from ZenPacks.zenoss.OpenStackInfrastructure.utils import result_errmsg, sleep
from zenoss.protocols.amqpconfig import AMQPConfig
from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema
from zenoss.protocols.twisted.amqp import AMQPFactory

# How long to cache data in memory before discarding it (data that
# is coming from ceilometer, but not consumed by any monitoring templates).
# Should be at least the cycle interval.
CACHE_EXPIRE_TIME = 25*60

# Process-wide cache of AMQP clients-
# these can be shared by multiple tasks for a given device.
amqp_client = {}                     # amqp_client[device.id] = AMQClient object

class AMQPDataSource(PythonDataSource):
    '''
    Datasource used to capture data and events shipped to us from OpenStack
    Ceilometer via AMQP.
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack Ceilometer AMQP',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 300

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'AMQPDataSource.AMQPDataSourcePlugin'


class IAMQPDataSourceInfo(IPythonDataSourceInfo):
    '''
    API Info interface for IAMQPDataSource.
    '''


class AMQPDataSourceInfo(PythonDataSourceInfo):
    '''
    API Info adapter factory for AMQPDataSource.
    '''

    implements(IAMQPDataSourceInfo)
    adapts(AMQPDataSource)

    testable = False


class AMQPDataSourcePlugin(PythonDataSourcePlugin):
    exchange_name = '$OpenStackInbound'
    queue_name = None  # override in subclass
    failure_eventClassKey = 'AMQPFailure'

    @classmethod
    def config_key(cls, datasource, context):
        """
        Return list that is used to split configurations at the collector.

        This is a classmethod that is executed in zenhub. The datasource and
        context parameters are the full objects.
        """
        return (
            context.device().id,
            datasource.getCycleTime(context),
            datasource.plugin_classname
        )

    @inlineCallbacks
    def collect(self, config):
        log.debug("Collect for OpenStack AMQP (%s)" % config.id)

        # During the first collect run, we spin up the AMQP listener.  After
        # that, no active collecting is done in the collect() method.
        #
        # Instead, as each message arives over the AMQP listener, it goes through
        # processMessage(), and is placed into a cache where it can be processed
        # by the onSuccess method.
        if config.id not in amqp_client:
            # Spin up the AMQP queue listener

            zcml.load_config('configure.zcml', zope.component)
            zcml.load_config('configure.zcml', Products.ZenMessaging.queuemessaging)

            self._amqpConnectionInfo = getUtility(IAMQPConnectionInfo)
            self._amqpConnectionInfo_collector = AMQPConfig(
                amqphost='localhost',
                amqpport=55672,
                amqpvhost=self._amqpConnectionInfo.vhost,
                amqpuser=self._amqpConnectionInfo.user,
                amqppassword=self._amqpConnectionInfo.password,
                amqpusessl=self._amqpConnectionInfo.usessl,
                amqpconnectionheartbeat=self._amqpConnectionInfo.amqpconnectionheartbeat)

            self._queueSchema = getUtility(IQueueSchema)

            amqp = AMQPFactory(self._amqpConnectionInfo, self._queueSchema)
            amqp_collector = AMQPFactory(self._amqpConnectionInfo_collector, self._queueSchema)
            queue = self._queueSchema.getQueue(self.queue_name, replacements={'device': config.id})
            log.debug("Listening on queue: %s with binding to routing key %s" % (queue.name, queue.bindings[self.exchange_name].routing_key))
            yield amqp.listen(queue, callback=partial(self._processMessage, amqp, config.id))
            yield amqp_collector.listen(queue, callback=partial(self._processMessage, amqp_collector, config.id))
            amqp_client[config.id] = amqp
            amqp_client[config.id + "_collector"] = amqp_collector

            # Give time for some of the existing messages to be processed during
            # this initial collection cycle
            yield sleep(10)

        data = self.new_data()
        defer.returnValue(data)

    def _processMessage(self, amqp, device_id, message):
        try:
            value = json.loads(message.content.body)
            log.debug("Procesing AMQP message: %r", value)
            self.processMessage(device_id, value)
            amqp.acknowledge(message)

        except Exception, e:
            log.error("Exception while processing ceilometer message: %r", e)

    def onError(self, result, config):
        errmsg = 'OpenStack AMQP: %s' % result_errmsg(result)
        log.error('%s: %s', config.id, errmsg)

        data = self.new_data()
        data['events'].append({
            'device': config.id,
            'summary': errmsg,
            'severity': ZenEventClasses.Error,
            'eventKey': 'openstackCeilometerAMQPCollection',
            'eventClassKey': self.failure_eventClassKey
            })

        return data

    def cleanup(self, config):
        log.debug("cleanup for OpenStack AMQP (%s)" % config.id)

        if config.id in amqp_client and amqp_client[config.id]:
            result = yield self.collect(config)
            self.onSuccess(result, config)
            amqp = amqp_client[config.id]
            amqp.disconnect()
            amqp.shutdown()
            del self.amqp_client[config.id]
            amqp_collector = amqp_client.get(config.id + "_collector")
            if amqp_collector:
                amqp_collector.disconnect()
                amqp_collector.shutdown()
                del amqp_client[config.id + "_collector"]
