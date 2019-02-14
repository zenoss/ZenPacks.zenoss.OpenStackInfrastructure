#!/usr/bin/env python
##############################################################################
#
# Copyright (C) Zenoss, Inc. 2018-2019, all rights reserved.
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

import cgi
from collections import defaultdict, deque
import datetime
from functools import partial
import json
from metrology import Metrology
from metrology.registry import registry as metrology_registry
from metrology.instruments import Meter
import re
import time
from pprint import pformat
import socket

from twisted.internet import reactor, defer, task
import twisted.manhole.telnet
from twisted.python import log as twisted_log
from twisted.spread import pb
from twisted.web.http import combinedLogFormatter, datetimeToLogString
from twisted.web.resource import Resource as TwistedResource, NoResource, ErrorPage
from twisted.web.server import Site as TwistedSite

import zope.interface
import zope.component

from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.ZenCollector.daemon import CollectorDaemon

from Products.ZenCollector.interfaces import (
    ICollector,
    ICollectorPreferences,
    IDataService,
    IScheduledTask
)

from Products.ZenCollector.tasks import (
    NullTaskSplitter,
    BaseTask,
    TaskStates
)

from Products.ZenEvents import ZenEventClasses
from Products.ZenUtils.Utils import unused, prepId

unused(Globals)

from ZenPacks.zenoss.OpenStackInfrastructure.events import event_is_mapped, map_event
from ZenPacks.zenoss.OpenStackInfrastructure.datamaps import ConsolidatingObjectMapQueue
from ZenPacks.zenoss.OpenStackInfrastructure.utils import amqp_timestamp_to_int
from ZenPacks.zenoss.OpenStackInfrastructure.services.OpenStackConfig import OpenStackDataSourceConfig

pb.setUnjellyableForClass(OpenStackDataSourceConfig, OpenStackDataSourceConfig)


class HTTPDebugLogBuffer(object):
    """Process payload data from ceilometer.publisher.http."""

    def __init__(self, cache_size=100):
        # Create a dict cache that consists of deques of size self.cache_size
        self.cache_size = cache_size
        self.cache = defaultdict(partial(deque, maxlen=self.cache_size))

    def store_request(self, request, response):
        """Store events in the cache, update statistics.

        Allow for separate samples/events/URI cache data.
        """

        # Create a unique client_id that has: host/uri
        client_ip = request.getClientIP()
        client_id = (client_ip, request.uri)

        # Add the client's message to the cache
        self.cache[client_id].append({
            'timestamp': datetime.datetime.now(),
            'response_code': request.code,
            'response_code_message': request.code_message,
            'request_body': request.content.getvalue(),
            'response_body': response,
            'zenoss_actions': request._zaction
        })

        # --------------------------------------------------------------------
        # Use Metrology to record the event
        # --------------------------------------------------------------------
        v = dict(
            dotted_uri=request.uri.replace('/', '.').strip('.'),
            client_ip=client_ip,
            method=request.method.lower()
        )

        Metrology.meter('http.requests').mark()
        Metrology.meter('http.{method}.requests'.format(**v)).mark()
        Metrology.meter("http.{method}.{dotted_uri}.requests".format(**v)).mark()
        Metrology.meter("http.{method}.{dotted_uri}.{client_ip}.requests".format(**v)).mark()

        if (request.code >= 400):
            Metrology.meter("http.{method}.{dotted_uri}.{client_ip}.errors".format(**v)).mark()

        for _ in request._zaction['maps']:
            Metrology.meter("zenopenstack.{dotted_uri}.{client_ip}.datamaps".format(**v)).mark()

        for _ in request._zaction['events']:
            Metrology.meter("zenopenstack.{dotted_uri}.{client_ip}.events".format(**v)).mark()

        for _ in request._zaction['metrics']:
            Metrology.meter("zenopenstack.{dotted_uri}.{client_ip}.metrics".format(**v)).mark()

    def get_client_keys(self):
        """Return list of client IDs monitored."""
        return self.cache.keys()

    def get_metrology_keys(self):
        """Return list of Metrology IDs."""
        return metrology_registry.metrics.keys()

    def get_requests(self, client_id):
        """Return list of events for client_id."""
        if client_id in self.cache:
            return self.cache[client_id]
        return []

    def get_most_recent_request(self, client_id):
        if client_id in self.cache:
            if self.cache[client_id]:
                return self.cache[client_id][-1]
        return None


