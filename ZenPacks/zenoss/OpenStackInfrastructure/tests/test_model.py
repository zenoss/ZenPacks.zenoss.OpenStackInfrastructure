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
import json
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
from ZenPacks.zenoss.OpenStackInfrastructure import DeviceProxyComponent
from ZenPacks.zenoss.OpenStackInfrastructure import hostmap

unused(Globals)

crochet = setup_crochet()

MOCK_DNS = {
    "liberty.yichi.local": "10.0.2.34",
    "liberty.zenoss.local": "192.168.56.122",
    "liberty.zenoss": "192.168.56.122",
    "wily.zenoss.local": "192.168.56.110",
    "bugs.zenoss.local": "192.168.56.111",
    "foghorn.zenoss.local": "192.168.56.112",
    "leghorn.zenoss.local": "192.168.56.112",
    "host-10-0-0-1.openstacklocal.": "10.0.0.1",
    "host-10-0-0-2.openstacklocal.": "10.0.0.2",
    "host-10-0-0-3.openstacklocal.": "10.0.0.3",
    "host-172-24-4-226.openstacklocal.": "172.24.4.226",
    "overcloud-controller-1.localdomain": "10.88.0.100"
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

        self._loadBadHosts()
        self._loadZenossData()

    @crochet.wait_for(timeout=30)
    def _preprocessHosts(self, modeler, results):
        return modeler.preprocess_hosts(self.d, results)

    def _loadBadHosts(self):
        # liberty, wily, and bugs are in the wrong device class, and so
        # won't be claimable.

        device_name = 'liberty.zenoss'
        dc = self.dmd.Devices.createOrganizer('/Devices/Server/SSH/Linux')
        bad_liberty = dc.createInstance(device_name)
        bad_liberty.setProdState(1000)
        bad_liberty.setPerformanceMonitor('localhost')
        bad_liberty.setManageIp('1.22.33.44')
        bad_liberty.index_object()
        notify(IndexingEvent(bad_liberty))

        device_name = 'wily.zenoss.local'
        repeated_ip_device = dc.createInstance(device_name)
        repeated_ip_device.setProdState(1000)
        repeated_ip_device.setPerformanceMonitor('localhost')
        repeated_ip_device.setManageIp('192.168.56.110')
        repeated_ip_device.index_object()
        notify(IndexingEvent(repeated_ip_device))

        device_name = 'bugs.zenoss.local'
        wrong_dc = dc.createInstance(device_name)
        wrong_dc.setProdState(1000)
        wrong_dc.setPerformanceMonitor('localhost')
        wrong_dc.setManageIp('192.168.56.111')
        wrong_dc.index_object()
        notify(IndexingEvent(wrong_dc))

        dc = self.dmd.Devices.createOrganizer('/Devices/Server/SSH/Linux/NovaHost')
        device_name = 'foghorn.zenoss.local'
        foghorn_dc = dc.createInstance(device_name)
        foghorn_dc.setProdState(1000)
        foghorn_dc.setPerformanceMonitor('localhost')
        foghorn_dc.setManageIp('192.168.56.112')
        foghorn_dc.index_object()
        notify(IndexingEvent(foghorn_dc))

    def _loadZenossData(self):
        if hasattr(self, '_modeled'):
            return

        modeler = OpenStackInfrastructureModeler()
        with open(os.path.join(os.path.dirname(__file__),
                               'data',
                               'modeldata.json')) as json_file:
            results = json.load(json_file)

        self._preprocessHosts(modeler, results)

        for data_map in modeler.process(self.d, results, log):
            self.applyDataMap(self.d, data_map)

        self._modeled = True

    def testTenant(self):
        self.assertTrue(self._modeled)

        tenants = self.d.getDeviceComponents(type='OpenStackInfrastructureTenant')
        self.assertEquals(len(tenants), 3)
        self.assertEquals(tenants[0].endpoint.id, 'endpoint')
        self.assertEquals(tenants[0].endpoint.name(), 'demo')
        self.assertEquals(tenants[1].endpoint.id, 'endpoint')
        self.assertEquals(tenants[1].endpoint.name(), 'services')
        self.assertEquals(tenants[2].endpoint.id, 'endpoint')
        self.assertEquals(tenants[2].endpoint.name(), 'admin')
        self.assertEquals(tenants[0].floatingIps.id, 'floatingIps')
        self.assertEquals(tenants[0].floatingIps.name(), 'demo')
        self.assertEquals(tenants[1].floatingIps.id, 'floatingIps')
        self.assertEquals(tenants[1].floatingIps.name(), 'services')
        self.assertEquals(tenants[2].floatingIps.id, 'floatingIps')
        self.assertEquals(tenants[2].floatingIps.name(), 'admin')
        self.assertEquals(tenants[0].instances.id, 'instances')
        self.assertEquals(tenants[0].instances.name(), 'demo')
        self.assertEquals(tenants[1].instances.id, 'instances')
        self.assertEquals(tenants[1].instances.name(), 'services')
        self.assertEquals(tenants[2].instances.id, 'instances')
        self.assertEquals(tenants[2].instances.name(), 'admin')
        self.assertEquals(tenants[0].networks.id, 'networks')
        self.assertEquals(tenants[0].networks.name(), 'demo')
        self.assertEquals(tenants[1].networks.id, 'networks')
        self.assertEquals(tenants[1].networks.name(), 'services')
        self.assertEquals(tenants[2].networks.id, 'networks')
        self.assertEquals(tenants[2].networks.name(), 'admin')
        self.assertEquals(tenants[0].ports.id, 'ports')
        self.assertEquals(tenants[0].ports.name(), 'demo')
        self.assertEquals(tenants[1].ports.id, 'ports')
        self.assertEquals(tenants[1].ports.name(), 'services')
        self.assertEquals(tenants[2].ports.id, 'ports')
        self.assertEquals(tenants[2].ports.name(), 'admin')
        self.assertEquals(tenants[0].routers.id, 'routers')
        self.assertEquals(tenants[0].routers.name(), 'demo')
        self.assertEquals(tenants[1].routers.id, 'routers')
        self.assertEquals(tenants[1].routers.name(), 'services')
        self.assertEquals(tenants[2].routers.id, 'routers')
        self.assertEquals(tenants[2].routers.name(), 'admin')
        self.assertEquals(tenants[0].subnets.id, 'subnets')
        self.assertEquals(tenants[0].subnets.name(), 'demo')
        self.assertEquals(tenants[1].subnets.id, 'subnets')
        self.assertEquals(tenants[1].subnets.name(), 'services')
        self.assertEquals(tenants[2].subnets.id, 'subnets')
        self.assertEquals(tenants[2].subnets.name(), 'admin')
        self.assertEquals(tenants[0].volumes.id, 'volumes')
        self.assertEquals(tenants[0].volumes.name(), 'demo')
        self.assertEquals(tenants[1].volumes.id, 'volumes')
        self.assertEquals(tenants[1].volumes.name(), 'services')
        self.assertEquals(tenants[2].volumes.id, 'volumes')
        self.assertEquals(tenants[2].volumes.name(), 'admin')
        # backups not in 2.2.0 release. Comment it out
        # self.assertEquals(tenants[0].backups.id, 'backups')
        # self.assertEquals(tenants[0].backups.name(), 'demo')
        # self.assertEquals(tenants[1].backups.id, 'backups')
        # self.assertEquals(tenants[1].backups.name(), 'services')
        # self.assertEquals(tenants[2].backups.id, 'backups')
        # self.assertEquals(tenants[2].backups.name(), 'admin')
        self.assertEquals(tenants[0].volSnapshots.id, 'volSnapshots')
        self.assertEquals(tenants[0].volSnapshots.name(), 'demo')
        self.assertEquals(tenants[1].volSnapshots.id, 'volSnapshots')
        self.assertEquals(tenants[1].volSnapshots.name(), 'services')
        self.assertEquals(tenants[2].volSnapshots.id, 'volSnapshots')
        self.assertEquals(tenants[2].volSnapshots.name(), 'admin')
        self.assertEquals(tenants[0].quota.id, 'quota')
        self.assertEquals(tenants[0].quota.name(), 'demo')
        self.assertEquals(tenants[1].quota.id, 'quota')
        self.assertEquals(tenants[1].quota.name(), 'services')
        self.assertEquals(tenants[2].quota.id, 'quota')
        self.assertEquals(tenants[2].quota.name(), 'admin')

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
        self.assertEquals('zone-nova', avzones[0].id)
        self.assertEquals('nova', avzones[0].name())
        self.assertEquals('zone-internal', avzones[1].id)
        self.assertEquals('internal', avzones[1].name())
        self.assertEquals(avzones[0].endpoint.id, 'endpoint')
        self.assertEquals(avzones[0].endpoint.name(), 'nova')
        self.assertEquals(avzones[0].hosts.id, 'hosts')
        self.assertEquals(avzones[0].hosts.name(), 'nova')
        self.assertEquals(avzones[0].pools.id, 'pools')
        self.assertEquals(avzones[0].pools.name(), 'nova')
        self.assertEquals(avzones[1].endpoint.id, 'endpoint')
        self.assertEquals(avzones[1].endpoint.name(), 'internal')
        self.assertEquals(avzones[1].hosts.id, 'hosts')
        self.assertEquals(avzones[1].hosts.name(), 'internal')
        self.assertEquals(avzones[1].pools.id, 'pools')
        self.assertEquals(avzones[1].pools.name(), 'internal')

    def testFlavor(self):
        self.assertTrue(self._modeled)

        flavors = self.d.getDeviceComponents(type='OpenStackInfrastructureFlavor')
        self.assertEquals(len(flavors), 5)
        flavornames = [f.name() for f in flavors]
        flavorids = [f.id for f in flavors]

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
        self.assertEquals(flavors[0].get_instances()[0],
                          'server-0aa87c33-aa73-4c02-976b-321f5e2df205')

    def testImage(self):
        self.assertTrue(self._modeled)

        images = self.d.getDeviceComponents(type='OpenStackInfrastructureImage')
        self.assertEquals(len(images), 1)

        self.assertEquals('image-b5ac0c5f-bf91-4ab6-bcaa-d895a8df90bb',
                          images[0].id)
        self.assertEquals('cirros', images[0].name())

    def testInstance(self):
        self.assertTrue(self._modeled)

        instances = self.d.getDeviceComponents(
            type='OpenStackInfrastructureInstance')
        self.assertEquals(len(instances), 1)
        self.assertEquals('server-0aa87c33-aa73-4c02-976b-321f5e2df205',
                          instances[0].id)
        self.assertEquals('tiny1', instances[0].name())

    def testHost(self):
        self.assertTrue(self._modeled)

        hosts = self.d.getDeviceComponents(type='OpenStackInfrastructureHost')
        bugs = getHostObjectByName(hosts, 'bugs')
        wily = getHostObjectByName(hosts, 'wily')
        overcloud = getHostObjectByName(hosts, 'overcloud')

        self.assertEquals(len(hosts), 5)
        self.assertEquals(bugs.device().id,
                          'zenoss.OpenStackInfrastructure.testDevice')
        self.assertEquals(bugs.name(), 'bugs.zenoss.local')
        self.assertEquals(bugs.hypervisor.id, 'hypervisor')
        self.assertEquals(bugs.hypervisor.name(), 'bugs.zenoss.local')
        self.assertEquals(overcloud.device().id,
                          'zenoss.OpenStackInfrastructure.testDevice')
        self.assertEquals(overcloud.name(), 'overcloud-controller-1.localdomain')
        self.assertEquals(overcloud.hypervisor.id, 'hypervisor')
        self.assertEquals(overcloud.hypervisor.name(),
                          'overcloud-controller-1.localdomain')

        hostedSoftware = wily.hostedSoftware()[0]
        self.assertEquals(hostedSoftware.id,
                'service-nova-conductor-wily.zenoss.local-internal')

        self.assertEquals(hostedSoftware.orgComponent().id,
                'zone-internal')


    def testDeviceProxyIntegrity(self):
        self.assertTrue(self._modeled)
        hosts = self.d.getDeviceComponents(type='OpenStackInfrastructureHost')
        self.assertEquals(len(hosts), 5)
        bugs = getHostObjectByName(hosts, 'bugs')
        wily = getHostObjectByName(hosts, 'wily')
        liberty = getHostObjectByName(hosts, 'liberty')
        leghorn = getHostObjectByName(hosts, 'leghorn')

        # Ensure the following hosts don't have proxy_device():
        self.assertIsNone(wily.proxy_device())
        self.assertIsNone(bugs.proxy_device())
        self.assertIsNotNone(liberty.proxy_device())

        # Ensure the leghorn has foghorn as proxy_device():
        leghorn_proxy = leghorn.proxy_device()
        self.assertEquals(leghorn_proxy.id, 'foghorn.zenoss.local')
        self.assertEquals(leghorn_proxy.manageIp, '192.168.56.112')

        # Break the proxy device linkage by changing leghorn device's uuid
        old_uuid = leghorn.openstackProxyDeviceUUID
        IGlobalIdentifier(leghorn_proxy).setGUID('97e184b1-ed49-481e-bb7c-cce3bba1d171')

        # Test fixage of the proxy_device claim for leghorn:
        with FilteredLog(["zen.OpenStackDeviceProxyComponent"], ["but it is not linked back.  Disregarding linkage."]):
            self.assertEquals(leghorn.proxy_device(), leghorn_proxy)

        self.assertNotEquals(leghorn.openstackProxyDeviceUUID, old_uuid)


    def testHypervisor(self):
        self.assertTrue(self._modeled)

        hypervisors = self.d.getDeviceComponents(
            type='OpenStackInfrastructureHypervisor')
        self.assertEquals(len(hypervisors), 1)
        self.assertEquals(hypervisors[0].hypervisorId, 1)
        self.assertEquals(hypervisors[0].id, 'hypervisor-1')
        self.assertEquals(hypervisors[0].name(), 'liberty.zenoss.local.1')
        self.assertEquals(hypervisors[0].host.id, 'host')
        self.assertEquals(hypervisors[0].host.name(), 'liberty.zenoss.local.1')
        self.assertEquals(hypervisors[0].instances.id, 'instances')
        self.assertEquals(hypervisors[0].instances.name(), 'liberty.zenoss.local.1')
        self.assertEquals(hypervisors[0].endpoint.id, 'endpoint')
        self.assertEquals(hypervisors[0].endpoint.name(), 'liberty.zenoss.local.1')
        self.assertEquals(hypervisors[0].getPrimaryId(),
                          '/zport/dmd/Devices/OpenStack/Infrastructure' +
                          '/devices/zenoss.OpenStackInfrastructure.testDevice' +
                          '/components/hypervisor-1')

    def testNeutronAgent(self):
        self.assertTrue(self._modeled)

        agents = self.d.getDeviceComponents(type='OpenStackInfrastructureNeutronAgent')
        self.assertEquals(len(agents), 5)
        self.assertEquals(agents[0].id, "agent-ee6407f6-9b13-4df4-8da0-cb751c410af5")
        self.assertEquals(agents[0].title, 'L3 agent@liberty.zenoss.local')
        self.assertEquals(agents[0].agentId, "ee6407f6-9b13-4df4-8da0-cb751c410af5")
        self.assertEquals(agents[0].binary, 'neutron-l3-agent')
        self.assertTrue(agents[0].enabled)
        self.assertEquals(agents[0].operStatus, 'UP')
        self.assertEquals(agents[0].type, 'L3 agent')
        self.assertEquals(agents[1].id, "agent-f3b165ca-d869-4a1f-a8da-361f2177da5b")
        self.assertEquals(agents[1].title, 'Metadata agent@liberty.zenoss.local')
        self.assertEquals(agents[1].agentId, "f3b165ca-d869-4a1f-a8da-361f2177da5b")
        self.assertEquals(agents[1].binary, 'neutron-metadata-agent')
        self.assertTrue(agents[1].enabled)
        self.assertEquals(agents[1].operStatus, 'UP')
        self.assertEquals(agents[1].type, 'Metadata agent')
        self.assertEquals(agents[2].id, "agent-f9697d9c-580e-4917-8c87-1b69ab53e5a6")
        self.assertEquals(agents[2].title, 'Open vSwitch agent@liberty.zenoss.local')
        self.assertEquals(agents[2].agentId, "f9697d9c-580e-4917-8c87-1b69ab53e5a6")
        self.assertEquals(agents[2].binary, 'neutron-openvswitch-agent')
        self.assertTrue(agents[2].enabled)
        self.assertEquals(agents[2].operStatus, 'UP')
        self.assertEquals(agents[2].type, 'Open vSwitch agent')
        self.assertEquals(agents[3].id, "agent-fade4d15-487c-4998-ac80-bff91b4532e9")
        self.assertEquals(agents[3].title, 'DHCP agent@liberty.zenoss.local')
        self.assertEquals(agents[3].agentId, "fade4d15-487c-4998-ac80-bff91b4532e9")
        self.assertEquals(agents[3].binary, 'neutron-dhcp-agent')
        self.assertTrue(agents[3].enabled)
        self.assertEquals(agents[3].operStatus, 'UP')
        self.assertEquals(agents[3].type, 'DHCP agent')
        self.assertEquals(agents[4].id, "agent-37c80256-d843-45c3-a9b6-fb0fde13ac89")
        self.assertEquals(agents[4].title,
                          'Loadbalancer agent@overcloud-controller-1.localdomain')
        self.assertEquals(agents[4].agentId, "37c80256-d843-45c3-a9b6-fb0fde13ac89")
        self.assertEquals(agents[4].binary, 'f5-oslbaasv1-agent')
        self.assertTrue(agents[4].enabled)
        self.assertEquals(agents[4].operStatus, 'UP')
        self.assertEquals(agents[4].type, 'Loadbalancer agent')

    def testNetwork(self):
        self.assertTrue(self._modeled)

        networks = self.d.getDeviceComponents(type='OpenStackInfrastructureNetwork')
        self.assertEquals(len(networks), 2)
        self.assertEquals(networks[0].title, 'private')
        self.assertEquals(networks[0].netId, "7a2d66f2-35e6-4459-92b9-260411a39039")
        self.assertFalse(networks[0].netExternal)
        self.assertEquals(networks[0].netStatus, 'ACTIVE')
        self.assertEquals(networks[0].netType, 'VXLAN')
        self.assertTrue(networks[0].admin_state_up)
        self.assertEquals(networks[1].title, 'public')
        self.assertEquals(networks[1].netId, "a13b2c35-d734-4021-9850-432dfa7fa7a3")
        self.assertTrue(networks[1].netExternal)
        self.assertEquals(networks[1].netStatus, 'ACTIVE')
        self.assertEquals(networks[1].netType, 'VXLAN')
        self.assertTrue(networks[1].admin_state_up)

    def testSubnet(self):
        self.assertTrue(self._modeled)

        subnets = self.d.getDeviceComponents(type='OpenStackInfrastructureSubnet')
        self.assertEquals(len(subnets), 2)
        self.assertEquals(subnets[0].title, 'private_subnet')
        self.assertEquals(subnets[0].cidr, '10.0.0.0/24')
        self.assertEquals(len(subnets[0].dns_nameservers), 0)
        self.assertEquals(subnets[0].gateway_ip, '10.0.0.1')
        self.assertEquals(subnets[0].subnetId,
                          '85085b15-4f2f-4457-ae31-0cfe1d5d301c')

        self.assertEquals(subnets[1].title, 'public_subnet')
        self.assertEquals(subnets[1].cidr, '172.24.4.224/28')
        self.assertEquals(len(subnets[1].dns_nameservers), 0)
        self.assertEquals(subnets[1].gateway_ip, '172.24.4.225')
        self.assertEquals(subnets[1].subnetId,
                          'efe34b3a-a35c-4a0e-9769-e1fd79d7ca2d')

    def testRouter(self):
        self.assertTrue(self._modeled)

        routers = self.d.getDeviceComponents(type='OpenStackInfrastructureRouter')
        self.assertEquals(len(routers), 1)
        self.assertEquals(routers[0].routerId,
                          '88b70ee0-4204-4a88-b9c5-dd49588d5c1a')
        self.assertTrue(routers[0].admin_state_up)
        self.assertEquals(routers[0].gateways[0], '172.24.4.226')
        self.assertEquals(len(routers[0].routes), 0)
        self.assertEquals(routers[0].status, 'ACTIVE')
        self.assertEquals(routers[0].title, 'router1')

    def testPort(self):
        self.assertTrue(self._modeled)

        ports = self.d.getDeviceComponents(type='OpenStackInfrastructurePort')
        self.assertEquals(len(ports), 4)
        self.assertTrue(ports[0].admin_state_up)
        self.assertEquals(ports[0].device_owner, 'network:router_gateway')
        self.assertEquals(ports[0].fixed_ip_list, '172.24.4.226')
        self.assertEquals(ports[0].portId, '027d0591-d2d7-412c-977e-5a42fd2d0277')
        self.assertEquals(ports[0].mac_address, 'FA:16:3E:1F:6A:CC')
        self.assertEquals(ports[0].status, 'DOWN')
        self.assertEquals(ports[0].title, '')
        self.assertEquals(ports[0].vif_type, 'ovs')
        self.assertTrue(ports[1].admin_state_up)
        self.assertEquals(ports[1].device_owner, 'compute:nova')
        self.assertEquals(ports[1].fixed_ip_list, '10.0.0.3')
        self.assertEquals(ports[1].portId, '2ce7575f-5368-4a33-b67d-17b4718cf77c')
        self.assertEquals(ports[1].mac_address, 'FA:16:3E:04:6D:E6')
        self.assertEquals(ports[1].status, 'ACTIVE')
        self.assertEquals(ports[1].title, '')
        self.assertEquals(ports[1].vif_type, 'ovs')
        self.assertTrue(ports[2].admin_state_up)
        self.assertEquals(ports[2].device_owner, 'network:router_interface')
        self.assertEquals(ports[2].fixed_ip_list, '10.0.0.1')
        self.assertEquals(ports[2].portId, '65fae58a-3d6b-4e8d-acc1-f9a43c0b7d31')
        self.assertEquals(ports[2].mac_address, 'FA:16:3E:BF:BE:AF')
        self.assertEquals(ports[2].status, 'ACTIVE')
        self.assertEquals(ports[2].title, '')
        self.assertEquals(ports[2].vif_type, 'ovs')
        self.assertTrue(ports[3].admin_state_up)
        self.assertEquals(ports[3].device_owner, 'network:dhcp')
        self.assertEquals(ports[3].fixed_ip_list, '10.0.0.2')
        self.assertEquals(ports[3].portId, 'd95c191c-f9fc-4933-9d13-af8f7524046a')
        self.assertEquals(ports[3].mac_address, 'FA:16:3E:FF:E5:8E')
        self.assertEquals(ports[3].status, 'ACTIVE')
        self.assertEquals(ports[3].title, '')
        self.assertEquals(ports[3].vif_type, 'ovs')

    def testFloatingIp(self):
        self.assertTrue(self._modeled)

        fips = self.d.getDeviceComponents(type='OpenStackInfrastructureFloatingIp')
        self.assertEquals(len(fips), 4)
        self.assertIsNone(fips[0].fixed_ip_address)
        self.assertEquals(fips[0].floating_ip_address, '10.239.180.102')
        self.assertEquals(fips[0].status, 'DOWN')
        self.assertEquals(fips[0].floatingipId, '7fc91b6e-6135-4ca3-932b-7f437c77ff45')
        self.assertIsNone(fips[1].fixed_ip_address)
        self.assertEquals(fips[1].floating_ip_address, '10.239.180.103')
        self.assertEquals(fips[1].status, 'DOWN')
        self.assertEquals(fips[1].floatingipId, '8a5b5177-4100-445e-b085-836276a3e0c6')
        self.assertIsNone(fips[2].fixed_ip_address)
        self.assertEquals(fips[2].floating_ip_address, '10.239.180.101')
        self.assertEquals(fips[2].status, 'ACTIVE')
        self.assertEquals(fips[2].floatingipId, 'c3d558d1-5ed7-4488-9529-1ed8d47412c1')
        self.assertIsNone(fips[3].fixed_ip_address)
        self.assertEquals(fips[3].floating_ip_address, '10.239.180.100')
        self.assertEquals(fips[3].status, 'DOWN')
        self.assertEquals(fips[3].floatingipId, 'd61d4dff-b941-4359-bd95-db6110364796')

    def testCinderService(self):
        self.assertTrue(self._modeled)

        cservices = self.d.getDeviceComponents(type='OpenStackInfrastructureCinderService')
        self.assertEquals(len(cservices), 3)
        self.assertEquals(cservices[0].title, "cinder-backup@liberty.zenoss.local (nova)")
        self.assertEquals(cservices[0].binary, "cinder-backup")
        self.assertFalse(cservices[0].enabled)
        self.assertEquals(cservices[0].operStatus, 'DOWN')
        self.assertEquals(cservices[1].title, "cinder-scheduler@liberty.zenoss.local (nova)")
        self.assertEquals(cservices[1].binary, "cinder-scheduler")
        self.assertTrue(cservices[1].enabled)
        self.assertEquals(cservices[1].operStatus, 'UP')
        self.assertEquals(cservices[2].title, "cinder-volume@liberty.zenoss.local (nova)")
        self.assertEquals(cservices[2].binary, "cinder-volume")
        self.assertTrue(cservices[2].enabled)
        self.assertEquals(cservices[2].operStatus, 'UP')

    def testCinderAPI(self):
        self.assertTrue(self._modeled)

        capis = self.d.getDeviceComponents(type='OpenStackInfrastructureCinderAPI')
        self.assertEquals(len(capis), 1)
        self.assertEquals(capis[0].id,
                          'service-cinder-api-liberty.zenoss.local-RegionOne')
        self.assertEquals(capis[0].title,
                          'cinder-api@liberty.zenoss.local (RegionOne)')
        self.assertEquals(capis[0].binary, 'cinder-api')

    def testVolume(self):
        self.assertTrue(self._modeled)

        volumes = self.d.getDeviceComponents(type='OpenStackInfrastructureVolume')
        self.assertEquals(len(volumes), 2)
        self.assertEquals(volumes[0].title, 'vol-GB1-2'),
        self.assertEquals(volumes[0].volumeId,
                          "c3aabf8c-9f44-41c7-b962-e50e1f5936ff")
        self.assertEquals(volumes[0].avzone, "nova"),
        self.assertEquals(volumes[0].created_at, "2015-12-16 19:44:25.000000"),
        self.assertIsNone(volumes[0].sourceVolumeId),
        self.assertEquals(volumes[0].host, "liberty.zenoss.local@lvm#lvm"),
        self.assertEquals(volumes[0].size, 1),
        self.assertEquals(volumes[0].bootable, 'FALSE'),
        self.assertEquals(volumes[0].status, "AVAILABLE"),
        self.assertEquals(volumes[1].title, 'vol-GB1'),
        self.assertEquals(volumes[1].volumeId,
                          "281a7105-935a-4bcf-a4b5-cf5e652d2daa")
        self.assertEquals(volumes[1].avzone, "nova"),
        self.assertEquals(volumes[1].created_at, "2015-10-30 18:15:46.000000"),
        self.assertIsNone(volumes[1].sourceVolumeId),
        self.assertEquals(volumes[1].host, "liberty.zenoss.local@lvm#lvm"),
        self.assertEquals(volumes[1].size, 1),
        self.assertEquals(volumes[1].bootable, 'FALSE'),
        self.assertEquals(volumes[1].status, "IN-USE"),
        self.assertEquals(volumes[1].instance.id, "instance"),
        self.assertEquals(volumes[1].instance.name(), "vol-GB1"),

    def testVolumeType(self):
        self.assertTrue(self._modeled)

        voltypes = self.d.getDeviceComponents(type='OpenStackInfrastructureVolType')
        self.assertEquals(len(voltypes), 2)
        self.assertEquals(voltypes[0].id, 'volType-033af14f-b609-45e3-aed2-5b2e02d44c8f')
        self.assertEquals(voltypes[0].title, 'ceph')
        self.assertEquals(voltypes[1].id, 'volType-6e2e993c-110e-4aaf-a79b-a44acc533051')
        self.assertEquals(voltypes[1].title, 'lvm')

    def testVolumeSnapshot(self):
        self.assertTrue(self._modeled)

        volsnaps = self.d.getDeviceComponents(type='OpenStackInfrastructureVolSnapshot')
        self.assertEquals(len(volsnaps), 1)
        self.assertEquals(volsnaps[0].id, "snapshot-7bae1e24-47db-4d63-90e1-a5b02d112fb1"),
        self.assertEquals(volsnaps[0].title, "vol-GB1-snapshot"),
        self.assertEquals(volsnaps[0].created_at, "2015-12-16 19:45:59.000000"),
        self.assertEquals(volsnaps[0].size, 1),
        self.assertEquals(volsnaps[0].description, "Linux volume 1 GB snapshot"),
        self.assertEquals(volsnaps[0].status, "AVAILABLE"),

    def testCinderQuota(self):
        self.assertTrue(self._modeled)

        quotas = self.d.getDeviceComponents(type='OpenStackInfrastructureQuota')
        self.assertEquals(len(quotas), 3)
        self.assertEquals(quotas[0].id, 'quota-demo')
        self.assertEquals(quotas[1].id, 'quota-services')
        self.assertEquals(quotas[2].id, 'quota-admin')
        self.assertEquals(quotas[0].tenant_name, 'demo')
        self.assertEquals(quotas[1].tenant_name, 'services')
        self.assertEquals(quotas[2].tenant_name, 'admin')
        self.assertEquals(quotas[0].volumes, 10)
        self.assertEquals(quotas[1].volumes, 10)
        self.assertEquals(quotas[2].volumes, 10)
        self.assertEquals(quotas[0].bytes, 1000)
        self.assertEquals(quotas[1].bytes, 1000)
        self.assertEquals(quotas[2].bytes, 1000)
        self.assertEquals(quotas[0].backup_bytes, 1000)
        self.assertEquals(quotas[1].backup_bytes, 1000)
        self.assertEquals(quotas[2].backup_bytes, 1000)
        self.assertEquals(quotas[0].snapshots, 10)
        self.assertEquals(quotas[1].snapshots, 10)
        self.assertEquals(quotas[2].snapshots, 10)
        self.assertEquals(quotas[0].backups, 10)
        self.assertEquals(quotas[1].backups, 10)
        self.assertEquals(quotas[2].backups, 10)


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestModel))
    return suite


if __name__ == "__main__":
    from zope.testrunner.runner import Runner
    runner = Runner(found_suites=[test_suite()])
    runner.run()
