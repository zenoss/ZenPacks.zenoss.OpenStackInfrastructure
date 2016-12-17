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

import collections
import logging
log = logging.getLogger("zen.OpenStack.device")

from Products.ZenModel.OSProcess import OSProcess
from Products.ZenUtils.Utils import monkeypatch, getObjectsFromCatalog
from Products.Zuul.facades.devicefacade import DeviceFacade
from ZenPacks.zenoss.OpenStackInfrastructure.utils import getIpInterfaceMacs
from ZenPacks.zenoss.OpenStackInfrastructure.DeviceProxyComponent import DeviceProxyComponent
from Products.DataCollector.ApplyDataMap import ApplyDataMap
from ..zenpacklib import catalog_search

# LinuxDevice only exists in LinuxMonitor >= 2.0.
try:
    from ZenPacks.zenoss.LinuxMonitor.LinuxDevice import LinuxDevice
except ImportError:
    from Products.ZenModel.Device import Device as LinuxDevice

from ZenPacks.zenoss.OpenStackInfrastructure.Endpoint import Endpoint


@monkeypatch('Products.ZenModel.Device.Device')
def openstackInstance(self):
    # Search first by serial number, if known.
    serialNumber = self.os.getHWSerialNumber()
    if serialNumber:
        instances = []
        for i in catalog_search(
                        self.dmd.Devices,
                        'ZenPacks_zenoss_OpenStackInfrastructure_Instance',
                        serialNumber=serialNumber):
            try:
                instance = i.getObject()
            except Exception:
                # ignore a stale entry
                pass
            else:
                instances.appens(instance)

        if len(instances) > 1:
            log.warning("More than one openstack instance found with a serial number of %s - returning the first one (%s)" %
                        (serialNumber, instances[0].id))
            return instances[0]

    # Nope?  OK, go to MAC addresses.
    instances = set()
    macs = getIpInterfaceMacs(self)
    vnics = []
    for v in catalog_search(
            self.dmd.Devices,
            'ZenPacks_zenoss_OpenStackInfrastructure_Vnic',
            serialNumber=macs):
        try:
            vnic = v.getObject()
        except Exception:
            # ignore a stale entry
            pass
        else:
            vnics.appens(vnic)

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


@monkeypatch(LinuxDevice)
def getDynamicViewGroup(self):
    """Return DynamicView group information.

    Monkey-patched here so that the devices related to OpenStack hosts can be
    put into a different group with a higher weight. This prevents hypervisor
    and other cloud management devices from being shown in the same column as
    guest devices.

    """
    if self.openstack_hostComponent():
        return {
            "name": "Devices (OpenStack)",
            "weight": 550,
            "type": "ZenPacks.zenoss.OpenStackInfrastructure",
            "icon": self.icon_url,
            }
    else:
        return original(self)  # NOQA: original injected by monkeypatch


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


if hasattr(DeviceFacade, "getGraphDefinitionsForComponent"):
    @monkeypatch(DeviceFacade)
    def getGraphDefinitionsForComponent(self, *args, **kwargs):
        """Return dictionary of meta_type to associated graph definitions.

        component.getGraphObjects() can return pairs of (graphDef, context)
        where context is not the component. One example is
        FileSystem.getGraphObjects returning pairs for graphs on its underlying
        HardDisk. We have to make sure to return these graph definitions under
        their meta_type, not component's meta_type.

        We accept *args and **kwargs to be less brittle in case the
        monkeypatched method changes signature in an otherwise unaffecting way.

        args is expected to look something like this:

            ('/zport/dmd/Devices/OpenStack/Infrastructure/devices/OpenStackInfrKilo',)

        kwargs is expected to look like this:

            {}

        """
        obj = self._getObject(args[0])

        # Limit the patch scope to this ZenPack
        if not isinstance(obj, Endpoint):
            return original(self, *args, **kwargs)

        graphDefs = collections.defaultdict(set)
        for component in getObjectsFromCatalog(obj.componentSearch):
            for graphDef, context in component.getGraphObjects():
                graphDefs[context.meta_type].add(graphDef.id)

        graphDefs = {
            meta_type:graphDefs[meta_type]
            for meta_type in graphDefs.iterkeys()
                if meta_type.startswith('OpenStackInfrastructure')
                    and meta_type != 'OpenStackInfrastructureEndpoint'}

        return graphDefs