class Registry(object):
    # Holds all the configured devices, metrics, etc.  Used by the
    # web server to process incoming messages.

    def __init__(self):
        self.configs = {}
        self.component_id = {}
        self.resource_bytype = {}
        self.event_types = {}

    def all_devices(self):
        return self.configs.keys()

    def has_device(self, device_id):
        return device_id in self.configs

    def remove_device(self, device_id):
        if device_id in self.configs:
            del self.configs[device_id]
        if device_id in self.event_types:
            del self.event_types[device_id]

    def device_event_types(self, device_id):
        if device_id in self.event_types:
            return self.event_types[device_id]
        return []

    def set_config(self, device_id, cfg):
        # (list of OpenStackDataSourceConfig as returned by OpenStackConfig service)

        self.configs[device_id] = {}
        self.component_id[device_id] = {}
        self.resource_bytype[device_id] = defaultdict(set)
        self.event_types[device_id] = cfg.zOpenStackProcessEventTypes

        for datasource in cfg.datasources:
            self.configs.setdefault(device_id, {})
            self.configs[device_id].setdefault(datasource.resourceId, {})
            self.configs[device_id][datasource.resourceId][datasource.meter] = datasource.points
            self.component_id[device_id][datasource.resourceId] = datasource.component
            self.resource_bytype[device_id][datasource.component_meta_type].add(datasource.resourceId)

    def has_resource(self, device_id, resourceId):
        return resourceId in self.component_id.get(device_id, {})

    def get_component_id(self, device_id, resourceId):
        # Given a resource ID, return the corresponding component ID,
        # or None if it is unrecognized.
        return self.component_id.get(device_id, {}).get(resourceId)

    def device_resource_ids(self, device_id, meta_type):
        # Given a device and meta_type, return all monitored resource IDs.
        return self.resource_bytype.get(device_id, {}).get(meta_type, [])

    def get_datapoints(self, device_id, resourceId, metric_name):
        if device_id not in self.configs:
            return []
        return self.configs[device_id].get(resourceId, {}).get(metric_name, [])


REGISTRY = Registry()
METRIC_QUEUE = deque()
EVENT_QUEUE = deque()
MAP_QUEUE = defaultdict(ConsolidatingObjectMapQueue)
VNICS = defaultdict(lambda: dict(
    potential=dict(),
    modeled=set()
))


class Site(TwistedSite):
    request_buffer = None

    def __init__(self, resource, requestFactory=None, *args, **kwargs):
        preferences = zope.component.queryUtility(
            ICollectorPreferences, 'zenopenstack')

        self.request_buffer = HTTPDebugLogBuffer(preferences.options.httpdebugbuffersize)

        return TwistedSite.__init__(self, resource, requestFactory, *args, **kwargs)


class Resource(TwistedResource):
    site = None

    # give all resources access to the site that contains them
    def putChild(self, path, child):
        child.site = self.site
        return TwistedResource.putChild(self, path, child)

    def render(self, request):
        # For proxied requests, we have to override getClientIP to return
        # the proper IP address.
        if request.requestHeaders.hasHeader(b'x-forwarded-for'):
            client_ip = request.requestHeaders.getRawHeaders(
                b"x-forwarded-for", [b"-"])[0].split(b",")[0].strip()
            request.getClientIP = lambda: client_ip

        # Add a few properties to the request object that are used to
        # return additional information for the request_buffer debugging
        # tool
        request._zaction = {
            "metrics": [],
            "maps": [],
            "events": []
        }

        result = TwistedResource.render(self, request)

        # log any requests that generated error responses
        # this will only get us the code, but the detailed response bodies
        # will be in the /health logs.
        if request.code >= 400:
            timestamp = datetimeToLogString(reactor.seconds())
            log.error(combinedLogFormatter(timestamp, request))

        if not request.uri.startswith("/health"):
            self.site.request_buffer.store_request(request, result)

        return result


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


