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

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks

import zope.component
from zope.component import adapts, getUtility
from zope.interface import implements

from Products.Five import zcml
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
CACHE_EXPIRE_TIME = 15*60


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
            'resourceId': context.resourceId
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
            log.info("Listening on queue: %s with binding to routing key %s" % (queue.name, queue.bindings['$OpenStackInbound'].routing_key))
            yield amqp.listen(queue, callback=partial(self.processMessage, config.id))
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

    def processMessage(self, device_id, message):
        try:
            value = json.loads(message.content.body)
            log.debug(value)

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
                    log.info("[%s/%s] Timestamp (%s) appears to be in the future.  Using now instead." % (resourceId, meter, value['data']['timestamp']))

                if timestamp < now - CACHE_EXPIRE_TIME:
                    log.info("[%s/%s] Timestamp (%s) is already %d seconds old- discarding message." % (resourceId, meter, value['data']['timestamp'], now-timestamp))
                else:
                    cache[device_id].add_perf(resourceId, meter, meter_value, timestamp)

            else:
                log.error("Discarding unrecognized message type: %s" % value['type'])

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
