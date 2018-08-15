#!/usr/bin/env python

##############################################################################
#
# Copyright (C) Zenoss, Inc. 2018, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

# These tests pre-create devices similarly to how the CiscoVIM zenpack would,
# and verify that the host components get linked up correctly.  In partciular,
# it verifies that hostmap and proxy_device create the expected components
# and link to the expected devices.

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('zen.OpenStackInfrastructure')

import Globals

import re
from twisted.internet import defer
from zope.event import notify
from Products.Zuul.catalog.events import IndexingEvent
from Products.ZenTestCase.BaseTestCase import BaseTestCase

from Products.ZenModel import Device
from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import addContained, setup_crochet
from ZenPacks.zenoss.OpenStackInfrastructure import hostmap
from ZenPacks.zenoss.OpenStackInfrastructure.hostmap import HostMap
from ZenPacks.zenoss.OpenStackInfrastructure.Host import Host
from ZenPacks.zenoss.OpenStackInfrastructure.services.OpenStackService import OpenStackService

crochet = setup_crochet()

MOCK_DNS = {
    'host1': '1.2.3.4',
    'host1.example.com': '1.2.3.4',
    'host1.test.com': '1.2.3.4',
    'host2': '1.2.3.5',
    'host2.example.com': '1.2.3.5',
    'host2.test.com': '1.2.3.5'
}        


class TestOpenStackService(BaseTestCase):
    disableLogging = False

    def afterSetUp(self):
        super(TestOpenStackService, self).afterSetUp()

        dc = self.dmd.Devices.createOrganizer('/Devices/OpenStack/Infrastructure')
        dc.setZenProperty('zPythonClass', 'ZenPacks.zenoss.OpenStackInfrastructure.Endpoint')
        dc.setZenProperty('zOpenStackHostDeviceClass', '/Server/SSH/Linux/NovaHost')
        dc.setZenProperty('zOpenStackHostLocalDomain', '')

        self.pc = self.dmd.Processes.manage_addOSProcessClass('ceilometer-collector')

        self.d = dc.createInstance('zenoss.OpenStackInfrastructure.testDevice')
        self.d.setPerformanceMonitor('localhost')                
        self.linux_dc = self.dmd.Devices.createOrganizer('/Server/SSH/Linux/NovaHost')
        self.hostmap = HostMap()
        self.service = OpenStackService(self.dmd, 'localhost')

        # mock out DNS for these tests
        def resolve_names(names):
            result = {}
            for name in names:
                result[name] = MOCK_DNS.get(name)
            return defer.maybeDeferred(lambda: result)

        self._real_resolve_names = hostmap.resolve_names
        hostmap.resolve_names = resolve_names

        self._real_getHostByName = Device.getHostByName
        Device.getHostByName = lambda x: MOCK_DNS.get(x)

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

    def tearDown(self):
        super(TestOpenStackService, self).tearDown()
        Device.getHostByName = self._real_getHostByName
        hostmap.resolve_names = self._real_resolve_names


    @crochet.wait_for(timeout=30)
    def perform_mapping(self):
        # This has to be run through the twisted reactor.
        return self.hostmap.perform_mapping()

    def create_hosts_from_hostmap(self, set_ips=False):
        hosts = []
        for host_id in self.hostmap.all_hostids():
            host = Host(host_id)
            host.title = self.hostmap.get_hostname_for_hostid(host_id)
            host.hostname = self.hostmap.get_hostname_for_hostid(host_id)
            short_hostname = re.sub(r'\..*', '', host.hostname)
            host.hostfqdn = short_hostname + ".example.com"
            host.hostlocalname = short_hostname + ".local"
            if set_ips:
                host.host_ip = self.hostmap.get_ip_for_hostid(host_id)  
            else:
                host.host_ip = None
            host = addContained(self.d, "components", host)
            host.index_object()
            hosts.append(host)
        return hosts


    def test_expected_ceilometer_heartbeats(self):

        self.hostmap.add_hostref("host1", source="nova services")
        self.hostmap.add_hostref("host2", source="nova services")
        self.hostmap.add_hostref("host1.example.com", source="something else")
        self.hostmap.add_hostref("host2.example.com", source="something else")
        self.hostmap.add_hostref("host1.test.com", source="something else")
        self.hostmap.add_hostref("host2.test.com", source="something else")

        self.perform_mapping()
        self.d.set_host_mappings(self.hostmap.freeze_mappings())

        hosts = self.create_hosts_from_hostmap(set_ips=True)

        for host in self.d.components():
            # create the proxy devices
            device = host.proxy_device()
            self.assertIsNone(device)            
            device = host.create_proxy_device()
            self.assertIsNotNone(device)

            # Change the device title so we can detect it later.
            device.title = 'device-' + device.titleOrId()
            # And the ceilometer-collector process running on that linux device
            device.os.addOSProcess('/zport/dmd/Processes/osProcessClasses/ceilometer-collector', "ceilometer-collector", True)
            device.os.processes()[0].index_object()

        # Now invoke expected_ceilometer_heartbeats and see what we get:
        expected = self.service.remote_expected_ceilometer_heartbeats(self.d.id)

        host1_expected = [x for x in expected if 'host1' in x['hostnames']][0]
        host2_expected = [x for x in expected if 'host2' in x['hostnames']][0]

        self.assertIsNotNone(host1_expected)
        self.assertIsNotNone(host2_expected)
        self.assertIn('ceilometer-collector', host1_expected['processes'])
        self.assertIn('ceilometer-collector', host2_expected['processes'])

        # should be pretty much the same- we'll make sure they have the same
        # number of results, then only dive down on one of them.
        self.assertEquals(len(host1_expected['hostnames']), len(host2_expected['hostnames']))

        # host.hostname
        self.assertIn('host1', host1_expected['hostnames'])

        # host.hostfqdn
        self.assertIn('host1.example.com', host1_expected['hostnames'])

        # host.hostlocalname
        self.assertIn('host1.local', host1_expected['hostnames'])

        # proxy device title
        self.assertIn('device-host1.example.com', host1_expected['hostnames'])

        # hostrefs
        self.assertIn('host1.test.com', host1_expected['hostnames'])


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestOpenStackService))
    return suite


if __name__ == "__main__":
    from zope.testrunner.runner import Runner
    runner = Runner(found_suites=[test_suite()])
    runner.run()