class Health(Resource):
    """ /health: expose health of zenopenstack daemon (metrics, logs) """

    isLeaf = True

    def render_GET(self, request):
        request.setResponseCode(200)
        request.setHeader(b"content-type", b"text/html")

        if len(request.postpath):
            if len(request.postpath) == 1 and request.postpath[0] == "metrics":
                body = "<html><body>"
                body += "<table border=\"1\">"
                body += "<tr>"
                body += "  <th>Metric</th>"
                body += "  <th>Count</th>"
                body += "  <th>1M Rate</th>"
                body += "  <th>5M Rate</th>"
                body += "  <th>15M Rate</th>"
                body += "  <th>Mean Rate</th>"
                body += "</tr>"

                for name, metric in sorted(metrology_registry):
                    if isinstance(metric, Meter):
                        body += "<tr>"
                        body += "  <td>%s</td>" % name
                        body += "  <td>%d</td>" % metric.count
                        body += "  <td>%f</td>" % metric.one_minute_rate
                        body += "  <td>%f</td>" % metric.five_minute_rate
                        body += "  <td>%f</td>" % metric.fifteen_minute_rate
                        body += "  <td>%f</td>" % metric.mean_rate
                        body += "</tr>"
                    else:
                        log.debug("Ignoring unhandled metric type: %s", metric)
                body += "</body></html>"
                return body

            if len(request.postpath) == 1 and request.postpath[0] == "queue":
                body = "<html><body>"
                body = "The following devices have received model updates:<ul>"
                for device_id in MAP_QUEUE:
                    body += '<li><a href="/health/queue/%s">%s</a></li>' % (device_id, device_id)
                body += "</ul></body></html>"
                return body

            if len(request.postpath) == 2 and request.postpath[0] == "queue":
                device_id = request.postpath[1]

                if device_id not in MAP_QUEUE:
                    return NoResource().render(request)

                body = "<html><body>"

                body += "<b>Currently-Held Object Maps</b><p>"
                for component_id, objmap in MAP_QUEUE[device_id].held_objmaps.iteritems():
                    body += "<hr>"
                    body += component_id + ":<br>"
                    body += "<pre>" + cgi.escape(pformat(objmap[1])) + "</pre>"

                body += "<b>Most Recently Released Object Maps</b>"
                for timestamp, objmap in reversed(MAP_QUEUE[device_id].released_objmaps):
                    body += "<hr>%s (%s ago)" % (
                        timestamp.isoformat(),
                        (datetime.datetime.now() - timestamp)
                    )
                    body += "<pre>" + cgi.escape(pformat(objmap)) + "</pre>"

                body += "</body></html>"
                return body

            if len(request.postpath) < 3 or request.postpath[0] != "logs":
                return NoResource().render(request)

            ip = request.postpath[1]
            uri = "/".join(request.postpath[2:])
            body = "<html><body>"
            records = self.site.request_buffer.get_requests((ip, '/' + uri))
            body += "<b>Most recent %d requests from /%s to %s</b> (of %d max)<p>" % (
                len(records),
                ip,
                uri,
                self.site.request_buffer.cache_size
            )

            for record in reversed(records):
                try:
                    request_body = record['request_body']
                    try:
                        # if the payload is JSON data, reindent it for readability
                        request_body = json.dumps(json.loads(request_body), indent=5)
                    except Exception:
                        pass
                    response_body = cgi.escape(record['response_body'])
                    zenoss_actions = cgi.escape(pformat(record['zenoss_actions']))

                    body += "<hr>%s (%s ago)" % (
                        record['timestamp'].isoformat(),
                        (datetime.datetime.now() - record['timestamp'])
                    )
                    body += '<table border="1" style="font-size: 80%"><tr><th>Request</th><th>Response</th><th>Zenoss Action</th></tr>'
                    body += "<tr valign=\"top\"><td><pre>" + request_body + "</pre></td>"
                    body += "<td><b>%d %s</b><pre>%s</pre></td>" % (
                        record['response_code'],
                        record['response_code_message'],
                        response_body)
                    body += "<td><pre>" + zenoss_actions + "</pre></td>"
                    body += "</tr></table>"
                except Exception, e:
                    body += "<hr>Error displaying log record: %s<hr>" % str(e)

            body += "</body></html>"
            return body

        body = """
<html>
  <body>
    <table border="1">
      <tr>
        <th rowspan="2">URI</th>
        <th rowspan="2">Client IP</th>
        <th colspan="3">POST</th>
        <th colspan="3">GET</th>
        <th colspan="3">POST Errors</th>
        <th colspan="3">GET Errors</th>
        <th colspan="3">Datamaps</th>
        <th colspan="3">Events</th>
        <th colspan="3">Metrics</th>
        <th rowspan="2">Last Request</th>
        <th rowspan="2">Details</th>
     </tr>
     <tr>
        <th>count</th>
        <th>15m</th>
        <th>mean</th>
        <th>count</th>
        <th>15m</th>
        <th>mean</th>
        <th>count</th>
        <th>15m</th>
        <th>mean</th>
        <th>count</th>
        <th>15m</th>
        <th>mean</th>
        <th>count</th>
        <th>15m</th>
        <th>mean</th>
        <th>count</th>
        <th>15m</th>
        <th>mean</th>
        <th>count</th>
        <th>15m</th>
        <th>mean</th>
     </tr>

        """

        for client_ip, uri in sorted(self.site.request_buffer.get_client_keys()):
            v = dict(
                dotted_uri=uri.replace('/', '.').strip('.'),
                client_ip=client_ip
            )

            posts = Metrology.meter("http.post.{dotted_uri}.{client_ip}.requests".format(**v))
            gets = Metrology.meter("http.get.{dotted_uri}.{client_ip}.requests".format(**v))
            post_errors = Metrology.meter("http.post.{dotted_uri}.{client_ip}.errors".format(**v))
            get_errors = Metrology.meter("http.get.{dotted_uri}.{client_ip}.errors".format(**v))
            datamaps = Metrology.meter("zenopenstack.{dotted_uri}.{client_ip}.datamaps".format(**v))
            events = Metrology.meter("zenopenstack.{dotted_uri}.{client_ip}.events".format(**v))
            metrics = Metrology.meter("zenopenstack.{dotted_uri}.{client_ip}.metrics".format(**v))

            most_recent_request = self.site.request_buffer.get_most_recent_request((client_ip, uri))

            body += "<tr>"
            body += "  <td>%s</td>" % uri
            body += "  <td>%s</td>" % client_ip
            body += "  <td>%d</td>" % posts.count
            body += "  <td>%.2f</td>" % posts.fifteen_minute_rate
            body += "  <td>%.2f</td>" % posts.mean_rate
            body += "  <td>%d</td>" % gets.count
            body += "  <td>%.2f</td>" % gets.fifteen_minute_rate
            body += "  <td>%.2f</td>" % gets.mean_rate
            body += "  <td>%d</td>" % post_errors.count
            body += "  <td>%.2f</td>" % post_errors.fifteen_minute_rate
            body += "  <td>%.2f</td>" % post_errors.mean_rate
            body += "  <td>%d</td>" % get_errors.count
            body += "  <td>%.2f</td>" % get_errors.fifteen_minute_rate
            body += "  <td>%.2f</td>" % get_errors.mean_rate
            body += "  <td>%d</td>" % datamaps.count
            body += "  <td>%.2f</td>" % datamaps.fifteen_minute_rate
            body += "  <td>%.2f</td>" % datamaps.mean_rate
            body += "  <td>%d</td>" % events.count
            body += "  <td>%.2f</td>" % events.fifteen_minute_rate
            body += "  <td>%.2f</td>" % events.mean_rate
            body += "  <td>%d</td>" % metrics.count
            body += "  <td>%.2f</td>" % metrics.fifteen_minute_rate
            body += "  <td>%.2f</td>" % metrics.mean_rate

            if most_recent_request:
                body += "  <td>%s ago (%d)</td>" % (
                    (datetime.datetime.now() - most_recent_request['timestamp']),
                    most_recent_request['response_code'])
            else:
                body += "  <td>None</td>"
            body += "  <td><a href=\"/health/logs/%s%s\">request log</a></td>" % (client_ip, uri)
            body += "</tr>"

        return body + """
    </table>

    <p><a href="/health/metrics">All Metrics</a></p>
    <p><a href="/health/queue">Model Update Queue</a></p>
  </body>
</html>
        """


