##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013-2014, all rights reserved.
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

from ZODB.transact import transact
from OFS.interfaces import IObjectWillBeAddedEvent
from Products.Zuul.catalog.events import IndexingEvent
from Products.ZenEvents.interfaces import IPostEventPlugin
from Products.ZenUtils.guid.interfaces import IGlobalIdentifier
from Products.ZenUtils.guid.guid import GUIDManager
from Products.Zuul.interfaces import ICatalogTool
from Products.AdvancedQuery import Eq


def onDeviceDeleted(object, event):
    '''
    Clean up the dangling reference to a device if that device has been removed.
    (Note: we may re-create the device automatically next time someone tries to access
    self.proxy_device, though)
    '''
    if not IObjectWillBeAddedEvent.providedBy(event):
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
            return GUIDManager(device.dmd).getObject(uuid)

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

    def maintain_proxy_device(self):
        '''
        Ensure that the proxy device exists, creating it if necessary.
        '''    
        self.proxy_device()

        return True

    def proxy_device(self):
        '''
        Return this component's corresponding proxy device, creating
        it in the proxy_deviceclass if it does not exist.

        Default assumes that the names must match.
        '''

        device = GUIDManager(self.dmd).getObject(getattr(self, 'openstackProxyDeviceUUID', None))
        if device:
            guid = IGlobalIdentifier(self).getGUID()

            # this shouldn't happen, but if we've somehow become half-connected
            # (we know about the device, it doesn't know about us), reconnect.
            if device.openstackProxyComponentUUID != guid:
                LOG.info("%s component '%s' linkage to device '%s' is broken.  Re-claiming it." % (self.meta_type, self.name(), device.name()))
                self.claim_proxy_device(device)

            return device

        # Does a device with a matching name exist?  Claim that one.
        device = self.dmd.Devices.findDevice(self.name())
        if device:
            self.claim_proxy_device(device)
            return device
        else:
            return self.create_proxy_device()

    @transact
    def create_proxy_device(self):
        '''
        Create a proxy device in the proxy_deviceclass.

        Default assumes that the names will match.
        '''

        # add the missing proxy device.
        device_name = self.name()

        LOG.info('Adding device for %s %s' % (self.meta_type, self.title))

        device = self.proxy_deviceclass().createInstance(device_name)
        device.setProdState(self.productionState)
        device.setPerformanceMonitor(self.getPerformanceServer().id)

        device.index_object()
        notify(IndexingEvent(device))

        LOG.info('Scheduling modeling job for %s' % device_name)
        device.collectDevice(setlog=False, background=True)

        self.claim_proxy_device(device)

        return device

    def claim_proxy_device(self, device):
        LOG.info("%s component '%s' is now linked to device '%s'" % (self.meta_type, self.name(), device.name()))
        device.openstackProxyComponentUUID = IGlobalIdentifier(self).getGUID()
        self.openstackProxyDeviceUUID = IGlobalIdentifier(device).getGUID()

    def release_proxy_device(self):
        device = GUIDManager(self.dmd).getObject(getattr(self, 'openstackProxyDeviceUUID', None))
        if device:
            LOG.info("device %s is now detached from %s component '%s'" % (device.name(), self.meta_type, self.name()))
            device.openstackProxyComponentUUID = None

        self.openstackProxyDeviceUUID = None
        LOG.info("%s component '%s' is now detached from any devices" % (self.meta_type, self.name()))

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


class PostEventPlugin(object):
    """ 
    Post-event plugin to mirror events from a proxy device onto its
    deviceproxycomponent.
    """
    implements(IPostEventPlugin)

    def apply(self, eventProxy, dmd):
        device = dmd.Devices.findDeviceByIdExact(eventProxy.device)

        if device and hasattr(device, 'openstackProxyComponentUUID'):
            LOG.debug("tagging event on %s with openstack proxy component component uuid %s",
                      eventProxy.device, device.openstackProxyComponentUUID)
            
            tags = [device.openstackProxyComponentUUID]

            # Also tag it with the openstack endpoint that the component is part of,
            # if possible.
            try:
                component = GUIDManager(dmd).getObject(device.openstackProxyComponentUUID)
                if component:
                    endpoint = component.device()
                    tags.append(IGlobalIdentifier(endpoint).getGUID())
            except Exception:
                LOG.debug("Unable to determine endpoint for proxy component uuid %s",
                          device.openstackProxyComponentUUID)

            # Get OSProcess component, if the event has one
            for brain in ICatalogTool(dmd).search('Products.ZenModel.OSProcess.OSProcess', query=Eq('id', eventProxy.component)):
                osprocess = brain.getObject()

                # Figure out if we have a corresponding software component:
                try:
                    for software in component.hostedSoftware():
                        if software.binary == osprocess.osProcessClass().id:
                            # Matches!
                            tags.append(IGlobalIdentifier(software).getGUID())
                except Exception:
                    LOG.debug("Unable to append event for OSProcess %s",
                              osprocess.osProcessClass().id)

            eventProxy.tags.addAll('ZenPacks.zenoss.OpenStack.DeviceProxyComponent', tags)
