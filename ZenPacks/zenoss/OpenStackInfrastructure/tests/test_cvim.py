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

from twisted.internet import defer
from zope.event import notify
from Products.Zuul.catalog.events import IndexingEvent
from Products.ZenTestCase.BaseTestCase import BaseTestCase

from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import addContained, setup_crochet, FilteredLog
from ZenPacks.zenoss.OpenStackInfrastructure.hostmap import HostMap
from ZenPacks.zenoss.OpenStackInfrastructure.Host import Host

crochet = setup_crochet()


class TestCVIM(BaseTestCase):
    disableLogging = False

    def afterSetUp(self):
        super(TestCVIM, self).afterSetUp()

        dc = self.dmd.Devices.createOrganizer('/Devices/OpenStack/Infrastructure')
        dc.setZenProperty('zPythonClass', 'ZenPacks.zenoss.OpenStackInfrastructure.Endpoint')
        dc.setZenProperty('zOpenStackHostDeviceClass', '/Server/SSH/Linux/NovaHost')
        dc.setZenProperty('zOpenStackHostLocalDomain', '')

        self.d = dc.createInstance('zenoss.OpenStackInfrastructure.testDevice')
        self.linux_dc = self.dmd.Devices.createOrganizer('/Server/SSH/Linux/NovaHost')
        self.hostmap = HostMap()

    @crochet.wait_for(timeout=30)
    def perform_mapping(self):
        # This has to be run through the twisted reactor.
        return self.hostmap.perform_mapping()

    def create_hosts_from_hostmap(self, set_ips=False):
        hosts = []
        for host_id in self.hostmap.all_hostids():
            host = Host(host_id)
            host.title = self.hostmap.get_hostname_for_hostid(host_id)
            if set_ips:
                host.host_ip = self.hostmap.get_ip_for_hostid(host_id)
            else:
                host.host_ip = None
            hosts.append(addContained(self.d, "components", host))
        return hosts


    def testHostMap31(self):
        # initialize a HostMap with data consistent with what we have seen in a 
        # test pod using CiscoVIM 3.1

        hostmap = self.hostmap
        hostmap.add_hostref("NFVI-MICROPOD-node-1", source="nova services")
        hostmap.add_hostref("NFVI-MICROPOD-node-2", source="nova services")
        hostmap.add_hostref("NFVI-MICROPOD-node-3", source="nova services")
        hostmap.add_hostref("NFVI-MICROPOD-New-compute-1", source="nova services")
        hostmap.add_hostref("NFVI-MICROPOD-New-compute-2", source="nova services")

        # Ensure that no names will resolve, then perform the mapping.
        hostmap.resolve_names = lambda: {}        
        self.perform_mapping()

        # make sure the host hostnames look right.
        self.assertEquals(hostmap.get_hostname_for_hostid(hostmap.get_hostid("NFVI-MICROPOD-node-1")), "nfvi-micropod-node-1")
        self.assertEquals(hostmap.get_hostname_for_hostid(hostmap.get_hostid("NFVI-MICROPOD-node-2")), "nfvi-micropod-node-2")
        self.assertEquals(hostmap.get_hostname_for_hostid(hostmap.get_hostid("NFVI-MICROPOD-node-3")), "nfvi-micropod-node-3")
        self.assertEquals(hostmap.get_hostname_for_hostid(hostmap.get_hostid("NFVI-MICROPOD-New-compute-1")), "nfvi-micropod-new-compute-1")
        self.assertEquals(hostmap.get_hostname_for_hostid(hostmap.get_hostid("NFVI-MICROPOD-New-compute-2")), "nfvi-micropod-new-compute-2")

        # No IPs in this case.
        self.assertEquals(hostmap.get_ip_for_hostid(hostmap.get_hostid("NFVI-MICROPOD-node-1")), None)
        self.assertEquals(hostmap.get_ip_for_hostid(hostmap.get_hostid("NFVI-MICROPOD-node-2")), None)
        self.assertEquals(hostmap.get_ip_for_hostid(hostmap.get_hostid("NFVI-MICROPOD-node-3")), None)
        self.assertEquals(hostmap.get_ip_for_hostid(hostmap.get_hostid("NFVI-MICROPOD-New-compute-1")), None)
        self.assertEquals(hostmap.get_ip_for_hostid(hostmap.get_hostid("NFVI-MICROPOD-New-compute-2")), None)


    def testHostProxyDevices31(self):
        # This test case ceates a series of host components and devices comparable
        # to those created by the CiscoVIM zenpack, version 3.1.   In this
        # configuration, every host component is has a hard-coded ID and a
        # pre-created linux device with the same name and the correct
        # IP.   The ID will be the same, minus the 'host-' prefix used on
        # host components.  DNS is not necessarily available to the openstack
        # modeler, so host.host_ip may not be populated.

        # Matching will be done based on the ID matching the title of the host
        # component.
           
        # hostnames are responded by the nova-services API are mixed case and
        # not DNS-resolvable.
        self.hostmap.add_hostref("NFVI-MICROPOD-node-1", source="nova services")
        self.hostmap.add_hostref("NFVI-MICROPOD-node-2", source="nova services")
        self.hostmap.add_hostref("NFVI-MICROPOD-node-3", source="nova services")
        self.hostmap.add_hostref("NFVI-MICROPOD-New-compute-1", source="nova services")
        self.hostmap.add_hostref("NFVI-MICROPOD-New-compute-2", source="nova services")

        # CiscoVIM uses zOpenStackHostMapToId to hardcode the component IDs:
        self.hostmap.assert_host_id('NFVI-MICROPOD-node-1', 'host-linux-0c5b56e1-583a-4590-a0f0-16d7dab30e58')
        self.hostmap.assert_host_id('NFVI-MICROPOD-node-3', 'host-linux-52e16fe2-45c2-4c84-94b9-d64639a11840')
        self.hostmap.assert_host_id('NFVI-MICROPOD-New-compute-2', 'host-linux-53e47e8f-0510-4b4d-91b3-4634d0ef0b59')
        self.hostmap.assert_host_id('NFVI-MICROPOD-node-2', 'host-linux-9869a1db-b0cd-40fb-9646-34dd4a898d29')
        self.hostmap.assert_host_id('NFVI-MICROPOD-New-compute-1', 'host-linux-dd5e80cf-4344-4308-9334-f15df4d2c7ed')

        # No names will resolve
        self.hostmap.resolve_names = lambda: {}        
        self.perform_mapping()

        # Now we create the same host components that the modeler would.
        # (in this case, none of the hostnames are resolvable)
        hosts = self.create_hosts_from_hostmap(set_ips=False)

        # And pre-create the linux devices as CiscoVIM would
        with FilteredLog(["zen.Device"], ["IP address has been set to"]):
            device = self.linux_dc.createInstance("linux-0c5b56e1-583a-4590-a0f0-16d7dab30e58")
            device.title = 'NFVI-MICROPOD-node-1'
            device.setManageIp('192.168.202.10')
            device = self.linux_dc.createInstance("linux-9869a1db-b0cd-40fb-9646-34dd4a898d29")
            device.title = 'NFVI-MICROPOD-node-2'
            device.setManageIp('192.168.202.12')
            device = self.linux_dc.createInstance("linux-52e16fe2-45c2-4c84-94b9-d64639a11840")
            device.title = 'NFVI-MICROPOD-node-3'
            device.setManageIp('192.168.202.11')
            device = self.linux_dc.createInstance("linux-dd5e80cf-4344-4308-9334-f15df4d2c7ed")
            device.title = 'NFVI-MICROPOD-New-compute-1'
            device.setManageIp('192.168.202.13')
            device = self.linux_dc.createInstance("linux-53e47e8f-0510-4b4d-91b3-4634d0ef0b59")
            device.title = 'NFVI-MICROPOD-New-compute-2'
            device.setManageIp('192.168.202.14')

        # Only the 5 pre-created host should exist..
        self.assertEquals(self.linux_dc.devices.countObjects(), 5)

        for host in self.d.components():
            # Every host should have a proxy device..
            device = host.proxy_device()
            self.assertIsNotNone(device)

            # And the id should equal the name (in this case)
            self.assertEquals(device.id, host.name())

        # Make sure it didn't create any new devices!
        self.assertEquals(self.linux_dc.devices.countObjects(), 5)

        # Now create another host that would try to claim a device that
        # is already claimed.   Make sure it doesn't succeed.
        host = Host('abc')
        host.title = "linux-53e47e8f-0510-4b4d-91b3-4634d0ef0b59"   # (same as NFVI-MICROPOD-New-compute-2)
        host = addContained(self.d, "components", host)

        # Make sure it doesn't find a host...
        device = host.proxy_device()
        self.assertIsNone(device, None)

        # And that it can't create one either, since the ID is already in use.
        with FilteredLog(['zen.OpenStackDeviceProxyComponent'],
                         ["Adding device for OpenStackInfrastructureHost", 
                          "a device with that ID already exists"]):
            device = host.create_proxy_device()
        self.assertIsNone(device, None)


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestCVIM))
    return suite


if __name__ == "__main__":
    from zope.testrunner.runner import Runner
    runner = Runner(found_suites=[test_suite()])
    runner.run()