class CeilometerRoot(Resource):
    """ /ceilometer """

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
    """ /ceilometer/v1 """
    pass


class CeilometerV1Samples(Resource):
    """ /ceilometer/v1/samples/<device id> : accept metrics from ceilometer """

    isLeaf = True
    future_warning = set()

    def render_POST(self, request):
        if len(request.postpath) != 1:
            return NoResource().render(request)

        device_id = request.postpath[0]

        if not REGISTRY.has_device(device_id):
            return NoResource(message="Unrecognized device '%s'" % device_id).render(request)

        content_type = request.requestHeaders.getRawHeaders('content-type', [None])[0]
        if content_type != 'application/json':
            return ErrorPage(415, "Unsupported Media Type", "Unsupported Media Type").render(request)
        try:
            payload = json.loads(request.content.getvalue())
        except Exception, e:
            log.error("Error [%s] while parsing JSON data: %s", e, request.content.getvalue())
            return ErrorPage(400, "Bad Request", "Error parsing JSON data: %s" % e).render(request)

        samples = []
        now = time.time()

        try:
            for sample in payload:
                if 'event_type' in sample and 'volume' not in sample:
                    return ErrorPage(422, "Unprocessable Entity", "Misconfigured- sending event data to metric URL").render(request)

                resourceId = sample['resource_id']
                meter = sample['name']
                value = sample['volume']
                timestamp = amqp_timestamp_to_int(sample['timestamp'])

                if timestamp > now:
                    if device_id not in self.future_warning:
                        log.debug("[%s/%s] Timestamp (%s) appears to be in the future.  Using now instead." % (
                            resourceId, meter, timestamp))
                        self.future_warning.add(device_id)
                    timestamp = now

                samples.append((resourceId, meter, value, timestamp))

        except Exception, e:
            log.exception("Error processing sample data")
            return ErrorPage(422, "Unprocessable Entity", "Error processing data: %s" % e).render(request)

        for resourceId, meter, value, timestamp in samples:
            datapoints = REGISTRY.get_datapoints(device_id, resourceId, meter)

            if datapoints:
                for dp in datapoints:
                    log.debug("Storing datapoint %s / %s value %d @ %d", device_id, dp.rrdPath, value, timestamp)
                    METRIC_QUEUE.append((dp, value, timestamp))
                    request._zaction['metrics'].append((device_id, dp.rrdPath, value, timestamp))

            else:
                log.debug("Ignoring unmonitored sample: %s / %s / %s", device_id, resourceId, meter)

            if meter.startswith("network") and not REGISTRY.has_resource(device_id, resourceId):
                # potentially, a new vnic.   Store the resource ID
                # so that we can investigate further in the VnicTask
                if resourceId not in VNICS[device_id]['potential']:
                    VNICS[device_id]['potential'][resourceId] = now

        # An empty response is fine.
        return b""


