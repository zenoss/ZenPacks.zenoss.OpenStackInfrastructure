##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
Patches to be applied to the platform.
'''

import logging
log = logging.getLogger("zen.OpenStack.device")

from Products.ZenModel.OSProcess import OSProcess
from Products.ZenUtils.Utils import monkeypatch
from ZenPacks.zenoss.OpenStackInfrastructure.utils import getIpInterfaceMacs
from ZenPacks.zenoss.OpenStackInfrastructure.DeviceProxyComponent import DeviceProxyComponent
from Products.DataCollector.ApplyDataMap import ApplyDataMap
from ..zenpacklib import catalog_search


@monkeypatch('Products.ZenModel.Device.Device')
def openstackInstance(self):
    # Search first by serial number, if known.
    serialNumber = self.os.getHWSerialNumber()
    if serialNumber:
        instances = [x.getObject() for x in catalog_search(
            self.dmd.Devices,
            'ZenPacks_zenoss_OpenStackInfrastructure_Instance',
            serialNumber=serialNumber)]
        if len(instances) > 1:
            log.warning("More than one openstack instance found with a serial number of %s - returning the first one (%s)" %
                        (serialNumber, instances[0].id))
            return instances[0]

    # Nope?  OK, go to MAC addresses.
    instances = set()
    macs = getIpInterfaceMacs(self)
    vnics = [x.getObject() for x in catalog_search(
        self.dmd.Devices,
        'ZenPacks_zenoss_OpenStackInfrastructure_Vnic',
        macaddress=macs)]

    for vnic in vnics:
        instances.add(vnic.instance())

    if len(instances):
        instance = instances.pop()

        if len(instances):
            log.warning("More than one openstack instance found with MACs of %s - returning the first one (%s)" %
                        (macs, instance.id))

        return instance

    # Didn't find it.  Oh well.
    return None


@monkeypatch('Products.ZenModel.Device.Device')
def openstack_hostComponent(self):
    # If this is an openstack compute node, returns a the OpenstackHost component for it.
    host = DeviceProxyComponent.component_for_proxy_device(self)
    if host is not None and host.meta_type == 'OpenStackInfrastructureHost':
        return host
    return None


@monkeypatch('Products.ZenModel.Device.Device')
def openstack_instanceList(self):
    # If this is an openstack compute node, returns a list of
    # (instance_ID, instance_UUID) tuples for instances running on this host.

    host = self.openstack_hostComponent()
    try:
        return [(x.id, x.serverId) for x in host.hypervisor().instances()]
    except AttributeError:
        return []


@monkeypatch('Products.ZenModel.Device.Device')
def getApplyDataMapToOpenStackInfrastructureEndpoint(self):
    return []


@monkeypatch('Products.ZenModel.Device.Device')
def setApplyDataMapToOpenStackInfrastructureEndpoint(self, datamap):
    mapper = ApplyDataMap()

    component = DeviceProxyComponent.component_for_proxy_device(self)
    if not component:
        log.error("Unable to apply datamap to proxy component for %s (component not found)" % self)
    else:
        mapper._applyDataMap(component.device(), datamap)


@monkeypatch('Products.ZenModel.Device.Device')
def getApplyDataMapToOpenStackInfrastructureHost(self):
    return []


@monkeypatch('Products.ZenModel.Device.Device')
def setApplyDataMapToOpenStackInfrastructureHost(self, datamap):
    mapper = ApplyDataMap()

    component = DeviceProxyComponent.component_for_proxy_device(self)
    if not component:
        log.error("Unable to apply datamap to proxy component for %s (component not found)" % self)
    else:
        mapper._applyDataMap(component, datamap)


@monkeypatch(OSProcess)
def openstack_softwareComponent(self):
    """Return associated OpenStack SoftwareComponent instance."""
    host = self.device().openstack_hostComponent()
    if host:
        for software in host.hostedSoftware():
            if software.binary == self.osProcessClass().id:
                return software
