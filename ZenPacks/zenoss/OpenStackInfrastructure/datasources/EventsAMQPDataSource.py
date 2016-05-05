##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.EventsAMQP')

from collections import defaultdict
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

from ZenPacks.zenoss.OpenStackInfrastructure.utils import result_errmsg, ExpiringFIFO, sleep, amqp_timestamp_to_int
from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema
from zenoss.protocols.twisted.amqp import AMQPFactory

# How long to cache data in memory before discarding it (data that
# is coming from ceilometer, but not consumed by any monitoring templates).
# Should be at least the cycle interval.
CACHE_EXPIRE_TIME = 15*60


class EventsAMQPDataSource(PythonDataSource):
    '''
    Datasource used to capture data and events shipped to us from OpenStack
    Ceilometer via AMQP.
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack Ceilometer Events AMQP',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 30

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'EventsAMQPDataSource.EventsAMQPDataSourcePlugin'

    # EventsAMQPDataSource

    _properties = PythonDataSource._properties + ()


class IEventsAMQPDataSourceInfo(IPythonDataSourceInfo):
    '''
    API Info interface for IEventsAMQPDataSource.
    '''

    pass


class EventsAMQPDataSourceInfo(PythonDataSourceInfo):
    '''
    API Info adapter factory for EventsAMQPDataSource.
    '''

    implements(IEventsAMQPDataSourceInfo)
    adapts(EventsAMQPDataSource)

    testable = False


class CeilometerEventCache(ExpiringFIFO):
    '''
    As data arrives via AMQP, we place it into an in-memory cache (for a
    period of time), and then pull it out of the cache during normal collection
    cycles.
    '''
    expireTime = CACHE_EXPIRE_TIME

    def __init__(self):
        super(CeilometerEventCache, self).__init__(self.expireTime, "events")


# Persistent state
amqp_client = {}                     # amqp_client[device.id] = AMQClient object
cache = defaultdict(CeilometerEventCache)


class EventsAMQPDataSourcePlugin(PythonDataSourcePlugin):
    proxy_attributes = ()

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
        log.debug("Collect for OpenStack AMQP Events (%s)" % config.id)

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
            self._queueSchema = getUtility(IQueueSchema)

            amqp = AMQPFactory(self._amqpConnectionInfo, self._queueSchema)
            queue = self._queueSchema.getQueue('$OpenStackInboundEvent', replacements={'device': config.id})
            log.info("Listening on queue: %s with binding to routing key %s" % (queue.name, queue.bindings['$OpenStackInbound'].routing_key))
            yield amqp.listen(queue, callback=partial(self.processMessage, amqp, config.id))
            amqp_client[config.id] = amqp

            # Give time for some of the existing messages to be processed during
            # this initial collection cycle
            yield sleep(10)

        data = self.new_data()
        device_id = config.configId

        for entry in cache[device_id].get():
            c_event = entry.value

            evt = {
                'device': device_id,
                'severity': ZenEventClasses.Info,
                'eventKey': '',
                'summary': 'OpenStackInfrastructure: ' + c_event['event_type'],
                'eventClassKey': 'openstack|' + c_event['event_type'],
            }

            traits = {}
            for trait in c_event['traits']:
                # liberty: [[name, dtype, value] ...]
                # [[u'display_name', 1, u'demo-volume1-snap'], ...]
                traits[trait[0]] = trait[2]

            if 'priority' in traits:
                if traits['priority'] == 'WARN':
                    evt['severity'] = ZenEventClasses.Warning
                elif traits['priority'] == 'ERROR':
                    evt['severity'] = ZenEventClasses.Error

            evt['eventKey'] = c_event['message_id']

            for trait in traits:
                evt['trait_' + trait] = traits[trait]

            from pprint import pformat
            log.debug(pformat(evt))

            data['events'].append(evt)

        if len(data['events']):
            data['events'].append({
                'device': config.id,
                'summary': 'OpenStack Ceilometer AMQP: successful collection',
                'severity': ZenEventClasses.Clear,
                'eventKey': 'openstackCeilometerAMQPCollection',
                'eventClassKey': 'EventsSuccess',
                })

        defer.returnValue(data)

    def processMessage(self, amqp, device_id, message):
        try:
            value = json.loads(message.content.body)
            log.debug(value)

            if value['device'] != device_id:
                log.error("While expecting a message for %s, received a message regarding %s instead!" % (device_id, value['device']))
                return

            if value['type'] == 'event':
                # Message is a json-serialized version of a ceilometer.storage.models.Event object
                # (http://docs.openstack.org/developer/ceilometer/_modules/ceilometer/storage/models.html#Event)
                timestamp = amqp_timestamp_to_int(value['data']['generated'])
                log.debug("Incoming event (%s) %s" % (timestamp, value['data']))
                cache[device_id].add(value['data'], timestamp)
            else:
                log.error("Discarding unrecognized message type: %s" % value['type'])

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
            'eventClassKey': 'EventsFailure',
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