class CeilometerV1Events(Resource):
    """ /ceilometer/v1/events/<device id> : accept events from ceilomter """

    isLeaf = True

    def render_POST(self, request):

        if len(request.postpath) != 1:
            return NoResource().render(request)

        device_id = request.postpath[0]

        if not REGISTRY.has_device(device_id):
            return NoResource(message="Unrecognized device '%s'" % device_id).render(request)

        content_type = request.requestHeaders.getRawHeaders('content-type', [None])[0]
        if content_type != 'application/json':
            return ErrorPage(415, "Unsupported Media Type", "Unsupported Media Type").render(request)
        try:
            payload = json.loads(request.content.getvalue())
        except Exception, e:
            log.error("Error [%s] while parsing JSON data: %s", e, request.content.getvalue())
            return ErrorPage(400, "Bad Request", "Error parsing JSON data: %s" % e).render(request)

        for c_event in payload:
            if 'event_type' not in c_event:
                if 'name' in c_event and 'volume' in c_event:
                    return ErrorPage(422, "Unprocessable Entity", "Misconfigured- sending metric data to event URL").render(request)
                log.error("%s: Ignoring unrecognized event payload: %s" % (request.getClientIP(), c_event))
                continue

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

            # only pass on events that we actually have mappings for.
            if event_type in REGISTRY.device_event_types(device_id):
                log.debug("Propagated %s event", event_type)
                EVENT_QUEUE.append(evt)
                request._zaction['events'].append(evt)

            if event_is_mapped(evt):
                # Try to turn the event into an objmap.
                try:
                    objmap = map_event(evt)
                    if objmap:
                        log.debug("Mapped %s event to %s", event_type, objmap)
                        MAP_QUEUE[device_id].append(objmap)
                        request._zaction['maps'].append((device_id, objmap))
                except Exception:
                    log.exception("Unable to process event: %s", evt)

        # An empty response is fine.
        return b""


