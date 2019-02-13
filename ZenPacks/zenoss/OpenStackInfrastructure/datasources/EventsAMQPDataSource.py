##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2019, all rights reserved.
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

from zope.component import adapts
from zope.interface import implements

from Products.ZenEvents import ZenEventClasses
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.utils import ZuulMessageFactory as _t

from ZenPacks.zenoss.OpenStackInfrastructure.datasources.AMQPDataSource import (
    AMQPDataSource, AMQPDataSourcePlugin, AMQPDataSourceInfo,
    IAMQPDataSourceInfo)

from ZenPacks.zenoss.OpenStackInfrastructure.utils import ExpiringFIFO, amqp_timestamp_to_int
from ZenPacks.zenoss.OpenStackInfrastructure.events import event_is_mapped, map_event
from ZenPacks.zenoss.OpenStackInfrastructure.datamaps import ConsolidatingObjectMapQueue

# How long to cache data in memory before discarding it (data that
# is coming from ceilometer, but not consumed by any monitoring templates).
# Should be at least the cycle interval.
CACHE_EXPIRE_TIME = 15 * 60

MAP_QUEUE = defaultdict(ConsolidatingObjectMapQueue)


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

    cycletime = schema.TextLine(
        group=_t('OpenStack Ceilometer'),
        title=_t('Cycletime')
    )


class EventsAMQPDataSourceInfo(AMQPDataSourceInfo):
    '''
    API Info adapter factory for EventsAMQPDataSource.
    '''

    implements(IEventsAMQPDataSourceInfo)
    adapts(EventsAMQPDataSource)

    cycletime = ProxyProperty('cycletime')

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
    proxy_attributes = (
        'zOpenStackProcessEventTypes',
        'zOpenStackIncrementalShortLivedSeconds',
        'zOpenStackIncrementalBlackListSeconds',
        'zOpenStackIncrementalConsolidateSeconds',
    )
    queue_name = "$OpenStackInboundEvent"
    failure_eventClassKey = 'EventsFailure'

    @inlineCallbacks
    def collect(self, config):
        log.debug("Collect for OpenStack AMQP Events (%s)" % config.id)

        data = yield super(EventsAMQPDataSourcePlugin, self).collect(config)
        device_id = config.configId
        ds0 = config.datasources[0]

        # Update queue settings
        MAP_QUEUE[device_id].shortlived_seconds = ds0.zOpenStackIncrementalShortLivedSeconds
        MAP_QUEUE[device_id].delete_blacklist_seconds = ds0.zOpenStackIncrementalBlackListSeconds
        MAP_QUEUE[device_id].update_consolidate_seconds = ds0.zOpenStackIncrementalConsolidateSeconds

        for entry in cache[device_id].get():
            c_event = entry.value
            event_type = c_event['event_type']

            evt = {
                'device': device_id,
                'severity': ZenEventClasses.Info,
                'eventKey': '',
                'summary': 'OpenStackInfrastructure: ' + event_type,
                'eventClassKey': 'openstack-' + event_type,
                'openstack_event_type': event_type
            }

            traits = {}
            for trait in c_event['traits']:
                if isinstance(trait, list) and len(trait) == 3:
                    # [[u'display_name', 1, u'demo-volume1-snap'], ...]
                    traits[trait[0]] = trait[2]
                elif isinstance(trait, dict) and "name" in trait and "value" in trait:
                    # I'm not sure that this format is actually used by ceilometer,
                    # but we're using it in sim_events.py currently.
                    #
                    # [{'name': 'display_name', 'value': 'demo-volume1-snap'}, ...]
                    traits[trait['name']] = trait['value']
                else:
                    log.warning("Unrecognized trait format: %s" % c_event['traits'])

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

            # only pass on events that we actually have mappings for.
            if event_type in ds0.zOpenStackProcessEventTypes:
                data['events'].append(evt)

            if event_is_mapped(evt):
                # Try to turn the event into an objmap.
                try:
                    objmap = map_event(evt)
                    if objmap:
                        log.debug("Mapped %d event to %s", event_type, objmap)
                        MAP_QUEUE[config.id].append(objmap)
                except Exception:
                    log.exception("Unable to process event: %s", evt)

        # Apply any maps that are ready to be applied.
        data['maps'].extend(MAP_QUEUE[config.id].drain())

        data['events'].append({
            'device': config.id,
            'summary': 'OpenStack Ceilometer AMQP: successful collection',
            'severity': ZenEventClasses.Clear,
            'eventKey': 'openstackCeilometerAMQPCollection',
            'eventClassKey': 'EventsSuccess',
        })

        log.debug("Sending datamaps for %s: %s", config.id, data['maps'])

        defer.returnValue(data)

    def processMessage(self, device_id, message, value):
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
