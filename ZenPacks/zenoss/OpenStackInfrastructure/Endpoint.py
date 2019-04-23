##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013-2019, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


from . import schema

import json
import logging
LOG = logging.getLogger('zen.OpenStackInfrastructureEndpoint')

from Products.Zuul import getFacade
from zope.component import getUtility
from zenoss.protocols.queueschema import substitute_replacements
from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema
from zenoss.protocols.amqp import Publisher as BlockingPublisher
from zenoss.protocols.protobufs.zep_pb2 import (
    STATUS_NEW, STATUS_ACKNOWLEDGED, SEVERITY_CRITICAL)
from amqplib.client_0_8.exceptions import AMQPChannelException
from OFS.interfaces import IObjectWillBeAddedEvent
from BTrees.OOBTree import OOBTree
from ZenPacks.zenoss.OpenStackInfrastructure.utils import addVirtualRoot


class Endpoint(schema.Endpoint):

    neutron_ini = {}
    host_mappings = {}

    def hosts(self):
        return self.getDeviceComponents(type="OpenStackInfrastructureHost")

    def region(self):
        return self.getDeviceComponents(type="OpenStackInfrastructureRegion")[0]

    def get_maintain_proxydevices(self):
        from ZenPacks.zenoss.OpenStackInfrastructure.DeviceProxyComponent \
            import DeviceProxyComponent
        for meta_type in DeviceProxyComponent.deviceproxy_meta_types():
            for component in self.getDeviceComponents(type=meta_type):
                if component.need_maintenance():
                    return False

        return True

    def set_maintain_proxydevices(self, arg):
        from ZenPacks.zenoss.OpenStackInfrastructure.DeviceProxyComponent \
            import DeviceProxyComponent
        for meta_type in DeviceProxyComponent.deviceproxy_meta_types():
            for component in self.getDeviceComponents(type=meta_type):
                component.maintain_proxy_device()

        return True

    def get_ensure_service_monitoring(self):
        return False

    def set_ensure_service_monitoring(self, arg):
        for host in self.getDeviceComponents(type="OpenStackInfrastructureHost"):
            host.ensure_service_monitoring()
        return True

    def set_host_mappings(self, values):
        if type(self.host_mappings) == dict:
            self.host_mappings = OOBTree()
        for k, v in values.iteritems():
            if k not in self.host_mappings or self.host_mappings[k] != v:
                LOG.debug("Updating host mapping: %s -> %s", k, v)
                self.host_mappings[k] = v

    def get_host_mappings(self):
        return dict(self.host_mappings)

    def set_neutron_ini(self, values):
        if type(self.neutron_ini) == dict:
            self.neutron_ini = OOBTree()

        changed = set()
        for k, v in values.iteritems():
            if k not in self.neutron_ini or self.neutron_ini[k] != v:
                self.neutron_ini[k] = v
                changed.add(k)

        if changed:
            LOG.info("The following INI values have changed: %s" % changed)
            LOG.info("Rebuilding neutron core integration keys.")
            from ZenPacks.zenoss.OpenStackInfrastructure.neutron_integration \
                import reindex_core_components
            reindex_core_components(self.dmd)

    def get_neutron_ini(self):
        return dict(self.neutron_ini)

    def ini_get(self, *args):
        return self.neutron_ini.get(*args)

    def health(self):
        """Dump out a health report for this endpoint"""

        return "Host Mappings:\n\n" + \
               "Settings:\n" + \
               "    zOpenStackNovaApiHosts=%s\n" % self.zOpenStackNovaApiHosts + \
               "    zOpenStackCinderApiHosts=%s\n" % self.zOpenStackCinderApiHosts + \
               "    zOpenStackExtraHosts=%s\n" % self.zOpenStackExtraHosts + \
               "    zOpenStackHostMapToId=%s\n" % self.zOpenStackHostMapToId + \
               "    zOpenStackHostMapSame=%s\n" % self.zOpenStackHostMapSame + \
               "\n" + \
               "Mappings=" + \
               json.dumps(self.get_host_mappings(), indent=4)

    def getStatus(self, statusclass=None, **kwargs):
        """Return status number for this device.

        The status number is the number of critical events associated
        with this device. This includes only events tagger with the
        device's UUID, and not events affecting components of the
        device.

        None is returned when the device's status is unknown because it
        isn't being monitored, or because there was an error retrieving
        its events.

        By default any critical severity event that is in either the new or
        acknowledged state in the event class that set in zStatusEventClass
        (if we don't have this property, use /Status class instead)
        property and is tagged with the device's UUID indicates that the
        device is down. An alternate event class (statusclass) can be
        provided, which is what would be done by the device's
        getPingStatus and getSnmpStatus methods.

        """
        if not self.monitorDevice():
            return None

        if statusclass is None:
            statusclass = getattr(self, 'zStatusEventClass', '/Status')

        zep = getFacade("zep", self.dmd)
        try:
            event_filter = zep.createEventFilter(
                tags=[self.getUUID()],
                element_sub_identifier=[""],
                severity=[SEVERITY_CRITICAL],
                status=[STATUS_NEW, STATUS_ACKNOWLEDGED],
                event_class=filter(None, [statusclass]))

            result = zep.getEventSummaries(0, filter=event_filter, limit=0)
        except Exception:
            return None

        return int(result['total'])

    def public_keystone_apiendpoint(self):
        # Return the public keystone API endpoint (from zOpenStackAuthUrl)
        try:
            return self.components._getOb('apiendpoint-zOpenStackAuthUrl')
        except AttributeError:
            return None

    def zenopenstack_url(self, https=False):
        try:
            from Products.ZenUtils.controlplane.application import getConnectionSettings
            from Products.ZenUtils.controlplane import ControlPlaneClient
        except ImportError:
            return

        if https:
            protocol = "https"
            endpoint_name = "proxy-zenopenstack_https"
        else:
            protocol = "http"
            endpoint_name = "proxy-zenopenstack_http"

        collector = self.perfServer().id
        client = ControlPlaneClient(**getConnectionSettings())
        for svc_id in [x.id for x in client.queryServices() if x.name == 'proxy-zenopenstack']:
            svc = client.getService(svc_id)
            for endpoint in filter(lambda s: s['Name'] == endpoint_name, svc.getRawData()['Endpoints']):
                try:
                    if endpoint['AddressAssignment']['IPAddr'] is None or endpoint['AddressAssignment']['IPAddr'] == "":
                        continue

                    if endpoint['AddressAssignment']['Port'] is None or int(endpoint['AddressAssignment']['Port']) == 0:
                        continue

                    if client.getService(svc.parentId).name == collector:
                        return "{protocol}://{ip}:{port}".format(
                            protocol=protocol,
                            ip=endpoint['AddressAssignment']['IPAddr'],
                            port=endpoint['AddressAssignment']['Port'])
                except Exception:
                    # no ip assignment or error determining what collector this is.
                    pass

    def ceilometer_url_samples(self):
        zenopenstack_url = self.zenopenstack_url(https=True)
        if zenopenstack_url:
            return "%s/ceilometer/v1/samples/%s?verify_ssl=False" % (
                zenopenstack_url,
                self.id
            )
        else:
            return "n/a"

    def ceilometer_url_events(self):
        zenopenstack_url = self.zenopenstack_url(https=True)
        if zenopenstack_url:
            return "%s/ceilometer/v1/events/%s?verify_ssl=False" % (
                zenopenstack_url,
                self.id
            )
        else:
            return "n/a"