class WebServer(object):
    site = None
    initialized = False

    def initialize(self):
        if self.initialized:
            return

        preferences = zope.component.queryUtility(
            ICollectorPreferences, 'zenopenstack')

        port = preferences.options.listenport

        root = Root()
        self.site = Site(root)
        root.site = self.site

        health = Health()
        root.putChild('health', health)

        ceilometer_root = CeilometerRoot()
        root.putChild('ceilometer', ceilometer_root)

        ceilometer_v1 = CeilometerV1()
        ceilometer_v1samples = CeilometerV1Samples()
        ceilometer_v1events = CeilometerV1Events()

        ceilometer_root.putChild('v1', ceilometer_v1)
        ceilometer_v1.putChild('samples', ceilometer_v1samples)
        ceilometer_v1.putChild('events', ceilometer_v1events)

        log.info("Starting http listener on port %d", port)

        # Enable twisted logging
        loggerName = "zen.zenopenstack.twisted"
        logging.getLogger(loggerName).setLevel(logging.ERROR)
        self.logobserver = twisted_log.PythonLoggingObserver(
            loggerName=loggerName)
        self.logobserver.start()

        reactor.listenTCP(port, self.site)

        self.initialized = True


class OpenStackCollectorDaemon(CollectorDaemon):
    initialServices = CollectorDaemon.initialServices + ['ModelerService']

    def _updateConfig(self, cfg):
        configId = cfg.configId
        self.log.debug("Processing configuration for %s", configId)

        REGISTRY.set_config(configId, cfg)

        # update queue settings
        MAP_QUEUE[configId].shortlived_seconds = cfg.zOpenStackIncrementalShortLivedSeconds
        MAP_QUEUE[configId].delete_blacklist_seconds = cfg.zOpenStackIncrementalBlackListSeconds
        MAP_QUEUE[configId].update_consolidate_seconds = cfg.zOpenStackIncrementalConsolidateSeconds

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

    def sighandler_USR1(self, signum, frame):
        super(OpenStackCollectorDaemon, self).sighandler_USR1(signum, frame)

        loggerName = "zen.zenopenstack.twisted"
        twisted_log = logging.getLogger(loggerName)
        if twisted_log.getEffectiveLevel() == logging.DEBUG:
            twisted_log.setLevel(logging.ERROR)
        else:
            twisted_log.setLevel(logging.DEBUG)

    def _displayStatistics(self, verbose=False):

        if hasattr(self, 'metricWriter') and self.metricWriter():
            self.log.info("%d devices processed (%d datapoints)",
                          len(REGISTRY.all_devices()), self.metricWriter().dataPoints)
        elif hasattr(self, '_rrd') and self._rrd:
            self.log.info("%d devices processed (%d datapoints)",
                          len(REGISTRY.all_devices()), self._rrd.dataPoints)
        else:
            self.log.info("%d devices processed (0 datapoints)",
                          len(REGISTRY.all_devices()))

        self._scheduler.displayStatistics(verbose)


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

    @defer.inlineCallbacks
    def doTask(self):
        if len(EVENT_QUEUE):
            log.debug("Draining event queue")
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
        if len(METRIC_QUEUE):
            log.debug("Draining metric queue")
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

        maps = {}
        for device_id, queue in MAP_QUEUE.iteritems():
            for datamap in queue.drain():
                maps.setdefault(device_id, [])
                maps[device_id].append(datamap)

        obsolete_devices = set(MAP_QUEUE.keys()) - set(REGISTRY.all_devices())
        for device_id in obsolete_devices:
            log.info("Removing datamap queue for deleted device %s", device_id)
            del MAP_QUEUE[device_id]

        if maps:
            log.debug("Draining datamap queue")
            self.state = 'SEND_DATAMAPS'
            remoteProxy = self._collector.getServiceNow('ModelerService')

            for device_id in maps:
                yield remoteProxy.callRemote(
                    'applyDataMaps', device_id, maps[device_id])

            self.state = TaskStates.STATE_IDLE


