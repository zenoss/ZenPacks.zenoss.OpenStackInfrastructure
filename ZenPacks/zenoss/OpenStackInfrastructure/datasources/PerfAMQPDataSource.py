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
import json
from functools import partial
import time
import re

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks

import zope.component
from zope.component import adapts, getUtility
from zope.interface import implements

from Products.Five import zcml
from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.ZenEvents import ZenEventClasses
import Products.ZenMessaging.queuemessaging
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.utils import ZuulMessageFactory as _t

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import (
    PythonDataSource, PythonDataSourcePlugin, PythonDataSourceInfo,
    IPythonDataSourceInfo)

from ZenPacks.zenoss.OpenStackInfrastructure.utils import result_errmsg, ExpiringFIFO, sleep, amqp_timestamp_to_int
from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema
from zenoss.protocols.twisted.amqp import AMQPFactory

# How long to cache data in memory before discarding it (data that
# is coming from ceilometer, but not consumed by any monitoring templates).
# Should be at least the cycle interval.
CACHE_EXPIRE_TIME = 25*60


class PerfAMQPDataSource(PythonDataSource):
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

    _properties = PythonDataSource._properties + (
        {'id': 'meter', 'type': 'string'},
        )


class IPerfAMQPDataSourceInfo(IPythonDataSourceInfo):
    '''
    API Info interface for IPerfAMQPDataSource.
    '''

    meter = schema.TextLine(
        group=_t('OpenStack Ceilometer'),
        title=_t('meter Name'))


class PerfAMQPDataSourceInfo(PythonDataSourceInfo):
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
        self.new_keys.remove(key)

    def get_new_keys(self):
        # return a list of new keys (tuples of (resourceId, meter)) that have
        # been seen but not acknowledged with clear_new_key()
        return list(self.new_keys)

# Persistent state
amqp_client = {}                     # amqp_client[device.id] = AMQClient object
cache = defaultdict(CeilometerPerfCache)


class PerfAMQPDataSourcePlugin(PythonDataSourcePlugin):
    proxy_attributes = ('resourceId')

    def __init__(self, *args, **kwargs):
        super(PerfAMQPDataSourcePlugin, self).__init__(*args, **kwargs)

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
        return {
            'meter':    datasource.talesEval(datasource.meter, context),
            'resourceId': context.resourceId,
            'component_meta_type': context.meta_type
        }

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
            self._queueSchema = getUtility(IQueueSchema)

            amqp = AMQPFactory(self._amqpConnectionInfo, self._queueSchema)
            queue = self._queueSchema.getQueue('$OpenStackInboundPerf', replacements={'device': config.id})
            log.debug("Listening on queue: %s with binding to routing key %s" % (queue.name, queue.bindings['$OpenStackInbound'].routing_key))
            yield amqp.listen(queue, callback=partial(self.processMessage, amqp, config.id))
            amqp_client[config.id] = amqp

            # Give time for some of the existing messages to be processed during
            # this initial collection cycle
            yield sleep(10)

        data = self.new_data()
        device_id = config.configId

        for ds in config.datasources:
            for entry in cache[device_id].get_perf(ds.params['resourceId'], ds.params['meter']):
                log.debug("perf %s/%s=%s @ %s" % (ds.params['resourceId'], ds.params['meter'], entry.value, entry.timestamp))
                data['values'][ds.component][ds.datasource] = (entry.value, entry.timestamp)

        # Look for new vNICs that we are getting data for from ceilometer, but
        # are not modeled in zenoss yet.  (vnic modeling only happens
        # periodically via zenmodeler)
        known_instances = dict()
        known_vnics = dict()
        for ds in config.datasources:
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
                'eventClassKey': 'PerfSuccess',
                })

        defer.returnValue(data)

    def processMessage(self, amqp, device_id, message):
        try:
            value = json.loads(message.content.body)
            log.debug(value)

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
            'eventClassKey': 'PerfFailure',
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