def onDeviceDeleted(object, event):
    # Clean up any AMQP queues we may have created for this device.

    if not IObjectWillBeAddedEvent.providedBy(event):
        connectionInfo = getUtility(IAMQPConnectionInfo)
        queueSchema = getUtility(IQueueSchema)

        # For some reason, if an error gets thrown by queue_delete, it seems
        # to break the connection, so we'll just use a separate connection
        # for each call to it.
        for queue in ('$OpenStackInboundEvent', '$OpenStackInboundPerf'):
            queueName = substitute_replacements(queueSchema._queue_nodes[queue].name,
                                                {'device': object.id})

            amqpClient = BlockingPublisher(connectionInfo, queueSchema)
            channel = amqpClient.getChannel()
            try:
                LOG.debug("Removing AMQP queue %s" % queueName)
                channel.queue_delete(queueName)
                LOG.info("Removed AMQP queue %s successfully." % queueName)
            except AMQPChannelException, e:
                # if the queue doesn't exist, don't worry about it.
                if e.amqp_reply_code == 404:
                    LOG.debug('Queue %s did not exist', queueName)
                else:
                    LOG.exception(e)

            amqpClient.close()


class DeviceLinkProvider(object):
    '''
Provides a link on the openstack device overview page to its zenopenstack
collector daemon's "health" diagnostic page.
'''
    def __init__(self, device):
        self._device = device

    def getExpandedLinks(self):
        links = []

        url = self._device.zenopenstack_url()
        if url:
            links.append('<a href="%s/health">zenopenstack diagnostics</a>' % url)

        url = addVirtualRoot(self._device.getPrimaryUrlPath())
        links.append('<a href="%s/health">modeling diagnostics</a>' % url)

        return links