class OpenStackVnicTask(BaseTask):
    zope.interface.implements(IScheduledTask)

    def __init__(self, taskName, configId, scheduleIntervalSeconds=60, taskConfig=None):
        super(OpenStackVnicTask, self).__init__(
            taskName, configId, scheduleIntervalSeconds, taskConfig)

        self.name = taskName
        self.configId = configId
        self.state = TaskStates.STATE_IDLE
        self.interval = scheduleIntervalSeconds

    @defer.inlineCallbacks
    def doTask(self):
        # Periodically look for new vnics, and if found, build ObjectMaps
        # for them, which will be picked up by the map task.

        now = time.time()
        i = 0
        for device_id, vnics in VNICS.iteritems():
            if not vnics['potential']:
                continue

            for resourceId, first_seen in vnics['potential'].iteritems():
                # We only attempt to model a vnic for 20 minutes, then give up.
                # this is to allow time for a new instance to be modeled, but
                # also to save processing time, because for every potential
                # vnic, we need to loop over every possible instance.
                # 20 minutes lets us try this many times, and if it
                # isn't working by then, it presumably never will.
                if now - first_seen > 20 * 60:
                    continue

                # We only ever model each vnic once.
                if resourceId in vnics['modeled']:
                    continue

                # Loop over every known instance to see if it is the parent
                # of this potential vnic.
                for instanceUUID in REGISTRY.device_resource_ids(device_id, 'OpenStackInfrastructureInstance'):
                    # give time back to the reactor occasionally
                    i += 1
                    if i % 500:
                        yield task.deferLater(reactor, 0, lambda: None)

                    # Vnic resourceIds are of the form:
                    #  [instanceName]-[instanceUUID]-[vnicName]
                    #  instance-00000001-95223d22-d3af-4b06-a91c-81114d557bd1-tap908bc571-0d

                    log.debug("Searching for instance %s in %s" % (instanceUUID, resourceId))
                    match = re.search("-%s-(.*)$" % instanceUUID, resourceId)
                    if match:
                        vnicName = match.group(1)
                        instance_id = REGISTRY.get_component_id(device_id, instanceUUID)
                        vnic_id = prepId(str('vnic-%s-%s' % (instanceUUID, vnicName)))

                        log.info("Discovered new vNIC (%s) on instance %s", vnic_id, instance_id)
                        vnics['modeled'].add(resourceId)

                        MAP_QUEUE[device_id].append(ObjectMap({
                            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Vnic',
                            'id': vnic_id,
                            'compname': 'components/%s' % instance_id,
                            'relname': 'vnics',
                            'title': vnicName,
                            'resourceId': resourceId
                        }))
                    break

                if resourceId in vnics['modeled']:
                    continue


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

        parser.add_option(
            '--httpdebugbuffersize',
            dest='httpdebugbuffersize',
            type='int',
            default=100,
            help="Size of HTTP request debug log buffer")

    def postStartup(self):
        pass

    def postStartupTasks(self):

        # We run one task for each type of processing- each consumes and sends
        # on data from a corresponding queue.
        yield OpenStackPerfTask('zenopenstack-perf', configId='zenopenstack-perf', scheduleIntervalSeconds=60)
        yield OpenStackEventTask('zenopenstack-event', configId='zenopenstack-event', scheduleIntervalSeconds=60)
        yield OpenStackMapTask('zenopenstack-map', configId='zenopenstack-map', scheduleIntervalSeconds=60)
        yield OpenStackVnicTask('zenopenstack-vnic', configId='zenopenstack-vnic', scheduleIntervalSeconds=60)


def get_manhole_port(base_port_number):
    """
    Returns an unused port number by starting with base_port_number
    and incrementing until an unbound port is found.
    """

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    port_number = base_port_number
    while True:
        try:
            s.bind(('', port_number))
        except socket.error:
            port_number += 1
            continue

        return port_number


def main():
    preferences = Preferences()
    task_splitter = TaskSplitter()
    webserver = WebServer()

    collectordaemon = OpenStackCollectorDaemon(
        preferences,
        task_splitter,
        initializationCallback=webserver.initialize)

    port = get_manhole_port(7777)
    log.debug("Starting manhole on port %d", port)

    f = twisted.manhole.telnet.ShellFactory()
    f.username, f.password = ('zenoss', 'zenoss')
    reactor.listenTCP(port, f)
    f.namespace.update(
        preferences=preferences,
        webserver=webserver,
        collectordaemon=collectordaemon,
        REGISTRY=REGISTRY,
        METRIC_QUEUE=METRIC_QUEUE,
        EVENT_QUEUE=EVENT_QUEUE,
        MAP_QUEUE=MAP_QUEUE,
        VNICS=VNICS
    )
    collectordaemon.run()


if __name__ == '__main__':
    main()
