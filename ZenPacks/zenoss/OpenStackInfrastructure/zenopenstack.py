#!/usr/bin/env python
##############################################################################
#
# Copyright (C) Zenoss, Inc. 2018, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""zenopenstack

Event and metric collection daemon for openstack ceilometer

"""

import logging
log = logging.getLogger('zen.OpenStack.zenopenstack')

import Globals

from collections import deque
import json
import time

from twisted.internet import reactor, defer
from twisted.spread import pb
from twisted.web.resource import Resource, NoResource, ErrorPage
from twisted.web.server import Site

import zope.interface

from Products.ZenCollector.daemon import CollectorDaemon

from Products.ZenCollector.interfaces import (
    ICollector,
    ICollectorPreferences,
    IDataService,
    IEventService,
    IStatisticsService,
    IScheduledTask
)

from Products.ZenCollector.tasks import (
    NullTaskSplitter,
    BaseTask,
    TaskStates
)

from Products.ZenUtils.Utils import unused

unused(Globals)

from ZenPacks.zenoss.OpenStackInfrastructure.utils import amqp_timestamp_to_int
from ZenPacks.zenoss.OpenStackInfrastructure.services.OpenStackConfig import OpenStackDataSourceConfig
pb.setUnjellyableForClass(OpenStackDataSourceConfig, OpenStackDataSourceConfig)


class Registry(object):
    # Holds all the configured devices, metrics, etc.  Used by the
    # web server to process incoming messages.

    def __init__(self):
        self.configs = {}

    def all_devices(self):
        return self.configs.keys()

    def has_device(self, device_id):
        return device_id in self.configs

    def remove_device(self, device_id):
        if device_id in self.configs:
            del self.configs[device_id]

    def set_datasources(self, device_id, datasources):
        # (list of OpenStackDataSourceConfig as returned by OpenStackConfig service)

        self.configs[device_id] = {}
        for datasource in datasources:
            self.configs.setdefault(device_id, {})
            self.configs[device_id].setdefault(datasource.resourceId, {})
            self.configs[device_id][datasource.resourceId][datasource.meter] = datasource.points

    def get_datapoints(self, device_id, resourceId, metric_name):
        if device_id not in self.configs:
            return []
        return self.configs[device_id].get(resourceId, {}).get(metric_name, [])


REGISTRY = Registry()
METRIC_QUEUE = deque()
EVENT_QUEUE = deque()
MAP_QUEUE = deque()


class Root(Resource):

    def getChild(self, path, request):
        if path == '':
            return self
        else:
            return Resource.getChild(self, path, request)

    def render_GET(self, request):
        request.setResponseCode(200)
        request.setHeader(b"content-type", b"application/json")

        return json.dumps({
            "links": [
                {
                    "href": "/ceilometer",
                    "rel": "related"
                }
            ]
        })


class CeilometerRoot(Resource):

    def getChild(self, path, request):
        if path == '':
            return self
        else:
            return Resource.getChild(self, path, request)

    def render_GET(self, request):
        request.setResponseCode(200)
        request.setHeader(b"content-type", b"application/json")
        return json.dumps({
            "versions": [
                {
                    "id": "v1.0",
                    "links": [
                        {
                            "href": "/ceilometer/v1/",
                            "rel": "self"
                        }
                    ],
                    "status": "SUPPORTED",
                    "version": "1.0",
                    "updated": "2018-10-23T00:00:00Z"
                }
            ]
        })


class CeilometerV1(Resource):
    pass


class CeilometerV1Samples(Resource):
    isLeaf = True

    def render_POST(self, request):
        if len(request.postpath) != 1:
            return NoResource().render(request)

        device_id = request.postpath[0]

        if not REGISTRY.has_device(device_id):
            return NoResource(message="Unrecognized device '%s'" % device_id).render(request)

        if request.received_headers.get('content-type') != 'application/json':
            return ErrorPage(415, "Unsupported Media Type", "Unsupported Media Type").render(request)
        try:
            payload = json.loads(request.content.getvalue())
        except Exception, e:
            log.exception("Error parsing JSON data")
            return ErrorPage(400, "Bad Request", "Error parsing JSON data: %s" % e).render(request)

        samples = []
        now = time.time()

        try:
            for sample in payload:
                resourceId = sample['resource_id']
                meter = sample['name']
                value = sample['volume']
                timestamp = amqp_timestamp_to_int(sample['timestamp'])

                if timestamp > now:
                    log.debug("[%s/%s] Timestamp (%s) appears to be in the future.  Using now instead." % (resourceId, meter, value['data']['timestamp']))

                samples.append((resourceId, meter, value, timestamp))

        except Exception, e:
            log.exception("Error processing sample data")
            return ErrorPage(422, "Unprocessable Entity", "Error processing data: %s" % e).render(request)

        for sample in samples:
            datapoints = REGISTRY.get_datapoints(device_id, resourceId, meter)

            if datapoints:
                for dp in datapoints:
                    log.debug("Storing datapoint %s / %s value %d @ %d", device_id, dp.rrdPath, value, timestamp)
                    METRIC_QUEUE.append((dp, value, timestamp))

            else:
                log.debug("Ignoring unmonitored sample: %s" % str(sample))

        # An empty response is fine.
        return b""


class CeilometerV1Events(Resource):
    isLeaf = True

    def render_POST(self, request):
        if len(request.postpath) != 1:
            return NoResource().render(request)

        device_id = request.postpath[0]

        if not REGISTRY.has_device(device_id):
            return NoResource(message="Unrecognized device '%s'" % device_id).render(request)

        if request.received_headers.get('content-type') != 'application/json':
            return ErrorPage(415, "Unsupported Media Type", "Unsupported Media Type").render(request)
        try:
            payload = json.loads(request.content.getvalue())
        except Exception, e:
            log.exception("Error parsing JSON data")
            return ErrorPage(400, "Bad Request", "Error parsing JSON data: %s" % e).render(request)

        log.info("NOT IMPLEMENTED event update: %s" % str(request.content))
        # Todo: implement event support- we can use the code in events.py for this-
        # all the code to generate objmaps exists.. so we can call that, and invoke
        # applydatamaps before passing on the events to zenoss.  This would take
        # load off zeneventd and move the datamap processing to zenhub.

        # An empty response is fine.
        return b""

class WebServer(object):
    site = None

    def __init__(self, preferences):
        self.preferences = preferences

    def initialize(self):
        port = self.preferences.options.listenport

        root = Root()
        ceilometer_root = CeilometerRoot()
        root.putChild('ceilometer', ceilometer_root)

        ceilometer_v1 = CeilometerV1()
        ceilometer_v1samples = CeilometerV1Samples()
        ceilometer_v1events = CeilometerV1Events()

        ceilometer_root.putChild('v1', ceilometer_v1)
        ceilometer_v1.putChild('samples', ceilometer_v1samples)
        ceilometer_v1.putChild('events', ceilometer_v1events)

        self.site = Site(root)
        log.info("Starting http listener on port %d", port)
        reactor.listenTCP(port, self.site)


class OpenStackCollectorDaemon(CollectorDaemon):
    initialServices = CollectorDaemon.initialServices + ['ModelerService']

    def _updateConfig(self, cfg):
        configId = cfg.configId
        self.log.debug("Processing configuration for %s", configId)

        REGISTRY.set_datasources(configId, cfg.datasources)

        return True

    def _deleteDevice(self, deviceId):
        self.log.debug("Removing config for %s", deviceId)

        REGISTRY.remove_device(deviceId)

    def getInitialServices(self):
        # CollectorDaemon does not honor initialServices currently (it is
        # overwritten to just the base services pl`us the configuration service),
        # so ModelerService will not be available unless we force the issue:

        for service in OpenStackCollectorDaemon.initialServices:
            if service not in self.initialServices:
                log.info("Re-adding initialService: %s", service)
                self.initialServices.append(service)

        return super(OpenStackCollectorDaemon, self).getInitialServices()


class TaskSplitter(NullTaskSplitter):
    def splitConfiguration(self, configs):
        collector = zope.component.getUtility(ICollector)
        for config in configs:
            collector._updateConfig(config)


class OpenStackEventTask(BaseTask):
    zope.interface.implements(IScheduledTask)

    def __init__(self, taskName, configId, scheduleIntervalSeconds=60, taskConfig=None):
        super(OpenStackEventTask, self).__init__(
            taskName, configId, scheduleIntervalSeconds, taskConfig)

        self.name = taskName
        self.configId = configId
        self.state = TaskStates.STATE_IDLE
        self.interval = scheduleIntervalSeconds
        self._collector = zope.component.queryUtility(ICollector)

    def doTask(self):
        log.debug("Draining event queue")

        if len(EVENT_QUEUE):
            self.state = 'SEND_EVENTS'

            while len(EVENT_QUEUE):
                event = EVENT_QUEUE.popleft()
                yield self._collector.sendEvent(event)

            self.state = TaskStates.STATE_IDLE


class OpenStackPerfTask(BaseTask):
    zope.interface.implements(IScheduledTask)

    def __init__(self, taskName, configId, scheduleIntervalSeconds=60, taskConfig=None):
        super(OpenStackPerfTask, self).__init__(
            taskName, configId, scheduleIntervalSeconds, taskConfig)

        self.name = taskName
        self.configId = configId
        self.state = TaskStates.STATE_IDLE
        self.interval = scheduleIntervalSeconds
        self._dataService = zope.component.queryUtility(IDataService)

        self.writeMetricWithMetadata = hasattr(
            self._dataService, 'writeMetricWithMetadata')

    @defer.inlineCallbacks
    def doTask(self):
        log.debug("Draining metric queue")

        if len(METRIC_QUEUE):
            self.state = 'STORE_PERF_DATA'

            while len(METRIC_QUEUE):
                dp, value, timestamp = METRIC_QUEUE.popleft()
                log.debug("Publishing datapoint %s value %f @ %f", dp.rrdPath, value, timestamp)

                if self.writeMetricWithMetadata:
                    yield defer.maybeDeferred(
                        self._dataService.writeMetricWithMetadata,
                        dp.dpName,
                        value,
                        dp.rrdType,
                        timestamp=timestamp,
                        min=dp.rrdMin,
                        max=dp.rrdMax,
                        metadata=dp.metadata)

                else:
                    self._dataService.writeRRD(
                        dp.rrdPath,
                        value,
                        dp.rrdType,
                        rrdCommand=dp.rrdCreateCommand,
                        cycleTime=self.interval,
                        min=dp.rrdMin,
                        max=dp.rrdMax,
                        timestamp=timestamp,
                        allowStaleDatapoint=False)
            self.state = TaskStates.STATE_IDLE


class OpenStackMapTask(BaseTask):
    zope.interface.implements(IScheduledTask)

    def __init__(self, taskName, configId, scheduleIntervalSeconds=60, taskConfig=None):
        super(OpenStackMapTask, self).__init__(
            taskName, configId, scheduleIntervalSeconds, taskConfig)

        self.name = taskName
        self.configId = configId
        self.state = TaskStates.STATE_IDLE
        self.interval = scheduleIntervalSeconds
        self._collector = zope.component.queryUtility(ICollector)

    @defer.inlineCallbacks
    def doTask(self):
        log.debug("Draining datamap queue")

        remoteProxy = self._collector.getServiceNow('ModelerService')

        maps = {}
        for device_id, datamap in MAP_QUEUE:
            maps.setdefault(device_id, [])
            maps[device_id].append(datamap)
        MAP_QUEUE.clear()

        self.state = 'SEND_DATAMAPS'

        for device_id in maps:
            yield remoteProxy.callRemote(
                'applyDataMaps', device_id, maps[device_id])

        self.state = TaskStates.STATE_IDLE


class Preferences(object):
    zope.interface.implements(ICollectorPreferences)

    collectorName = 'zenopenstack'
    configurationService = 'ZenPacks.zenoss.OpenStackInfrastructure.services.OpenStackConfig'
    cycleInterval = 5 * 60  # 5 minutes
    configCycleInterval = 60 * 60 * 12  # 12 hours
    maxTasks = None  # use system default

    # do not let the collector maintenance function pause devices
    pauseUnreachableDevices = False

    def buildOptions(self, parser):
        parser.add_option(
            '--listenport',
            dest='listenport',
            type='int',
            default=8242,
            help="Port to listen on for HTTP requests")

    def postStartup(self):
        pass

    def postStartupTasks(self):

        # We run one task for each type of processing- each consumes and sends
        # on data from a corresponding queue.
        yield OpenStackPerfTask('zenopenstack-perf', configId='zenopenstack-perf', scheduleIntervalSeconds=60)
        yield OpenStackEventTask('zenopenstack-event', configId='zenopenstack-event', scheduleIntervalSeconds=60)
        yield OpenStackMapTask('zenopenstack-map', configId='zenopenstack-map', scheduleIntervalSeconds=60)


def main():
    preferences = Preferences()
    task_splitter = TaskSplitter()
    webserver = WebServer(preferences)

    collectordaemon = OpenStackCollectorDaemon(
        preferences,
        task_splitter,
        initializationCallback=webserver.initialize)

    collectordaemon.run()


if __name__ == '__main__':
    main()
