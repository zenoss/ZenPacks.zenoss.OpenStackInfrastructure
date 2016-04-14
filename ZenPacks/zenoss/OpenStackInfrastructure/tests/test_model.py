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
log = logging.getLogger('zen.OpenStackInfrastructure')

from zope.event import notify
from Products.Zuul.catalog.events import IndexingEvent
from Products.Five import zcml

from Products.DataCollector.ApplyDataMap import ApplyDataMap
from Products.ZenTestCase.BaseTestCase import BaseTestCase

from ZenPacks.zenoss.OpenStackInfrastructure.modeler.plugins.zenoss.OpenStackInfrastructure \
    import OpenStackInfrastructure as OpenStackInfrastructureModeler

CLOUDSTACK_ICON = '/++resource++cloudstack/img/cloudstack.png'


class TestModel(BaseTestCase):
    def afterSetUp(self):
        super(TestModel, self).afterSetUp()

        dc = self.dmd.Devices.createOrganizer('/Devices/OpenStack/Infrastructure')

        dc.setZenProperty('zPythonClass', 'ZenPacks.zenoss.OpenStackInfrastructure.Endpoint')
        dc.setZenProperty('zOpenStackHostDeviceClass', '/Server/SSH/Linux/NovaHost')
        dc.setZenProperty('zOpenStackRegionName', 'RegionOne')
        dc.setZenProperty('zOpenStackNovaApiHosts', [])
        dc.setZenProperty('zOpenStackExtraHosts', [])
        # dc.setZenProperty('zPythonClass', 'ZenPacks.zenoss.OpenStackInfrastructureModeler.Cloud')

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
        if hasattr(self, '_loaded'):
            return

        modeler = OpenStackInfrastructureModeler()
        with open(os.path.join(os.path.dirname(__file__),
                               'data',
                               'modeldata.json')) as json_file:
            results = json.load(json_file)

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

        instances = self.d.getDeviceComponents(type='OpenStackInfrastructureInstance')
        self.assertEquals(len(instances), 1)
        self.assertEquals('server-0aa87c33-aa73-4c02-976b-321f5e2df205',
                          instances[0].id)
        self.assertEquals('tiny1', instances[0].name())

    def testHost(self):
        self.assertTrue(self._modeled)

        hosts = self.d.getDeviceComponents(type='OpenStackInfrastructureHost')
        self.assertEquals(len(hosts), 1)
        hypervisor = hosts[0].hypervisor
        self.assertEquals(hosts[0].device().id,
                          'zenoss.OpenStackInfrastructure.testDevice')
        self.assertEquals(hosts[0].name(), 'liberty.zenoss.local')
        self.assertEquals(hypervisor.id, 'hypervisor')
        self.assertEquals(hypervisor.name(), 'liberty.zenoss.local')

    def testHypervisor(self):
        self.assertTrue(self._modeled)

        hypervisors = self.d.getDeviceComponents(type='OpenStackInfrastructureHypervisor')
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
        self.assertEquals(1, 1)

    def testNetwork(self):
        self.assertEquals(1, 1)

    def testSubnet(self):
        self.assertEquals(1, 1)

    def testRouter(self):
        self.assertEquals(1, 1)

    def testPort(self):
        self.assertEquals(1, 1)

    def testFloatingIp(self):
        self.assertEquals(1, 1)

    def testCinderService(self):
        self.assertEquals(1, 1)

    def testCinderAPI(self):
        self.assertEquals(1, 1)

    def testVolume(self):
        self.assertEquals(1, 1)

    def testVolumeTypes(self):
        self.assertTrue(self._modeled)

        voltypes = self.d.getDeviceComponents(type='OpenStackInfrastructureVolType')
        self.assertEquals(len(voltypes), 2)
        self.assertEquals(voltypes[0].id, 'volType-033af14f-b609-45e3-aed2-5b2e02d44c8f')
        self.assertEquals(voltypes[0].title, 'ceph')
        self.assertEquals(voltypes[1].id, 'volType-6e2e993c-110e-4aaf-a79b-a44acc533051')
        self.assertEquals(voltypes[1].title, 'lvm')

    def testSnapshot(self):
        self.assertEquals(1, 1)

    def testVolumePools(self):
        self.assertEquals(1, 1)

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
