##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.HeartbeatsAMQP')

import json
from time import time, strftime, localtime
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
from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema
from zenoss.protocols.twisted.amqp import AMQPFactory
from ZenPacks.zenoss.OpenStackInfrastructure.Endpoint import Endpoint


class HeartbeatsAMQPDataSource(PythonDataSource):
    '''
    Datasource used to capture heartbeats shipped to us from OpenStack
    Ceilometer via AMQP.
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack Ceilometer Heartbeats AMQP',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 30

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'HeartbeatsAMQPDataSource.HeartbeatsAMQPDataSourcePlugin'

    # HeartbeatsAMQPDataSource

    _properties = PythonDataSource._properties + ()


class IHeartbeatsAMQPDataSourceInfo(IPythonDataSourceInfo):
    '''
    API Info interface for IHeartbeatsAMQPDataSource.
    '''

    pass


class HeartbeatsAMQPDataSourceInfo(PythonDataSourceInfo):
    '''
    API Info adapter factory for HeartbeatsAMQPDataSource.
    '''

    implements(IHeartbeatsAMQPDataSourceInfo)
    adapts(HeartbeatsAMQPDataSource)

    testable = False


# Persistent state
amqp_client = {}                    # amqp_client[device.id] = AMQClient object
heartbeats = {}
MAX_MSG_RECORDS = 11                # for 10 diffs
MAX_TIME_LAPSE = 3600


class HeartbeatsAMQPDataSourcePlugin(PythonDataSourcePlugin):
    proxy_attributes = ('expected_ceilometer_heartbeats',)

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

    @classmethod
    def params(cls, datasource, context):
        return {}

    @inlineCallbacks
    def collect(self, config):
        log.debug("Collect for OpenStack AMQP Heartbeats (%s)" % config.id)

        ds = config.datasources[0]
        hostnames = ds.expected_ceilometer_heartbeats[0]['hostnames']
        processes = ds.expected_ceilometer_heartbeats[0]['processes']

        # During the first collect run, we spin up the AMQP listener.  After
        # that, no active collecting is done in the collect() method.
        #
        # Instead, as each message arrives over the AMQP listener, it goes through
        # processMessage(), and is placed into a list, per host, per process,
        # where it can be processed by the onSuccess method.
        if config.id not in amqp_client:
            # Spin up the AMQP queue listener

            zcml.load_config('configure.zcml', zope.component)
            zcml.load_config('configure.zcml', Products.ZenMessaging.queuemessaging)

            self._amqpConnectionInfo = getUtility(IAMQPConnectionInfo)
            self._queueSchema = getUtility(IQueueSchema)

            amqp = AMQPFactory(self._amqpConnectionInfo, self._queueSchema)
            queue = self._queueSchema.getQueue('$OpenStackInboundHeartbeat',
                                               replacements={'device': config.id})
            log.info("Listening on queue: %s with binding to routing key %s" % (queue.name, queue.bindings['$OpenStackInboundHeartbeats'].routing_key))
            yield amqp.listen(queue, callback=partial(self.processMessage, amqp))
            amqp_client[config.id] = amqp

            # Give time for some of the existing messages to be processed during
            # this initial collection cycle
            yield sleep(10)

        data = self.new_data()
        device_id = config.id

        for host in heartbeats.keys():
            if host not in hostnames:
                continue

            for proc in heartbeats[host].keys():
                if proc not in processes:
                    continue

                # time diffs in lastheard
                diffs = [(heartbeats[host][proc][i]['lastheard'] - \
                           heartbeats[host][proc][i - 1]['lastheard']) \
                          for i in xrange(1, len(heartbeats[host][proc]))]
                # any diffs > MAX_TIME_LAPSE?
                if len([diff for diff in diffs if diff > MAX_TIME_LAPSE]) > 0:

                    evt = {
                        'device': device_id,
                        'severity': ZenEventClasses.Warning,
                        'eventKey': '',
                        'summary': 'Timelapse between heartbeats from '+ \
                                   proc + ' on ' + host + \
                                   ' is more than ' + \
                                   str(MAX_TIME_LAPSE) + ' seconds',
                        'eventClassKey': 'openstackHeartbeat_' + \
                                         host + '_' + proc,
                    }

                    from pprint import pformat
                    log.debug(pformat(evt))

                    data['events'].append(evt)

                    log.warn('Timelapse between heartbeats from ' + \
                             proc + ' on ' + host + \
                             ' is more than ' + \
                                str(MAX_TIME_LAPSE) + ' seconds')

        if len(data['events']):
            data['events'].append({
                'device': device_id,
                'summary': 'OpenStack Ceilometer AMQP Heartbeat: successful collection',
                'severity': ZenEventClasses.Clear,
                'eventKey': 'openstackCeilometerAMQPHeartbeatCollection',
                'eventClassKey': 'EventsSuccess',
                })

        defer.returnValue(data)

    def processMessage(self, amqp, message):
        # add neartbeats to messages on per host, per process base
        msg = {}
        try:
            contentbody = json.loads(message.content.body)
            hostname = contentbody['hostname']
            processname = contentbody['processname']

            if hostname not in heartbeats:
                heartbeats[hostname] = {}
            if processname not in heartbeats[hostname]:
                heartbeats[hostname][processname] = []

            msg['exchange'] = message.fields[3]
            msg['routing_key'] = message.fields[4]
            msg['lastheard'] = time()               # use zenoss side timer

            # keep no more than MAX_MSG_RECORDS records
            while len(heartbeats[hostname][processname]) > (MAX_MSG_RECORDS - 1):
                heartbeats[hostname][processname].pop(0)
            heartbeats[hostname][processname].append(msg)

            amqp.acknowledge(message)

        except Exception, e:
            log.error("Exception while processing ceilometer heartbeat: %r", e)

    def onError(self, result, config):
        errmsg = 'OpenStack AMQP: %s' % result_errmsg(result)
        log.error('%s: %s', config.id, errmsg)

        data = self.new_data()
        data['events'].append({
            'device': config.id,
            'summary': errmsg,
            'severity': ZenEventClasses.Error,
            'eventKey': 'openstackCeilometerHeartbeatAMQPDataSourceCollection',
            'eventClassKey': 'HeartbeatAMQPDataSourceFailure',
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
            del amqp_client[config.id]
