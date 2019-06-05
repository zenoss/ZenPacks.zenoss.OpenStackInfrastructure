##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013-2018, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


from . import schema

import logging
LOG = logging.getLogger('zen.OpenStackDeviceProxyComponent')

from zope.event import notify
from zope.interface import implements

from OFS.interfaces import IObjectWillBeAddedEvent, IObjectWillBeMovedEvent
from Products.Zuul.catalog.events import IndexingEvent
from Products.ZenEvents.interfaces import IPostEventPlugin
from Products.ZenModel.Exceptions import DeviceExistsError
from Products.ZenUtils.guid.interfaces import IGlobalIdentifier
from Products.ZenUtils.guid.guid import GUIDManager
from Products.ZenUtils.Utils import monkeypatch
from Products.Zuul.interfaces import ICatalogTool
from Products.AdvancedQuery import Eq, And, Or, In, MatchGlob
from Products.DataCollector.ApplyDataMap import ApplyDataMap
from Products.ZenUtils.IpUtil import getHostByName, IpAddressError
import socket


def onDeviceDeleted(object, event):
    '''
    Clean up the dangling reference to a device if that device has been removed.
    (Note: we may re-create the device automatically next time someone calls
    self.ensure_proxy_device, though)
    '''
    if not IObjectWillBeAddedEvent.providedBy(event) and not IObjectWillBeMovedEvent.providedBy(event):
        if hasattr(object, 'openstackProxyComponentUUID'):
            component = GUIDManager(object.dmd).getObject(getattr(object, 'openstackProxyComponentUUID', None))
            if component:
                component.release_proxy_device()
            object.openstackProxyComponentUUID = None


def onDeviceProxyComponentDeleted(object, event):
    '''
    Clean up the dangling reference from a device if the component has been removed.
    '''
    if not IObjectWillBeAddedEvent.providedBy(event):
        object.release_proxy_device()


