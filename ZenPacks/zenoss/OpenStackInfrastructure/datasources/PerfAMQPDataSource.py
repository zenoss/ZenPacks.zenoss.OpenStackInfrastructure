##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.PerfAMQP')

from collections import defaultdict
import time
import re

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks

from zope.component import adapts
from zope.interface import implements

from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.ZenEvents import ZenEventClasses
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.utils import ZuulMessageFactory as _t

from ZenPacks.zenoss.OpenStackInfrastructure.datasources.AMQPDataSource import (
    AMQPDataSource, AMQPDataSourcePlugin, AMQPDataSourceInfo,
    IAMQPDataSourceInfo)

from ZenPacks.zenoss.OpenStackInfrastructure.utils import ExpiringFIFO, amqp_timestamp_to_int

# How long to cache data in memory before discarding it (data that
# is coming from ceilometer, but not consumed by any monitoring templates).
# Should be at least the cycle interval.
CACHE_EXPIRE_TIME = 25 * 60


class PerfAMQPDataSource(AMQPDataSource):
    '''
    Datasource used to capture data and events shipped to us from OpenStack
    Ceilometer via AMQP.
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack Ceilometer Perf AMQP',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 300

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'PerfAMQPDataSource.PerfAMQPDataSourcePlugin'

    # PerfAMQPDataSource
    meter = ''

    _properties = AMQPDataSource._properties + (
        {'id': 'meter', 'type': 'string'},
    )


class IPerfAMQPDataSourceInfo(IAMQPDataSourceInfo):
    '''
    API Info interface for IPerfAMQPDataSource.
    '''

    meter = schema.TextLine(
        group=_t('OpenStack Ceilometer'),
        title=_t('meter Name'))

    cycletime = schema.TextLine(
        group=_t('OpenStack Ceilometer'),
        title=_t('Cycletime')
    )

class PerfAMQPDataSourceInfo(AMQPDataSourceInfo):
    '''
    API Info adapter factory for PerfAMQPDataSource.
    '''

    implements(IPerfAMQPDataSourceInfo)
    adapts(PerfAMQPDataSource)

    cycletime = ProxyProperty('cycletime')

    testable = False

    meter = ProxyProperty('meter')


class CeilometerPerfCache(object):
    '''
    As data arrives via AMQP, we place it into an in-memory cache (for a
    period of time), and then pull it out of the cache during normal collection
    cycles.
    '''
    expireTime = CACHE_EXPIRE_TIME

    perf_entries = None
    new_keys = None
    all_keys = None

    def __init__(self):
        self.perf_entries = {}
        self.new_keys = set()
        self.all_keys = set()

    def add_perf(self, resourceId, meter, value, timestamp):
        log.debug("add_perf(%s/%s) = %s @ %s" % (resourceId, meter, value, timestamp))

        key = (resourceId, meter,)

        if key not in self.perf_entries:
            context = "%s/%s" % key
            self.perf_entries[key] = ExpiringFIFO(self.expireTime, context)

        self.perf_entries[key].add(value, timestamp)
        if key not in self.all_keys:
            self.all_keys.add(key)
            self.new_keys.add(key)

    def get_perf(self, resourceId, meter, ):
        key = (resourceId, meter,)
        if key not in self.perf_entries:
            return

        for entry in self.perf_entries[key].get():
            yield entry

    def clear_new_key(self, key):
        if key in self.new_keys:
            self.new_keys.remove(key)

    def get_new_keys(self):
        # return a list of new keys (tuples of (resourceId, meter)) that have
        # been seen but not acknowledged with clear_new_key()
        return list(self.new_keys)


# Persistent state
cache = defaultdict(CeilometerPerfCache)


class PerfAMQPDataSourcePlugin(AMQPDataSourcePlugin):
    proxy_attributes = ('resourceId')
    queue_name = "$OpenStackInboundPerf"
    failure_eventClassKey = 'PerfFailure'

    @classmethod
    def params(cls, datasource, context):
        return {
            'meter': datasource.talesEval(datasource.meter, context),
            'resourceId': context.resourceId,
            'component_meta_type': context.meta_type
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug("Collect for OpenStack AMQP Perf (%s)" % config.id)

        data = yield super(PerfAMQPDataSourcePlugin, self).collect(config)
        device_id = config.configId

        for ds in config.datasources:
            if 'meter' not in ds.params or 'resourceId' not in ds.params:
                log.warn('Skipping collection for bad datasource %s', ds)
                continue
            for entry in cache[device_id].get_perf(ds.params.get('resourceId'), ds.params.get('meter')):
                log.debug("perf %s/%s=%s @ %s" % (ds.params['resourceId'], ds.params['meter'], entry.value, entry.timestamp))
                data['values'][ds.component].setdefault(ds.datasource, [])
                data['values'][ds.component][ds.datasource].append((entry.value, entry.timestamp))

        # Look for new vNICs that we are getting data for from ceilometer, but
        # are not modeled in zenoss yet.  (vnic modeling only happens
        # periodically via zenmodeler)
        known_instances = dict()
        known_vnics = dict()
        for ds in config.datasources:
            if 'resourceId' not in ds.params:
                log.warn('Skipping identification for bad datasource %s', ds)
                continue
            if ds.params['component_meta_type'] == 'OpenStackInfrastructureInstance':
                known_instances[ds.params['resourceId']] = ds.component
            elif ds.params['component_meta_type'] == 'OpenStackInfrastructureVnic':
                known_vnics[ds.params['resourceId']] = ds.component

        potential_vnic_resourceIds = set()
        for key in cache[device_id].get_new_keys():
            resourceId, meter = key

            if meter.startswith("network") and resourceId not in known_vnics:
                potential_vnic_resourceIds.add(resourceId)
            else:
                # not of interest to us.
                cache[device_id].clear_new_key(key)

        for resourceId in potential_vnic_resourceIds:
            log.info("Checking possible new vnic reference: %s" % resourceId)
            # ok, let's assume the rest of it is probably a metric.  If it
            # corresponds to a known instance, we can create a vNIC for it.
            for instanceUUID in known_instances:
                # The first time we see a network-related metric, we do a
                # loop through all modeled instances to see if this seems
                # to be a vNIC on that instance.  This will be tried once per
                # polling cycle per resource until it is matched to an instance.
                # The assumption is that most of the time, this will only
                # need to be done once or twice per vnic, before we find a known
                # instance id in there and model this new vnic.

                # Vnic resourceIds are of the form:
                #  [instanceName]-[instanceUUID]-[vnicName]
                #  instance-00000001-95223d22-d3af-4b06-a91c-81114d557bd1-tap908bc571-0d

                match = re.search("-%s-(.*)$" % instanceUUID, resourceId)
                if match:
                    vnicName = match.group(1)
                    instance_id = known_instances[instanceUUID]
                    vnic_id = str('vnic-%s-%s' % (instanceUUID, vnicName))

                    log.info("Discovered new vNIC (%s)", vnic_id)
                    known_vnics[resourceId] = vnic_id

                    data['maps'].append(ObjectMap({
                        'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Vnic',
                        'id': vnic_id,
                        'compname': 'components/%s' % instance_id,
                        'relname': 'vnics',
                        'title': vnicName,
                        'resourceId': resourceId
                    }))

                    # Note- we model the new vnic, but we don't store any
                    # perf data for it yet, because we don't have the right
                    # datasource names, etc, until we get a config from zenhub.
                    # That should happen by the next cycle (10 minutes)

                    for key in cache[device_id].get_new_keys():
                        newResourceId, _ = key
                        if resourceId == newResourceId:
                            cache[device_id].clear_new_key(key)
                    break

            if not match:
                log.info("Instance could not be identified at this time.")

        if len(data['values']):
            data['events'].append({
                'device': config.id,
                'component': ds.component,
                'summary': 'OpenStack Ceilometer AMQP: successful collection',
                'severity': ZenEventClasses.Clear,
                'eventKey': 'openstackCeilometerAMQPCollection',
                'eventClassKey': 'openstack-PerfSuccess',
            })

        defer.returnValue(data)

    def processMessage(self, device_id, message, value):
        if value['device'] != device_id:
            log.error("While expecting a message for %s, received a message regarding %s instead!" % (device_id, value['device']))
            return

        if value['type'] == 'meter':
            # Message is a json-serialized version of a ceilometer.storage.models.Sample object
            # (http://docs.openstack.org/developer/ceilometer/_modules/ceilometer/storage/models.html#Sample)

            # pull the information we are interested in out of the raw
            # ceilometer Sample data structure.
            resourceId = value['data']['resource_id']
            meter = value['data']['counter_name']
            meter_value = value['data']['counter_volume']
            timestamp = amqp_timestamp_to_int(value['data']['timestamp'])

            now = time.time()
            if timestamp > now:
                log.debug("[%s/%s] Timestamp (%s) appears to be in the future.  Using now instead." % (resourceId, meter, value['data']['timestamp']))

            if timestamp < now - CACHE_EXPIRE_TIME:
                log.debug("[%s/%s] Timestamp (%s) is already %d seconds old- discarding message." % (resourceId, meter, value['data']['timestamp'], now - timestamp))
            else:
                cache[device_id].add_perf(resourceId, meter, meter_value, timestamp)

        else:
            log.error("Discarding unrecognized message type: %s" % value['type'])
