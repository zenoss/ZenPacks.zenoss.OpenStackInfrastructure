##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.PerfAMQP')

from collections import defaultdict
import time

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks

import zope.component
from zope.component import adapts, getUtility
from zope.interface import implements

from Products.ZenEvents import ZenEventClasses
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.utils import ZuulMessageFactory as _t

from ZenPacks.zenoss.OpenStackInfrastructure.datasources.AMQPDataSource import (
    AMQPDataSource, AMQPDataSourcePlugin, AMQPDataSourceInfo,
    IAMQPDataSourceInfo)

from ZenPacks.zenoss.OpenStackInfrastructure.utils import result_errmsg, ExpiringFIFO, sleep, amqp_timestamp_to_int

# How long to cache data in memory before discarding it (data that
# is coming from ceilometer, but not consumed by any monitoring templates).
# Should be at least the cycle interval.
CACHE_EXPIRE_TIME = 25*60


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


class PerfAMQPDataSourceInfo(AMQPDataSourceInfo):
    '''
    API Info adapter factory for PerfAMQPDataSource.
    '''

    implements(IPerfAMQPDataSourceInfo)
    adapts(PerfAMQPDataSource)

    testable = False

    meter = ProxyProperty('meter')


class CeilometerPerfCache(object):
    '''
    As data arrives via AMQP, we place it into an in-memory cache (for a
    period of time), and then pull it out of the cache during normal collection
    cycles.
    '''
    expireTime = CACHE_EXPIRE_TIME

    perf_entries = {}

    def add_perf(self, resourceId, meter, value, timestamp):
        log.debug("add_perf(%s/%s) = %s @ %s" % (resourceId, meter, value, timestamp))

        key = (resourceId, meter,)

        if key not in self.perf_entries:
            context = "%s/%s" % key
            self.perf_entries[key] = ExpiringFIFO(self.expireTime, context)

        self.perf_entries[key].add(value, timestamp)

    def get_perf(self, resourceId, meter, ):
        key = (resourceId, meter,)
        if key not in self.perf_entries:
            return

        for entry in self.perf_entries[key].get():
            yield entry


# Persistent state
cache = defaultdict(CeilometerPerfCache)


class PerfAMQPDataSourcePlugin(AMQPDataSourcePlugin):
    proxy_attributes = ('resourceId')
    queue_name = "$OpenStackInboundPerf"
    failure_eventClassKey = 'PerfFailure'

    @classmethod
    def params(cls, datasource, context):
        return {
            'meter':    datasource.talesEval(datasource.meter, context),
            'resourceId': context.resourceId
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug("Collect for OpenStack AMQP (%s)" % config.id)

        data = super(PerfAMQPDataSourcePlugin, self).collect(config)
        device_id = config.configId

        for ds in config.datasources:
            for entry in cache[device_id].get_perf(ds.params['resourceId'], ds.params['meter']):
                log.debug("perf %s/%s=%s @ %s" % (ds.params['resourceId'], ds.params['meter'], entry.value, entry.timestamp))
                data['values'][ds.component][ds.datasource] = (entry.value, entry.timestamp)

        if len(data['values']):
            data['events'].append({
                'device': config.id,
                'component': ds.component,
                'summary': 'OpenStack Ceilometer AMQP: successful collection',
                'severity': ZenEventClasses.Clear,
                'eventKey': 'openstackCeilometerAMQPCollection',
                'eventClassKey': 'PerfSuccess',
                })

        defer.returnValue(data)

    def processMessage(self, device_id, value):
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
                log.debug("[%s/%s] Timestamp (%s) is already %d seconds old- discarding message." % (resourceId, meter, value['data']['timestamp'], now-timestamp))
            else:
                cache[device_id].add_perf(resourceId, meter, meter_value, timestamp)

        else:
            log.error("Discarding unrecognized message type: %s" % value['type'])