class DeviceProxyComponent(schema.DeviceProxyComponent):

    @classmethod
    def deviceproxy_meta_types(cls):
        return [x.meta_type for x in DeviceProxyComponent.__subclasses__()]

    @classmethod
    def component_for_proxy_device(cls, device):
        '''
        Given any device in the system, check if it has a DeviceProxyComponent
        associated with it, and if it does, return that component.
        '''

        uuid = getattr(device, 'openstackProxyComponentUUID', None)
        if uuid:
            component = GUIDManager(device.dmd).getObject(uuid)

            # ensure that the component is also linked back to this device-
            # a uni-directional linkage (device to component, but not 
            # component to device) is not valid.
            component_device_uuid = getattr(component, 'openstackProxyDeviceUUID', None)
            if component_device_uuid == IGlobalIdentifier(device).getGUID():
                return component
            else:                
                LOG.warning("Device %s is linked to component %s, but it is not linked back.  Disregarding linkage.",
                            device, component)
        return None

    def proxy_deviceclass_zproperty(self):
        '''
        Return the name of the zProperty that contains the proxy device
        class name.

        Default is 'z<meta type>DeviceClass'
        '''
        return 'z' + self.meta_type + 'DeviceClass'

    def proxy_deviceclass(self):
        '''
        Return the device class object identified by
        proxy_deviceclass_zproperty, creating it if necessary.
        '''
        if self.proxy_deviceclass_zproperty() is None:
            raise ValueError("proxy_deviceclass_zproperty is not defined for %s" % self.meta_type)

        dcpath = self.getZ(self.proxy_deviceclass_zproperty())
        if dcpath is None or "/" not in dcpath:
            raise ValueError("%s (%s) is invalid" % (self.proxy_deviceclass_zproperty(), dcpath))

        try:
            return self.dmd.Devices.getOrganizer(dcpath)
        except Exception:
            LOG.info("Creating DeviceClass %s" % dcpath)
            return self.dmd.Devices.createOrganizer(dcpath)

    def need_maintenance(self):
        guid = IGlobalIdentifier(self).getGUID()
        device = GUIDManager(self.dmd).getObject(getattr(self, 'openstackProxyDeviceUUID', None))
        if device and getattr(device, 'openstackProxyComponentUUID', None) \
                and device.openstackProxyComponentUUID == guid:
            return False
        return True

    def maintain_proxy_device(self):
        '''
        Ensure that the proxy device exists, creating it if necessary.
        '''
        if not self.proxy_device():
            self.create_proxy_device()

            return True

    def claim_proxy_device(self, device):
        LOG.debug("%s component '%s' is now linked to device '%s'" % (self.meta_type, self.name(), device.name()))
        device.openstackProxyComponentUUID = IGlobalIdentifier(self).getGUID()
        self.openstackProxyDeviceUUID = IGlobalIdentifier(device).getGUID()

    def ensure_valid_claim(self, device):
        component_guid = IGlobalIdentifier(self).getGUID()
        device_guid = IGlobalIdentifier(device).getGUID()
        valid = True

        # Confirm forward linkage
        if getattr(self, 'openstackProxyDeviceUUID', None) != device_guid:
            valid = False

        # Confirm reverse linkage
        if getattr(device, 'openstackProxyComponentUUID', None) != component_guid:
            valid = False

        if not valid:
            # the linkage is broken in at least one direction.  Just re-claim
            # it to set it right.
            LOG.info("%s component '%s' linkage to device '%s' is broken. "
                     "Re-claiming it.",
                     self.meta_type, self.name(), device.name())
            self.claim_proxy_device(device)
        return device

    def find_claimable_device(self, device_class=None):
        '''
        Find a possible Linux device for the host:

        Search by id, title, and management IP, against id, hostnames, and IPs
        '''

        if device_class is None:
            device_class = self.proxy_deviceclass()

        suggested_name = self.suggested_device_name()

        search_values = [x for x in self.id, suggested_name, self.hostname, self.host_ip if x is not None]
        brains = device_class.deviceSearch.evalAdvancedQuery(
            And(
                MatchGlob('getDeviceClassPath', device_class.getOrganizerName() + "*"),
                Or(In('id', search_values),
                   In('titleOrId', search_values),
                   In('getDeviceIp', search_values))))

        possible_devices = []
        for brain in brains:
            try:
                device = brain.getObject()

                if device.openstack_hostComponent() is None:
                    if hasattr(device, 'getIpRealm'):
                        if self.getIpRealm() is device.getIpRealm():
                            possible_devices.append(device)
                    else:
                        possible_devices.append(device)
                else:
                    LOG.info("%s component %s unable to claim device %s, because it is already linked to %s",
                             self.meta_type, self.name(), device.id, device.openstack_hostComponent().id)
            except Exception:
                pass

        # 1. First look by matching id against my id/suggested_name/hostname
        for device in possible_devices:
            if device.id == self.id:
                return device

        for device in possible_devices:
            if device.id == suggested_name or device.id == self.hostname:
                return device

        # 2. Next find by matching name against my id/suggested_name/hostname
        for device in possible_devices:
            if device.name() == self.id:
                return device

        for device in possible_devices:
            if device.name() == suggested_name or device.name() == self.hostname:
                return device

        # Otherwise, return the first device, if one was found
        if possible_devices:
            return possible_devices[0]

        if device_class == self.proxy_deviceclass():
            # check for other devices that we would have claimed, if they
            # had been in the right device class
            device = self.find_claimable_device(device_class=self.dmd.Devices)
            if device:
                LOG.debug(
                    "No claimable device found for %s, but %s was found "
                    "in another device class.  Moving it to %s will make "
                    "it eligible.", self.id, device.id, self.proxy_deviceclass().getOrganizerName())

        # No claimable device was found.
        return None

    def proxy_device(self):
        '''
        Return this component's corresponding proxy device, or None if
        there isn't one at this time.   This method will not attempt to
        create a new device.
        '''

        # A claimed device already exists.
        device = GUIDManager(self.dmd).getObject(getattr(self, 'openstackProxyDeviceUUID', None))
        if device:
            # Make sure that the GUID is correct in the reverse direction,
            # then return it.
            return self.ensure_valid_claim(device)

        # Look for device that matches our requirements
        device = self.find_claimable_device()

        # Claim it.
        if device:
            self.claim_proxy_device(device)
            return device

        # We found nothing to claim, so return None.
        return None

    def suggested_device_name(self):
        return self.name()

    def suggested_host_ip(self):
        return getHostByName(self.suggested_device_name())

    def create_proxy_device(self):
        '''
        Create a proxy device in the proxy_deviceclass.

        Returns created device, or None if unable to create the device
        (due to ID conflict, etc)
        '''

        device_name = self.suggested_device_name()

        LOG.info('Adding device for %s %s' % (self.meta_type, self.title))
        try:
            device = self.proxy_deviceclass().createInstance(device_name)
            device.setProdState(self.productionState)
            device.setPerformanceMonitor(self.getPerformanceServer().id)
        except DeviceExistsError:
            LOG.info("Unable to create linux device (%s) because a device with that ID already exists.",
                     device_name)
            return None
        except Exception as ex:
            # Device creation fails for other reasons.
            LOG.warning("Error creating device (%s): %s",
                        device_name, ex)
            return None

        # A new device now exists.
        # We should only model the device if we've added it as a new device and
        # if it has a valid management IP (see below)
        should_model = False

        # Set the new device IP if possible.
        try:
            ip = self.suggested_host_ip()
            if ip is None:
                LOG.info("%s does not resolve- not setting manageIp", device_name)
            elif ip.startswith("127") or ip.startswith("::1"):
                LOG.info("%s resolves to a loopback address- not setting manageIp", device_name)
            else:
                device.setManageIp(ip)
                should_model = True

        except (IpAddressError, socket.gaierror):
            LOG.warning("Unable to set management IP based on %s", device_name)

        device.index_object()
        notify(IndexingEvent(device))

        if should_model:
            LOG.info('Scheduling modeling job for %s' % device_name)
            device.collectDevice(setlog=False, background=True)

        self.claim_proxy_device(device)

        return device

    def release_proxy_device(self):
        device = GUIDManager(self.dmd).getObject(getattr(self, 'openstackProxyDeviceUUID', None))
        if device:
            LOG.debug("device %s is now detached from %s component '%s'" % (device.name(), self.meta_type, self.name()))
            device.openstackProxyComponentUUID = None

        self.openstackProxyDeviceUUID = None
        LOG.debug("%s component '%s' is now detached from any devices" % (self.meta_type, self.name()))

    def devicelink_descr(self):
        '''
        The description to put on the proxy device's expanded links section when
        linking back to this component.
        '''
        return '"%s "%s" at %s' % (
            self.meta_type,
            self.name(),
            self.device().name()
        )

    def getDefaultGraphDefs(self, drange=None):
        """
        Return graph definitions for this component along with all graphs
        from the associated device.
        """
        graphs = super(DeviceProxyComponent, self).getDefaultGraphDefs(drange=drange)
        device = self.proxy_device()
        if device:
            for device_graph in device.getDefaultGraphDefs(drange):
                graphs.append(device_graph)

        return graphs

    def getGraphObjects(self, drange=None):
        """
        Return graph definitions for this software comoponent, along with
        any graphs from the associated OSProcess component.
        This method is for 5.x compatibility
        """
        graphs = super(DeviceProxyComponent, self).getGraphObjects()
        device = self.proxy_device()
        if device:
            graphs.extend(device.getGraphObjects())
        return graphs


