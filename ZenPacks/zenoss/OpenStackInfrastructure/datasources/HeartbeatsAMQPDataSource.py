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
from time import time
from functools import partial

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks, returnValue

import zope.component
from zope.component import adapts, getUtility, queryUtility
from zope.interface import implements

from Products.ZenCollector.interfaces import ICollector
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
last_heard_heartbeats = {}
MAX_TIME_LAPSE = 300


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
    def getService(self, service_name):
        collector = zope.component.queryUtility(ICollector)
        service = yield collector.getService(service_name)
        returnValue(service)

    @inlineCallbacks
    def collect(self, config):
        log.debug("Collect for OpenStack AMQP Heartbeats (%s)" % config.id)

        service = yield self.getService('ZenPacks.zenoss.OpenStackInfrastructure.services.OpenStackService')
        expected_heartbeats = yield service.callRemote('expected_ceilometer_heartbeats', config.id)

        if not expected_heartbeats:
            return
            
        hostnames = expected_heartbeats[0]['hostnames']
        processes = expected_heartbeats[0]['processes']

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

        for host in last_heard_heartbeats.keys():
            if host not in hostnames:
                continue

            for proc in last_heard_heartbeats[host].keys():
                if proc not in processes:
                    continue

                # diff > MAX_TIME_LAPSE?
                time_diff = time() - \
                    last_heard_heartbeats[host][proc]['lastheard']
                if time_diff > MAX_TIME_LAPSE:

                    evt = {
                        'device': device_id,
                        'severity': ZenEventClasses.Warning,
                        'eventKey': host + '_' + proc,
                        'summary': 'Have not heard from '+ \
                                   proc + ' on ' + host + \
                                   ' for more than ' + \
                                   str(MAX_TIME_LAPSE) + ' seconds. ' + \
                                   'Please check its status. ' + \
                                   'Restart it if necessary',
                        'eventClassKey': 'openStackCeilometerHeartbeat',
                    }

                    from pprint import pformat
                    log.error(pformat(evt))

                else:

                    evt = {
                        'device': device_id,
                        'severity': ZenEventClasses.Clear,
                        'eventKey': host + '_' + proc,
                        'summary': 'Clear event for '+ \
                                   proc + ' on ' + host,
                        'eventClassKey': 'openStackCeilometerHeartbeat',
                    }

                data['events'].append(evt)

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
        # add neartbeats to last_heard_heartbeats on per host, per process base
        msg = {}
        try:
            contentbody = json.loads(message.content.body)
            hostname = contentbody['hostname']
            processname = contentbody['processname']

            if hostname not in last_heard_heartbeats:
                last_heard_heartbeats[hostname] = {}

            msg['exchange'] = message.fields[3]
            msg['routing_key'] = message.fields[4]
            msg['lastheard'] = contentbody['timestamp']

            last_heard_heartbeats[hostname][processname] = msg

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
            'eventKey': 'AMQPDataSourceCollection',
            'eventClassKey': 'openStackCeilometerHeartbeat',
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
