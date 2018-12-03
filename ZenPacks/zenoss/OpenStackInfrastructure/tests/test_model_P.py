#!/usr/bin/env python

###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2015, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

import os
import pickle
import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('zen.OpenStackInfrastructure')

from twisted.internet import defer

import Globals
from zope.event import notify
from Products.Zuul.catalog.events import IndexingEvent
from Products.Five import zcml

from Products.DataCollector.ApplyDataMap import ApplyDataMap
from Products.ZenTestCase.BaseTestCase import BaseTestCase
from Products.ZenUtils.guid.interfaces import IGlobalIdentifier
from Products.ZenUtils.Utils import unused

from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import setup_crochet, FilteredLog
from ZenPacks.zenoss.OpenStackInfrastructure.modeler.plugins.zenoss.OpenStackInfrastructure \
    import OpenStackInfrastructure as OpenStackInfrastructureModeler

from Products.ZenModel import Device
from ZenPacks.zenoss.OpenStackInfrastructure import hostmap

unused(Globals)

crochet = setup_crochet()

MOCK_DNS = {
    "osi-p": "10.87.209.165",
}


def getHostObjectByName(hosts, name):
    for h in hosts:
        if name in h.id:
            return h


class TestModel(BaseTestCase):

    disableLogging = False

    def tearDown(self):
        super(TestModel, self).tearDown()
        Device.getHostByName = self._real_getHostByName
        hostmap.resolve_names = self._real_resolve_names

    def afterSetUp(self):
        super(TestModel, self).afterSetUp()

        # Workaround for IMP-389:
        # When Impact 5.2.1-5.2.3 (at least) are installed, setProdState
        # is patched to re-index the object in the global catalog specifically
        # on the productionState column, but at least on older verions of RM,
        # the sandboxed version of global_catalog does not index that column,
        # which causes setProdState to fail.  Add the index for now, to
        # work around this.
        if (hasattr(self.dmd.global_catalog, 'indexes') and
                'productionState' not in self.dmd.global_catalog.indexes()):
            from Products.ZenUtils.Search import makeCaseSensitiveFieldIndex
            self.dmd.global_catalog.addIndex('productionState', makeCaseSensitiveFieldIndex('productionState'))
            self.dmd.global_catalog.addColumn('productionState')

        # Patch to remove DNS dependencies
        def getHostByName(name):
            return MOCK_DNS.get(name)

        def resolve_names(names):
            result = {}
            for name in names:
                result[name] = MOCK_DNS.get(name)
            return defer.maybeDeferred(lambda: result)

        self._real_resolve_names = hostmap.resolve_names
        hostmap.resolve_names = resolve_names

        self._real_getHostByName = Device.getHostByName
        Device.getHostByName = getHostByName

        dc = self.dmd.Devices.createOrganizer('/Devices/OpenStack/Infrastructure')

        dc.setZenProperty('zPythonClass', 'ZenPacks.zenoss.OpenStackInfrastructure.Endpoint')
        dc.setZenProperty('zOpenStackHostDeviceClass', '/Server/SSH/Linux/NovaHost')
        dc.setZenProperty('zOpenStackRegionName', 'RegionOne')
        dc.setZenProperty('zOpenStackAuthUrl', 'http://1.2.3.4:5000/v2.0')
        dc.setZenProperty('zOpenStackNovaApiHosts', [])
        dc.setZenProperty('zOpenStackExtraHosts', [])
        dc.setZenProperty('zOpenStackHostMapToId', [])
        dc.setZenProperty('zOpenStackHostMapSame', [])
        dc.setZenProperty('zOpenStackHostLocalDomain', '')
        dc.setZenProperty('zOpenStackExtraApiEndpoints', [])

        self.d = dc.createInstance('zenoss.OpenStackInfrastructure.testDevice')
        self.d.setPerformanceMonitor('localhost')
        self.d.index_object()
        notify(IndexingEvent(self.d))

        self.applyDataMap = ApplyDataMap()._applyDataMap

        # Required to prevent erroring out when trying to define viewlets in
        # ../browser/configure.zcml.
        import zope.viewlet
        zcml.load_config('meta.zcml', zope.viewlet)

        import ZenPacks.zenoss.OpenStackInfrastructure
        zcml.load_config('configure.zcml', ZenPacks.zenoss.OpenStackInfrastructure)

        self._loadZenossData()

    def _loadZenossData(self):
        if hasattr(self, '_modeled'):
            return

        modeler = OpenStackInfrastructureModeler()
        with open(os.path.join(os.path.dirname(__file__),
                               'data',
                               'model',
                               'osi_p_admin.pickle')) as pickle_file:
            results = pickle.load(pickle_file)

        for data_map in modeler.process(self.d, results, log):
            self.applyDataMap(self.d, data_map)

        self._modeled = True

    def testTenant(self):
        self.assertTrue(self._modeled)

        tenants = self.d.getDeviceComponents(type='OpenStackInfrastructureTenant')
        self.assertEquals(len(tenants), 3)
        self.assertEquals(tenants[0].endpoint.id, 'endpoint')
        self.assertEquals(tenants[0].endpoint.name(), 'admin')
        self.assertEquals(tenants[1].endpoint.id, 'endpoint')
        self.assertEquals(tenants[1].endpoint.name(), 'services')
        self.assertEquals(tenants[2].endpoint.id, 'endpoint')
        self.assertEquals(tenants[2].endpoint.name(), 'demo')
        self.assertEquals(tenants[0].floatingIps.id, 'floatingIps')
        self.assertEquals(tenants[0].floatingIps.name(), 'admin')
        self.assertEquals(tenants[1].floatingIps.id, 'floatingIps')
        self.assertEquals(tenants[1].floatingIps.name(), 'services')
        self.assertEquals(tenants[2].floatingIps.id, 'floatingIps')
        self.assertEquals(tenants[2].floatingIps.name(), 'demo')
        self.assertEquals(tenants[0].instances.id, 'instances')
        self.assertEquals(tenants[0].instances.name(), 'admin')
        self.assertEquals(tenants[1].instances.id, 'instances')
        self.assertEquals(tenants[1].instances.name(), 'services')
        self.assertEquals(tenants[2].instances.id, 'instances')
        self.assertEquals(tenants[2].instances.name(), 'demo')
        self.assertEquals(tenants[0].networks.id, 'networks')
        self.assertEquals(tenants[0].networks.name(), 'admin')
        self.assertEquals(tenants[1].networks.id, 'networks')
        self.assertEquals(tenants[1].networks.name(), 'services')
        self.assertEquals(tenants[2].networks.id, 'networks')
        self.assertEquals(tenants[2].networks.name(), 'demo')
        self.assertEquals(tenants[0].ports.id, 'ports')
        self.assertEquals(tenants[0].ports.name(), 'admin')
        self.assertEquals(tenants[1].ports.id, 'ports')
        self.assertEquals(tenants[1].ports.name(), 'services')
        self.assertEquals(tenants[2].ports.id, 'ports')
        self.assertEquals(tenants[2].ports.name(), 'demo')
        self.assertEquals(tenants[0].routers.id, 'routers')
        self.assertEquals(tenants[0].routers.name(), 'admin')
        self.assertEquals(tenants[1].routers.id, 'routers')
        self.assertEquals(tenants[1].routers.name(), 'services')
        self.assertEquals(tenants[2].routers.id, 'routers')
        self.assertEquals(tenants[2].routers.name(), 'demo')
        self.assertEquals(tenants[0].subnets.id, 'subnets')
        self.assertEquals(tenants[0].subnets.name(), 'admin')
        self.assertEquals(tenants[1].subnets.id, 'subnets')
        self.assertEquals(tenants[1].subnets.name(), 'services')
        self.assertEquals(tenants[2].subnets.id, 'subnets')
        self.assertEquals(tenants[2].subnets.name(), 'demo')
        self.assertEquals(tenants[0].volumes.id, 'volumes')
        self.assertEquals(tenants[0].volumes.name(), 'admin')
        self.assertEquals(tenants[1].volumes.id, 'volumes')
        self.assertEquals(tenants[1].volumes.name(), 'services')
        self.assertEquals(tenants[2].volumes.id, 'volumes')
        self.assertEquals(tenants[2].volumes.name(), 'demo')
        self.assertEquals(tenants[0].volSnapshots.id, 'volSnapshots')
        self.assertEquals(tenants[0].volSnapshots.name(), 'admin')
        self.assertEquals(tenants[1].volSnapshots.id, 'volSnapshots')
        self.assertEquals(tenants[1].volSnapshots.name(), 'services')
        self.assertEquals(tenants[2].volSnapshots.id, 'volSnapshots')
        self.assertEquals(tenants[2].volSnapshots.name(), 'demo')
        self.assertEquals(tenants[0].quota.id, 'quota')
        self.assertEquals(tenants[0].quota.name(), 'admin')
        self.assertEquals(tenants[1].quota.id, 'quota')
        self.assertEquals(tenants[1].quota.name(), 'services')
        self.assertEquals(tenants[2].quota.id, 'quota')
        self.assertEquals(tenants[2].quota.name(), 'demo')

    def testRegion(self):
        self.assertTrue(self._modeled)

        regions = self.d.getDeviceComponents(type='OpenStackInfrastructureRegion')
        self.assertEquals(len(regions), 1)
        self.assertEquals('region-RegionOne', regions[0].id)
        self.assertEquals('RegionOne', regions[0].name())
        self.assertEquals(regions[0].endpoint.id, 'endpoint')
        self.assertEquals(regions[0].endpoint.name(), 'RegionOne')
        self.assertEquals(regions[0].hosts.id, 'hosts')
        self.assertEquals(regions[0].hosts.name(), 'RegionOne')
        self.assertEquals(regions[0].pools.id, 'pools')
        self.assertEquals(regions[0].pools.name(), 'RegionOne')

    def testAvailabilityZone(self):
        self.assertTrue(self._modeled)

        avzones = self.d.getDeviceComponents(type='OpenStackInfrastructureAvailabilityZone')
        self.assertEquals(len(avzones), 2)
        for zone in avzones:
            if 'zone-internal' in zone.id: zone_internal = zone
            if 'zone-nova' in zone.id: zone_nova = zone

        self.assertEquals(zone_nova.endpoint.id, 'endpoint')
        self.assertEquals(zone_nova.endpoint.name(), 'nova')
        self.assertEquals(zone_nova.hosts.id, 'hosts')
        self.assertEquals(zone_nova.hosts.name(), 'nova')
        self.assertEquals(zone_nova.pools.id, 'pools')
        self.assertEquals(zone_nova.pools.name(), 'nova')

        self.assertEquals(zone_internal.endpoint.id, 'endpoint')
        self.assertEquals(zone_internal.endpoint.name(), 'internal')
        self.assertEquals(zone_internal.hosts.id, 'hosts')
        self.assertEquals(zone_internal.hosts.name(), 'internal')
        self.assertEquals(zone_internal.pools.id, 'pools')
        self.assertEquals(zone_internal.pools.name(), 'internal')

    def testFlavor(self):
        self.assertTrue(self._modeled)

        flavors = self.d.getDeviceComponents(type='OpenStackInfrastructureFlavor')
        self.assertEquals(len(flavors), 6)
        flavornames = [f.name() for f in flavors]
        flavorids = [f.id for f in flavors]

        self.assertTrue('m1.nano' in flavornames)
        self.assertTrue('m1.tiny' in flavornames)
        self.assertTrue('m1.small' in flavornames)
        self.assertTrue('m1.medium' in flavornames)
        self.assertTrue('m1.large' in flavornames)
        self.assertTrue('m1.xlarge' in flavornames)
        self.assertTrue('flavor-1' in flavorids)
        self.assertTrue('flavor-2' in flavorids)
        self.assertTrue('flavor-3' in flavorids)
        self.assertTrue('flavor-4' in flavorids)
        self.assertTrue('flavor-5' in flavorids)

    def testImage(self):
        self.assertTrue(self._modeled)

        images = self.d.getDeviceComponents(type='OpenStackInfrastructureImage')
        self.assertEquals(len(images), 1)

        self.assertEquals(images[0].id,'image-fc6607b7-ccbf-4834-be6c-0a09faef19ec')
        self.assertEquals(images[0].name(), 'cirros')

    def testInstance(self):
        self.assertTrue(self._modeled)

        instances = self.d.getDeviceComponents(
            type='OpenStackInfrastructureInstance')
        self.assertEquals(len(instances), 3)
        self.assertEquals(instances[0].id,'server-29132ff8-5048-4c63-a4c7-ba56c13d0895')
        self.assertEquals('test2', instances[0].name())

    def testHost(self):
        self.assertTrue(self._modeled)

        hosts = self.d.getDeviceComponents(type='OpenStackInfrastructureHost')

        host = getHostObjectByName(hosts, 'osi-p')
        self.assertEquals(len(hosts), 1)
        self.assertEquals(host.device().id, 'zenoss.OpenStackInfrastructure.testDevice')
        self.assertEquals(host.name(), 'osi-p')
        self.assertEquals(host.hypervisor.id, 'hypervisor')
        self.assertEquals(host.hypervisor.name(), 'osi-p')

        hostedSoftware = host.hostedSoftware()[0]
        self.assertEquals(hostedSoftware.id,
                          'service-nova-conductor-osi-p-internal')

        self.assertEquals(hostedSoftware.orgComponent().id,
                          'zone-internal')

    def testDeviceProxyIntegrity(self):
        self.assertTrue(self._modeled)

        hosts = self.d.getDeviceComponents(type='OpenStackInfrastructureHost')
        self.assertEquals(len(hosts), 1)

        host = getHostObjectByName(hosts, 'osi-p')

        # Ensure the following hosts don't have proxy_device():
        self.assertIsNotNone(host.proxy_device())
        self.assertEquals(len(host.hostedSoftware()), 12)

    def testHypervisor(self):
        self.assertTrue(self._modeled)

        hypervisors = self.d.getDeviceComponents(type='OpenStackInfrastructureHypervisor')
        self.assertEquals(len(hypervisors), 1)

        self.assertEquals(hypervisors[0].hypervisorId, 1)
        self.assertEquals(hypervisors[0].id, 'hypervisor-1')
        self.assertEquals(hypervisors[0].name(), 'osi-p.1')
        self.assertEquals(hypervisors[0].host.id, 'host')
        self.assertEquals(hypervisors[0].host.name(), 'osi-p.1')
        self.assertEquals(hypervisors[0].instances.id, 'instances')
        self.assertEquals(hypervisors[0].instances.name(), 'osi-p.1')
        self.assertEquals(hypervisors[0].endpoint.id, 'endpoint')
        self.assertEquals(hypervisors[0].endpoint.name(), 'osi-p.1')
        self.assertEquals(hypervisors[0].getPrimaryId(),
                          '/zport/dmd/Devices/OpenStack/Infrastructure' +
                          '/devices/zenoss.OpenStackInfrastructure.testDevice' +
                          '/components/hypervisor-1')

    def testNeutronAgent(self):
        self.assertTrue(self._modeled)

        agents = self.d.getDeviceComponents(type='OpenStackInfrastructureNeutronAgent')
        self.assertEquals(len(agents), 5)

        self.assertEquals(agents[0].id, "agent-552a05c5-2454-49d2-9fbe-c27434532d67")
        self.assertEquals(agents[0].title, 'Open vSwitch agent@osi-p')
        self.assertEquals(agents[0].agentId, "552a05c5-2454-49d2-9fbe-c27434532d67")
        self.assertEquals(agents[0].binary, 'neutron-openvswitch-agent')
        self.assertTrue(agents[0].enabled)
        self.assertEquals(agents[0].operStatus, 'UP')
        self.assertEquals(agents[0].type, 'Open vSwitch agent')

        self.assertEquals(agents[1].id, "agent-5b14f0a0-1856-416e-8513-b343abb1379a")
        self.assertEquals(agents[1].title, 'DHCP agent@osi-p')
        self.assertEquals(agents[1].agentId, "5b14f0a0-1856-416e-8513-b343abb1379a")
        self.assertEquals(agents[1].binary, 'neutron-dhcp-agent')
        self.assertTrue(agents[1].enabled)
        self.assertEquals(agents[1].operStatus, 'UP')
        self.assertEquals(agents[1].type, 'DHCP agent')

        self.assertEquals(agents[2].id, "agent-70f5cf23-f76a-46a6-959d-8eb2cc70be7b")
        self.assertEquals(agents[2].title, 'Metering agent@osi-p')
        self.assertEquals(agents[2].agentId, "70f5cf23-f76a-46a6-959d-8eb2cc70be7b")
        self.assertEquals(agents[2].binary, 'neutron-metering-agent')
        self.assertTrue(agents[2].enabled)
        self.assertEquals(agents[2].operStatus, 'UP')
        self.assertEquals(agents[2].type, 'Metering agent')

        self.assertEquals(agents[3].id, "agent-aca99d33-7d7c-4e19-9693-24ce78fcd0fc")
        self.assertEquals(agents[3].title, 'Metadata agent@osi-p')
        self.assertEquals(agents[3].agentId, "aca99d33-7d7c-4e19-9693-24ce78fcd0fc")
        self.assertEquals(agents[3].binary, 'neutron-metadata-agent')
        self.assertTrue(agents[3].enabled)
        self.assertEquals(agents[3].operStatus, 'UP')
        self.assertEquals(agents[3].type, 'Metadata agent')

        self.assertEquals(agents[4].id, "agent-d5dc68ba-9dcc-45cd-b4a7-95a4ba39e68c")
        self.assertEquals(agents[4].title, 'L3 agent@osi-p')
        self.assertEquals(agents[4].agentId, "d5dc68ba-9dcc-45cd-b4a7-95a4ba39e68c")
        self.assertEquals(agents[4].binary, 'neutron-l3-agent')
        self.assertTrue(agents[4].enabled)
        self.assertEquals(agents[4].operStatus, 'UP')
        self.assertEquals(agents[4].type, 'L3 agent')

    def testNetwork(self):
        self.assertTrue(self._modeled)

        networks = self.d.getDeviceComponents(type='OpenStackInfrastructureNetwork')
        self.assertEquals(len(networks), 2)

        self.assertEquals(networks[0].title, 'public')
        self.assertEquals(networks[0].netId, "0ccbb5ec-9737-4107-96ab-5fca0e5974fe")
        self.assertTrue(networks[0].netExternal)
        self.assertEquals(networks[0].netStatus, 'ACTIVE')
        self.assertEquals(networks[0].netType, 'FLAT')
        self.assertTrue(networks[0].admin_state_up)

        self.assertEquals(networks[1].title, 'private')
        self.assertEquals(networks[1].netId, "f82afbca-d429-4dc7-b3c0-3ead28855f2e")
        self.assertFalse(networks[1].netExternal)
        self.assertEquals(networks[1].netStatus, 'ACTIVE')
        self.assertEquals(networks[1].netType, 'VXLAN')
        self.assertTrue(networks[1].admin_state_up)

    def testSubnet(self):
        self.assertTrue(self._modeled)

        subnets = self.d.getDeviceComponents(type='OpenStackInfrastructureSubnet')
        self.assertEquals(len(subnets), 2)

        self.assertEquals(subnets[0].title, 'public_subnet')
        self.assertEquals(subnets[0].cidr, '172.24.4.0/24')
        self.assertEquals(len(subnets[0].dns_nameservers), 0)
        self.assertEquals(subnets[0].gateway_ip, '172.24.4.1')
        self.assertEquals(subnets[0].subnetId, '0e56f3ac-2289-4422-b3a8-e5a930dcec47')

        self.assertEquals(subnets[1].title, 'private_subnet')
        self.assertEquals(subnets[1].cidr, '10.0.0.0/24')
        self.assertEquals(len(subnets[1].dns_nameservers), 0)
        self.assertEquals(subnets[1].gateway_ip, '10.0.0.1')
        self.assertEquals(subnets[1].subnetId, '25fca2dd-953a-4663-a640-10e0f04d9543')

    def testRouter(self):
        self.assertTrue(self._modeled)

        routers = self.d.getDeviceComponents(type='OpenStackInfrastructureRouter')
        self.assertEquals(len(routers), 1)

        self.assertEquals(routers[0].routerId, '3dfb6205-861c-416c-ac3d-81912abc0335')
        self.assertTrue(routers[0].admin_state_up)
        self.assertEquals(routers[0].gateways[0], '172.24.4.8')
        self.assertEquals(len(routers[0].routes), 0)
        self.assertEquals(routers[0].status, 'ACTIVE')
        self.assertEquals(routers[0].title, 'router1')

    def testPort(self):
        self.assertTrue(self._modeled)

        ports = self.d.getDeviceComponents(type='OpenStackInfrastructurePort')
        self.assertEquals(len(ports), 8)

        self.assertTrue(ports[0].admin_state_up)
        self.assertEquals(ports[0].device_owner, 'network:router_interface')
        self.assertEquals(ports[0].fixed_ip_list, '10.0.0.1')
        self.assertEquals(ports[0].portId, '486e57cb-2ba3-4c4f-acb8-a21ea7739f03')
        self.assertEquals(ports[0].mac_address, 'FA:16:3E:92:D3:AB')
        self.assertEquals(ports[0].status, 'ACTIVE')
        self.assertEquals(ports[0].title, '')
        self.assertEquals(ports[0].vif_type, 'ovs')

        self.assertTrue(ports[1].admin_state_up)
        self.assertEquals(ports[1].device_owner, 'network:floatingip')
        self.assertEquals(ports[1].fixed_ip_list, '172.24.4.5')
        self.assertEquals(ports[1].portId, '507e8f3e-426f-40fb-8abf-f342f724a077')
        self.assertEquals(ports[1].mac_address, 'FA:16:3E:56:AE:85')
        self.assertEquals(ports[1].status, 'N/A')
        self.assertEquals(ports[1].title, '')
        self.assertEquals(ports[1].vif_type, 'unbound')

        self.assertTrue(ports[2].admin_state_up)
        self.assertEquals(ports[2].device_owner, 'network:floatingip')
        self.assertEquals(ports[2].fixed_ip_list, '172.24.4.4')
        self.assertEquals(ports[2].portId, '66297e0e-5f7f-4be2-9708-f8d6a8540574')
        self.assertEquals(ports[2].mac_address, 'FA:16:3E:B5:50:E9')
        self.assertEquals(ports[2].status, 'N/A')
        self.assertEquals(ports[2].title, '')
        self.assertEquals(ports[2].vif_type, 'unbound')

        self.assertTrue(ports[3].admin_state_up)
        self.assertEquals(ports[3].device_owner, 'compute:nova')
        self.assertEquals(ports[3].fixed_ip_list, '10.0.0.4')
        self.assertEquals(ports[3].portId, '6ccfce1e-e37a-42db-9a94-65f50ec18060')
        self.assertEquals(ports[3].mac_address, 'FA:16:3E:E6:D7:3B')
        self.assertEquals(ports[3].status, 'ACTIVE')
        self.assertEquals(ports[3].title, '')
        self.assertEquals(ports[3].vif_type, 'ovs')

    def testFloatingIp(self):
        self.assertTrue(self._modeled)

        fips = self.d.getDeviceComponents(type='OpenStackInfrastructureFloatingIp')
        self.assertEquals(len(fips), 3)

        self.assertIsNone(fips[0].fixed_ip_address)
        self.assertEquals(fips[0].floating_ip_address, '172.24.4.4')
        self.assertEquals(fips[0].status, 'DOWN')
        self.assertEquals(fips[0].floatingipId, '733d3d80-3a29-4035-a333-577f1b60267c')

        self.assertEquals(fips[1].fixed_ip_address, '10.0.0.4')
        self.assertEquals(fips[1].floating_ip_address, '172.24.4.5')
        self.assertEquals(fips[1].status, 'ACTIVE')
        self.assertEquals(fips[1].floatingipId, 'd20b1cb0-4b52-4110-a784-cc73c913551e')

        self.assertIsNone(fips[2].fixed_ip_address)
        self.assertEquals(fips[2].floating_ip_address, '172.24.4.6')

    def testCinderService(self):
        self.assertTrue(self._modeled)

        cservices = self.d.getDeviceComponents(type='OpenStackInfrastructureCinderService')
        self.assertEquals(len(cservices), 3)

        self.assertEquals(cservices[0].title, "cinder-scheduler@osi-p (nova)")
        self.assertEquals(cservices[0].binary, "cinder-scheduler")
        self.assertTrue(cservices[0].enabled)
        self.assertEquals(cservices[0].operStatus, 'UP')

    def testVolume(self):
        self.assertTrue(self._modeled)

        volumes = self.d.getDeviceComponents(type='OpenStackInfrastructureVolume')
        self.assertEquals(len(volumes), 1)

        self.assertEquals(volumes[0].title, 'blueVolume')
        self.assertEquals(volumes[0].volumeId, "285fa789-ab57-4bd7-9a61-6b26684b4eb6")
        self.assertEquals(volumes[0].avzone, "nova")
        self.assertIsNone(volumes[0].sourceVolumeId)
        self.assertEquals(volumes[0].host, None)
        self.assertEquals(volumes[0].size, 100)
        self.assertEquals(volumes[0].bootable, 'FALSE')
        self.assertEquals(volumes[0].status, "ERROR")

    def testVolumeType(self):
        self.assertTrue(self._modeled)

        voltypes = self.d.getDeviceComponents(type='OpenStackInfrastructureVolType')
        self.assertEquals(len(voltypes), 1)

        self.assertEquals(voltypes[0].id, 'volType-45bbf67b-c222-4bc6-a3a1-97804d9b1d53')
        self.assertEquals(voltypes[0].title, 'iscsi')

    def testVolumeSnapshot(self):
        self.assertTrue(self._modeled)

        volsnaps = self.d.getDeviceComponents(type='OpenStackInfrastructureVolSnapshot')
        self.assertEquals(len(volsnaps), 0)

    def testCinderQuota(self):
        self.assertTrue(self._modeled)

        quotas = self.d.getDeviceComponents(type='OpenStackInfrastructureQuota')
        self.assertEquals(len(quotas), 3)

        self.assertEquals(quotas[0].id, 'quota-313da8e3ab19478e82be9c50e6b1a04b')
        self.assertEquals(quotas[1].id, 'quota-9afe0a3dc0414bff8c69a4f3474fafba')
        self.assertEquals(quotas[2].id, 'quota-d6a14c911aed48cfa9edc383ff85587f')
        self.assertEquals(quotas[0].tenant_name, 'admin')
        self.assertEquals(quotas[1].tenant_name, 'services')
        self.assertEquals(quotas[2].tenant_name, 'demo')
        self.assertEquals(quotas[0].snapshots, 10)
        self.assertEquals(quotas[1].snapshots, 10)
        self.assertEquals(quotas[2].snapshots, 10)


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestModel))
    return suite


if __name__ == "__main__":
    from zope.testrunner.runner import Runner
    runner = Runner(found_suites=[test_suite()])
    runner.run()