class DeviceLinkProvider(object):
    '''
    Provides a link on the device overview page to the openstack component the
    device is a representation of.
    '''
    def __init__(self, device):
        self._device = device

    def getExpandedLinks(self):
        proxycomponent = DeviceProxyComponent.component_for_proxy_device(self._device)
        if proxycomponent:
            return ['<a href="%s">%s</a>' % (
                proxycomponent.getPrimaryUrlPath(),
                proxycomponent.devicelink_descr()
            )]

        return []


@monkeypatch('Products.ZenModel.Device.Device')
def getApplyDataMapToProxyComponent(self):
    return []


@monkeypatch('Products.ZenModel.Device.Device')
def setApplyDataMapToProxyComponent(self, datamap):
    mapper = ApplyDataMap()

    component = DeviceProxyComponent.component_for_proxy_device(self)
    if not component:
        LOG.error("Unable to apply datamap to proxy component for %s (component not found)" % self)
    else:
        mapper._applyDataMap(component, datamap)


class PostEventPlugin(object):
    """
    Post-event plugin to mirror events from a proxy device onto its
    deviceproxycomponent.
    """
    implements(IPostEventPlugin)

    def apply(self, eventProxy, dmd):

        # See ZPS-1677 for explanation.  This workaround will hopefully be
        # removed in the future (ZPS-1685)
        if eventProxy.eventClass == '/Status/Ping':
            return

        device = dmd.Devices.findDeviceByIdExact(eventProxy.device)

        if device and hasattr(device, 'openstackProxyComponentUUID'):
            LOG.debug("tagging event on %s with openstack proxy component component uuid %s",
                      eventProxy.device, device.openstackProxyComponentUUID)

            tags = []

            try:
                component = GUIDManager(dmd).getObject(device.openstackProxyComponentUUID)
                if component:

                    # Tag the event with the corresponding openstack component.
                    tags.append(device.openstackProxyComponentUUID)

                    # Also tag it with the openstack endpoint that the
                    # component is part of, if possible.
                    endpoint = component.device()
                    tags.append(IGlobalIdentifier(endpoint).getGUID())
            except Exception:
                LOG.debug("Unable to determine endpoint for proxy component uuid %s",
                          device.openstackProxyComponentUUID)

            # Get OSProcess component, if the event has one
            if eventProxy.component:
                for brain in ICatalogTool(dmd).search('Products.ZenModel.OSProcess.OSProcess', query=Eq('id', eventProxy.component)):
                    try:
                        osprocess = brain.getObject()
                    except Exception:
                        # ignore a stale entry
                        pass
                    else:
                        # Figure out if we have a corresponding software component:
                        try:
                            for software in component.hostedSoftware():
                                if software.binary == osprocess.osProcessClass().id:
                                    # Matches!
                                    tags.append(IGlobalIdentifier(software).getGUID())
                        except Exception:
                            LOG.debug("Unable to append event for OSProcess %s",
                                      osprocess.osProcessClass().id)

            if tags:
                eventProxy.tags.addAll('ZenPacks.zenoss.OpenStackInfrastructure.DeviceProxyComponent', tags)
