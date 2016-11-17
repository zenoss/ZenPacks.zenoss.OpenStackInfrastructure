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

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks

import zope.component
from zope.component import adapts, getUtility
from zope.interface import implements

from Products.ZenEvents import ZenEventClasses

from ZenPacks.zenoss.OpenStackInfrastructure.datasources.AMQPDataSource import (
    AMQPDataSource, AMQPDataSourcePlugin, AMQPDataSourceInfo,
    IAMQPDataSourceInfo)

from ZenPacks.zenoss.OpenStackInfrastructure.utils import result_errmsg, ExpiringFIFO, sleep, amqp_timestamp_to_int

# How long to cache data in memory before discarding it (data that
# is coming from ceilometer, but not consumed by any monitoring templates).
# Should be at least the cycle interval.
CACHE_EXPIRE_TIME = 15*60


class EventsAMQPDataSource(AMQPDataSource):
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

    _properties = AMQPDataSource._properties + ()


class IEventsAMQPDataSourceInfo(IAMQPDataSourceInfo):
    '''
    API Info interface for IEventsAMQPDataSource.
    '''

    pass


class EventsAMQPDataSourceInfo(AMQPDataSourceInfo):
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
cache = defaultdict(CeilometerEventCache)


class EventsAMQPDataSourcePlugin(AMQPDataSourcePlugin):
    proxy_attributes = ()
    queue_name = "$OpenStackInboundEvent"
    failure_eventClassKey = 'EventsFailure'

    @inlineCallbacks
    def collect(self, config):
        log.debug("Collect for OpenStack AMQP Events (%s)" % config.id)

        data = super(EventsAMQPDataSourcePlugin, self).collect(config)
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

    def processMessage(self, device_id, value):
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

