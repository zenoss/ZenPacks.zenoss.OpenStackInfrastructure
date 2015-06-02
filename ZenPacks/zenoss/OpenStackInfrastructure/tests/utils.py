##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
LOG = logging.getLogger('zen.OpenStack')

import Globals

import functools
import importlib
import re

from Products.ZenRelations.RelationshipBase import RelationshipBase
from Products.ZenRelations.ToManyContRelationship import ToManyContRelationship
from Products.ZenUtils.Utils import unused

unused(Globals)


def require_zenpack(zenpack_name, default=None):
    '''
    Decorator with mandatory zenpack_name argument.

    If zenpack_name can't be imported, the decorated function or method
    will return default. Otherwise it will execute and return as
    written.

    Usage looks like the following:

        @require_zenpack('ZenPacks.zenoss.Impact')
        @require_zenpack('ZenPacks.zenoss.vCloud')
        def dothatthingyoudo(args):
            return "OK"

        @require_zenpack('ZenPacks.zenoss.Impact', [])
        def returnalistofthings(args):
            return [1, 2, 3]
    '''
    def wrap(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                importlib.import_module(zenpack_name)
            except ImportError:
                return

            return f(*args, **kwargs)

        return wrapper

    return wrap


# When a manually-created python object is first added to its container, we
# need to reload it, as its in-memory representation is changed.
def addContained(object, relname, target):
    # print "addContained(" + str(object) + "." + relname + " => " + str(target) + ")"
    rel = getattr(object, relname)

    # contained via a relationship
    if isinstance(rel, ToManyContRelationship):
        rel._setObject(target.id, target)
        return rel._getOb(target.id)

    elif isinstance(rel, RelationshipBase):
        rel.addRelation(target)
        return rel._getOb(target.id)

    # contained via a property
    else:
        # note: in this scenario, you must have the target object's ID the same
        #       as the relationship from the parent object.

        assert(relname == target.id)
        object._setObject(target.id, target)
        return getattr(object, relname)


def addNonContained(object, relname, target):
    rel = getattr(object, relname)
    rel.addRelation(target)
    return target


def create_model_data(dmd):
    '''
    Return an Endpoint suitable for Impact functional testing.
    '''
    # DeviceClass
    dc = dmd.Devices.createOrganizer('/OpenStack/Infrastructure')
    dc.setZenProperty('zPythonClass', 'ZenPacks.zenoss.OpenStackInfrastructure.Endpoint')

    # OSProcessClasses
    osc = dmd.Processes.createOrganizer('/OpenStack')
    for binary in ['nova-cert', 'nova-conductor', 'nova-consoleauth', 'nova-scheduler', 'nova-compute', 'nova-api']:
        osc.manage_addOSProcessClass(binary)

    # Endpoint
    endpoint = dc.createInstance('endpoint')

    # Org Structure
    from ZenPacks.zenoss.OpenStackInfrastructure.Region import Region
    from ZenPacks.zenoss.OpenStackInfrastructure.AvailabilityZone import AvailabilityZone
    region = addContained(endpoint, "components", Region("region"))
    zone1 = addContained(endpoint, "components", AvailabilityZone("zone1"))
    zone2 = addContained(endpoint, "components", AvailabilityZone("zone2"))
    addNonContained(region, "childOrgs", zone1)
    addNonContained(region, "childOrgs", zone2)

    # Tenants
    from ZenPacks.zenoss.OpenStackInfrastructure.Tenant import Tenant
    tenant1 = addContained(endpoint, "components", Tenant("tenant-tenant1"))
    tenant2 = addContained(endpoint, "components", Tenant("tenant-tenant2"))

    # Flavor
    from ZenPacks.zenoss.OpenStackInfrastructure.Flavor import Flavor
    flavor1 = addContained(endpoint, "components", Flavor("flavor1"))

    # Image
    from ZenPacks.zenoss.OpenStackInfrastructure.Image import Image
    image1 = addContained(endpoint, "components", Image("image1"))

    # Host
    from ZenPacks.zenoss.OpenStackInfrastructure.Host import Host
    computehost1 = addContained(endpoint, "components", Host("computehost1"))
    addNonContained(computehost1, "orgComponent", zone1)
    computehost2 = addContained(endpoint, "components", Host("computehost2"))
    addNonContained(computehost2, "orgComponent", zone2)
    controllerhost = addContained(endpoint, "components", Host("controllerhost"))
    addNonContained(controllerhost, "orgComponent", zone1)

    # SoftwareComponents
    from ZenPacks.zenoss.OpenStackInfrastructure.NovaService import NovaService
    from ZenPacks.zenoss.OpenStackInfrastructure.NovaApi import NovaApi
    nova_consoleauth = addContained(endpoint, "components", NovaService("nova-consoleauth"))
    nova_consoleauth.binary = 'nova-consoleauth'
    addNonContained(nova_consoleauth, "hostedOn", controllerhost)
    addNonContained(nova_consoleauth, "orgComponent", zone1)
    nova_scheduler = addContained(endpoint, "components", NovaService("nova-scheduler"))
    nova_scheduler.binary = 'nova-scheduler'
    addNonContained(nova_scheduler, "hostedOn", controllerhost)
    addNonContained(nova_scheduler, "orgComponent", zone1)
    nova_conductor1 = addContained(endpoint, "components", NovaService("nova-conductor1"))
    nova_conductor1.binary = 'nova-conductor'
    nova_conductor2 = addContained(endpoint, "components", NovaService("nova-conductor2"))
    nova_conductor2.binary = 'nova-conductor'
    addNonContained(nova_conductor1, "hostedOn", computehost1)
    addNonContained(nova_conductor1, "orgComponent", zone1)
    addNonContained(nova_conductor2, "hostedOn", computehost2)
    addNonContained(nova_conductor2, "orgComponent", zone2)
    nova_compute1 = addContained(endpoint, "components", NovaService("nova-compute1"))
    nova_compute1.binary = 'nova-compute'
    nova_compute2 = addContained(endpoint, "components", NovaService("nova-compute2"))
    nova_compute2.binary = 'nova-compute'
    addNonContained(nova_compute1, "hostedOn", computehost1)
    addNonContained(nova_compute1, "orgComponent", zone1)
    addNonContained(nova_compute2, "hostedOn", computehost2)
    addNonContained(nova_compute2, "orgComponent", zone2)
    nova_cert = addContained(endpoint, "components", NovaService("nova-cert"))
    nova_cert.binary = 'nova-cert'
    addNonContained(nova_cert, "hostedOn", controllerhost)
    addNonContained(nova_cert, "orgComponent", zone1)
    nova_api = addContained(endpoint, "components", NovaApi("nova-api"))
    nova_api.binary = 'nova-api'
    addNonContained(nova_api, "hostedOn", controllerhost)
    addNonContained(nova_api, "orgComponent", region)

    # Hypervisor
    from ZenPacks.zenoss.OpenStackInfrastructure.Hypervisor import Hypervisor
    hypervisor1 = addContained(endpoint, "components", Hypervisor("hypervisor1"))
    hypervisor2 = addContained(endpoint, "components", Hypervisor("hypervisor2"))
    addNonContained(hypervisor1, "host", computehost1)
    addNonContained(hypervisor2, "host", computehost2)

    # Instance
    from ZenPacks.zenoss.OpenStackInfrastructure.Instance import Instance
    instance1 = addContained(endpoint, "components", Instance("instance1"))
    instance2 = addContained(endpoint, "components", Instance("instance2"))
    instance3 = addContained(endpoint, "components", Instance("instance3"))
    instance4 = addContained(endpoint, "components", Instance("instance4"))
    addNonContained(instance1, "flavor", flavor1)
    addNonContained(instance2, "flavor", flavor1)
    addNonContained(instance3, "flavor", flavor1)
    addNonContained(instance4, "flavor", flavor1)
    addNonContained(instance1, "image", image1)
    addNonContained(instance2, "image", image1)
    addNonContained(instance3, "image", image1)
    addNonContained(instance4, "image", image1)
    addNonContained(instance1, "hypervisor", hypervisor1)
    addNonContained(instance2, "hypervisor", hypervisor1)
    addNonContained(instance3, "hypervisor", hypervisor2)
    addNonContained(instance4, "hypervisor", hypervisor2)
    addNonContained(instance1, "tenant", tenant1)
    addNonContained(instance2, "tenant", tenant2)
    addNonContained(instance3, "tenant", tenant1)
    addNonContained(instance4, "tenant", tenant2)

    # Vnic
    from ZenPacks.zenoss.OpenStackInfrastructure.Vnic import Vnic
    instance1vnic1 = addContained(instance1, "vnics", Vnic("instance1_vnic1"))
    instance1vnic1.macaddress = 'de:ad:be:ef:01:01'
    instance1vnic1.index_object()
    instance1vnic2 = addContained(instance1, "vnics", Vnic("instance1_vnic2"))
    instance1vnic2.macaddress = 'de:ad:be:ef:01:02'
    instance1vnic2.index_object()
    instance2vnic1 = addContained(instance2, "vnics", Vnic("instance2_vnic1"))
    instance2vnic1.macaddress = 'de:ad:be:ef:02:01'
    instance2vnic1.index_object()
    instance2vnic2 = addContained(instance2, "vnics", Vnic("instance2_vnic2"))
    instance2vnic2.macaddress = 'de:ad:be:ef:02:02'
    instance2vnic2.index_object()
    instance3vnic1 = addContained(instance3, "vnics", Vnic("instance3_vnic1"))
    instance3vnic1.macaddress = 'de:ad:be:ef:03:01'
    instance3vnic1.index_object()
    instance3vnic2 = addContained(instance3, "vnics", Vnic("instance3_vnic2"))
    instance3vnic2.macaddress = 'de:ad:be:ef:03:02'
    instance3vnic2.index_object()
    instance4vnic1 = addContained(instance4, "vnics", Vnic("instance4_vnic1"))
    instance4vnic1.macaddress = 'de:ad:be:ef:04:01'
    instance4vnic1.index_object()
    instance4vnic2 = addContained(instance4, "vnics", Vnic("instance4_vnic2"))
    instance4vnic2.macaddress = 'de:ad:be:ef:04:02'
    instance4vnic2.index_object()

    # Linux guest devices (Virtual)
    # make sure that the interfaces line up.
    guest_dc = dmd.Devices.createOrganizer('/Server/SSH/Linux')
    guest_dc.setZenProperty('zPythonClass', 'Products.ZenModel.Device')
    guest_instance1 = guest_dc.createInstance("g-instance1")
    guest_instance2 = guest_dc.createInstance("g-instance2")
    guest_instance3 = guest_dc.createInstance("g-instance3")
    # instance4 is not monitored by zenoss.

    from Products.ZenModel.IpInterface import IpInterface

    def add_linux_interface_mac(device, interface_name, macaddress):
        eth_if = IpInterface(interface_name)
        device.os.interfaces._setObject(eth_if.id, eth_if)
        eth_if = device.os.interfaces._getOb(eth_if.id)
        eth_if.macaddress = macaddress
        eth_if.index_object()
        device.index_object()

    add_linux_interface_mac(guest_instance1, 'eth0', 'de:ad:be:ef:01:01')
    add_linux_interface_mac(guest_instance1, 'eth1', 'de:ad:be:ef:01:02')
    add_linux_interface_mac(guest_instance2, 'eth0', 'de:ad:be:ef:02:01')
    add_linux_interface_mac(guest_instance2, 'eth1', 'de:ad:be:ef:02:02')
    add_linux_interface_mac(guest_instance3, 'eth0', 'de:ad:be:ef:03:01')
    add_linux_interface_mac(guest_instance3, 'eth1', 'de:ad:be:ef:03:02')

    # Linux devices (Physical)
    # (link to host1 and host2)
    phys_dc = dmd.Devices.createOrganizer('/Server/SSH/Linux/NovaHost')
    phys_dc.setZenProperty('zPythonClass', 'Products.ZenModel.Device')
    phys_computehost1 = phys_dc.createInstance("p-computehost1")
    phys_computehost2 = phys_dc.createInstance("p-computehost2")
    phys_controllerhost = phys_dc.createInstance("p-controllerhost")

    # Link the host components to the physical hosts.
    computehost1.claim_proxy_device(phys_computehost1)
    computehost2.claim_proxy_device(phys_computehost2)
    controllerhost.claim_proxy_device(phys_controllerhost)

    # Add OSprocesses for each of the software components.
    from ZenPacks.zenoss.OpenStackInfrastructure.SoftwareComponent import SoftwareComponent
    from Products.ZenModel.OSProcess import OSProcess
    for component in endpoint.components():
        if isinstance(component, SoftwareComponent):
            binary = component.binary
            linux_device = component.hostedOn().proxy_device()

            process_id = '%s_%s' % (linux_device.id, binary)
            process = OSProcess(process_id)
            linux_device.os.processes._setObject(process_id, process)
            process = linux_device.os.processes._getOb(process_id)

            process_class = re.sub(r'\d+$', '', binary)
            process.setOSProcessClass("Processes/OpenStack/osProcessClasses/%s" % process_class)

    return {
        'endpoint': endpoint,
        'phys_dc': phys_dc,
        'guest_dc': guest_dc
    }
