##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStackCeilometerAMQP')

from collections import defaultdict, deque
import json
from functools import partial
import time
import dateutil
import datetime
import pytz

from twisted.internet import defer, reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import deferLater

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

from ZenPacks.zenoss.OpenStack.utils import result_errmsg
from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema
from zenoss.protocols.twisted.amqp import AMQPFactory

# How long to cache data in memory before discarding it (data that
# is coming from ceilometer, but not consumed by any monitoring templates).
# Should be at least the cycle interval.
CACHE_EXPIRE_TIME = 15*60

_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)


class OpenStackCeilometerAMQPDataSource(PythonDataSource):
    '''
    Datasource used to capture data and events shipped to us from OpenStack
    Ceilometer via AMQP.
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStack'

    sourcetypes = ('OpenStack Ceilometer AMQP',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 300

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStack.datasources.'\
        'OpenStackCeilometerAMQPDataSource.OpenStackCeilometerAMQPDataSourcePlugin'

    # OpenStackCeilometerAMQPDataSource
    meter = ''

    _properties = PythonDataSource._properties + (
        {'id': 'meter', 'type': 'string'},
        )


class IOpenStackCeilometerAMQPDataSourceInfo(IPythonDataSourceInfo):
    '''
    API Info interface for OpenStackCeilometerAMQP.
    '''

    meter = schema.TextLine(
        group=_t('OpenStack Ceilometer'),
        title=_t('meter Name'))


class OpenStackCeilometerAMQPDataSourceInfo(PythonDataSourceInfo):
    '''
    API Info adapter factory for OpenStackCeilometerAMQPDataSource.
    '''

    implements(IOpenStackCeilometerAMQPDataSourceInfo)
    adapts(OpenStackCeilometerAMQPDataSource)

    testable = False

    meter = ProxyProperty('meter')


def sleep(sec):
    # Simple helper to delay asynchronously for some number of seconds.
    return deferLater(reactor, sec, lambda: None)


class CeilometerCacheEntry(object):
    def __init__(self, value, timestamp):
        self.value = value
        self.timestamp = timestamp
        self.expires = time.time() + CACHE_EXPIRE_TIME


class CeilometerCache(object):
    '''
    As data arrives via AMQP, we place it into an in-memory cache (for a
    period of time), and then pull it out of the cache during normal collection
    cycles.
    '''
    event_entries = deque()
    perf_entries = defaultdict(deque)

    def _expire(self, entries, context):
        # remove expired entries from the supplied list (deque)
        now = time.time()

        while len(entries) and entries[0].expires <= now:
            log.debug("Expiration timestamp %s < %s", entries[0].expires, now)
            v = entries.popleft()
            log.debug("Expired %s = %s from cache", context, v.value)

    def add_event(self, value, timestamp):
        entries = self.event_entries
        self._expire(entries, "event")
        entries.append(CeilometerCacheEntry(value, timestamp))

    def add_perf(self, resourceId, meter, value, timestamp):
        log.debug("add_perf(%s/%s) = %s @ %s" % (resourceId, meter, value, timestamp))
        entries = self.perf_entries[(resourceId, meter,)]
        self._expire(entries, (resourceId, meter,))
        entries.append(CeilometerCacheEntry(value, timestamp))

    def get_event(self):
        entries = self.event_entries
        self._expire(entries, "event")

        try:
            entry = entries.popleft()
            yield entry.value
        except IndexError:
            # deque is empty.
            return

    def get_perf(self, resourceId, meter, ):
        entries = self.perf_entries[(resourceId, meter,)]
        self._expire(entries, (resourceId, meter,))

        try:
            entry = entries.popleft()
            log.debug("get_perf(%s/%s) = %s @ %s" % (resourceId, meter, entry.value, entry.timestamp))
            yield entry
        except IndexError:
            # deque is empty.
            return


# Persistent state
amqp_client = {}                     # amqp_client[device.id] = AMQClient object
cache = defaultdict(CeilometerCache)


class OpenStackCeilometerAMQPDataSourcePlugin(PythonDataSourcePlugin):
    proxy_attributes = ('resourceId')

    def __init__(self, *args, **kwargs):
        super(OpenStackCeilometerAMQPDataSourcePlugin, self).__init__(*args, **kwargs)

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
            queue = self._queueSchema.getQueue('$OpenStackInbound', replacements={'device': config.id})
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
                'eventClassKey': 'OpenStackCeilometerAMQPSuccess',
                })

        defer.returnValue(data)

    def timestamp_to_int(self, timestamp_string):
        # The timestamps arrive in several formats, so we let
        # dateutil.parser.parse() figure them out.
        dt = dateutil.parser.parse(timestamp_string)
        if dt.tzinfo is None:
            log.debug("Timestamp string (%s) does not contain a timezone- assuming it is UTC." % timestamp_string)
            dt = pytz.utc.localize(dt)

        return (dt - _EPOCH).total_seconds()

    def processMessage(self, device_id, message):
        try:
            value = json.loads(message.content.body)
            log.debug(value)

            if value['type'] == 'event':
                # Message is a json-serialized version of a ceilometer.storage.models.Event object
                # (http://docs.openstack.org/developer/ceilometer/_modules/ceilometer/storage/models.html#Event)
                timestamp = self.timestamp_to_int(value['data']['generated'])
                cache[device_id].add_event(value['data'], timestamp)

            elif value['type'] == 'meter':
                # Message is a json-serialized version of a ceilometer.storage.models.Sample object
                # (http://docs.openstack.org/developer/ceilometer/_modules/ceilometer/storage/models.html#Sample)

                # pull the information we are interested in out of the raw
                # ceilometer Sample data structure.
                resourceId = value['data']['resource_id']
                meter = value['data']['counter_name']
                meter_value = value['data']['counter_volume']
                timestamp = self.timestamp_to_int(value['data']['timestamp'])

                now = time.time()
                if timestamp > now:
                    log.info("Timestamp (%s) appears to be in the future.  Using now instead." % value['data']['timestamp'])

                if timestamp < now - CACHE_EXPIRE_TIME:
                    log.info("Timestamp (%s) is already too old- discarding message." % value['data']['timestamp'])
                else:
                    cache[device_id].add_perf(resourceId, meter, meter_value, timestamp)

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
            'eventClassKey': 'OpenStackCeilometerAMQPError',
            })

        return data

    def cleanup(self, config):
        log.debug("cleanup for OpenStack AMQP (%s)" % config.id)
