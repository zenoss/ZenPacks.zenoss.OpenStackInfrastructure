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

from ZODB.transact import transact

from Products.Zuul.decorators import info, memoize
from Products.Zuul.catalog.events import IndexingEvent
from Products.Zuul.interfaces import ICatalogTool
from Products.AdvancedQuery import Eq
from Products.Zuul.form import schema as formschema
from Products.Zuul.utils import ZuulMessageFactory as _t


class DeviceProxyComponent(schema.DeviceProxyComponent):

    @classmethod
    def component_for_proxy_device(cls, device):
        '''
        Given any device in the system, check if it has a DeviceProxyComponent associated with
        it, and if it does, return that component.
        '''

        dmd = device.dmd
        for class_ in DeviceProxyComponent.__subclasses__():
            classname = class_.__module__ + '.' + class_.__name__

            results = ICatalogTool(dmd.Devices).search(
                types=(classname,),
                query=class_.componentsearch_query(device)
            )

            for brain in results:
                possible_match = brain.getObject()
                if device.id == possible_match.proxy_device().id:
                    return possible_match

        return None

    @classmethod
    def componentsearch_query(cls, device):
        '''
        Given a device, return a query that will match it against the set of
        components of this types which it could potentially be a proxy
        device for.

        This is used by component_for_proxy_device (and the devicelinkprovider)
        to know when a device has an associated DeviceProxyComponent.  It may
        be called on any device in the system.

        Default is to return any with a matching name.
        '''
        return Eq('name', device.name())

    def proxy_deviceclass_zproperty(self):
        '''
        Return the name of the zProperty that contains the proxy device 
        class name.

        Default is 'z<meta type>DeviceClass'
        '''
        return 'z' + self.meta_type + 'DeviceClass'

    def proxy_deviceclass(self):
        '''
        Return the device class object identified by proxy_deviceclass_zproperty,
        creating it if necessary.
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

    def ensure_proxy_device(self):
        '''
        Ensure that the proxy device exists, creating it if necessary.
        '''
        # Technically his does not need to retrieve the device, just
        # verify that it is there.  (Default is to retrieving it,
        # but this can be made more efficient by querying the 
        # catalog more intelligently)
        self.proxy_device()

        return True

    def proxy_device(self):
        '''
        Return this component's corresponding proxy device, creating
        it in the proxy_deviceclass if it does not exist.

        Default assumes that the names must match.
        '''
        device = self.dmd.Devices.findDevice(self.name())
        if device:
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

        return device

    def devicelink_descr(self):
        '''
        The description to put on the proxy device's expanded links section when linking
        back to this component.
        '''    
        return '"%s "%s" at %s' % (
            self.meta_type,
            self.name(),
            self.device().name()
        )


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

   