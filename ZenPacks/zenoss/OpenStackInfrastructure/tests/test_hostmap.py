#!/usr/bin/env python

##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016-2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
Unit tests for hostmap
'''

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('zen.OpenStack')

import Globals
from Products.ZenTestCase.BaseTestCase import BaseTestCase
from Products.ZenUtils.Utils import unused

from ZenPacks.zenoss.OpenStackInfrastructure import hostmap
from ZenPacks.zenoss.OpenStackInfrastructure.hostmap import HostMap
from ZenPacks.zenoss.OpenStackInfrastructure.Host import Host
from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import setup_crochet, addContained

from twisted.internet import defer

unused(Globals)

crochet = setup_crochet()


class TestHostMap(BaseTestCase):
    '''
    Test suite for HostMap
    '''

    disableLogging = False

    def setUp(self):
        super(TestHostMap, self).setUp()

        def resolve_names(names):
            return defer.maybeDeferred(lambda: {
                'test1': '1.2.3.4',
                'test1.example.com': '1.2.3.4',
                'test2': '1.2.3.5',
                'test2.example.com': '1.2.3.5',
                'test1.localdomain': '127.0.0.1',
                'test2.localdomain': '127.0.0.1',

                'ip-10-111-5-173': '10.111.5.173',
                'ip-10-111-5-173.zenoss.loc': '10.111.5.173'
            })
        self._real_resolve_names = hostmap.resolve_names
        hostmap.resolve_names = resolve_names

    def tearDown(self):
        super(TestHostMap, self).tearDown()

        hostmap.resolve_names = self._real_resolve_names

    @crochet.wait_for(timeout=30)
    def perform_mapping(self, hostmap):
        # This has to be run through the twisted reactor.
        return hostmap.perform_mapping()

    def test_clear_mappings(self):
        hostmap = HostMap()
        self.perform_mapping(hostmap)
        self.assertEquals(len(hostmap.all_hostids()), 0)

        hostmap.add_hostref("test")

        self.perform_mapping(hostmap)
        self.assertEquals(len(hostmap.all_hostids()), 1)

        hostmap.clear_mappings()

        self.perform_mapping(hostmap)
        self.assertEquals(len(hostmap.all_hostids()), 0)

    def test_freeze_thaw_mappings(self):
        hostmap = HostMap()
        hostmap.add_hostref("test1")
        hostmap.add_hostref("test2")
        hostmap.add_hostref("test3")
        hostmap.assert_host_id("test2", "host-test2-forcedid")
        self.perform_mapping(hostmap)
        self.assertEquals(len(hostmap.all_hostids()), 3)

        frozen = hostmap.freeze_mappings()

        hostmap.clear_mappings()
        hostmap.thaw_mappings(frozen)
        hostmap.add_hostref("test1")
        hostmap.add_hostref("test2")
        hostmap.add_hostref("test3")
        self.perform_mapping(hostmap)
        self.assertEquals(len(hostmap.all_hostids()), 3)

        self.assertEquals(hostmap.get_hostid("test1"), "host-test1")
        self.assertEquals(hostmap.get_hostid("test2"), "host-test2-forcedid")
        self.assertEquals(hostmap.get_hostid("test3"), "host-test3")

    def test_short_fqdn(self):
        hostmap = HostMap()
        hostmap.add_hostref("test1")
        hostmap.add_hostref("test1.example.com")
        hostmap.add_hostref("test2")
        hostmap.add_hostref("test2.example.com")
        self.perform_mapping(hostmap)

        # These should be condensed down, if they resolve to the
        # same IP.  Otherwise, it does not assume that they are the same.
        self.assertEquals(len(hostmap.all_hostids()), 2)

        # It should use the longer name, as well.
        self.assertEquals(hostmap.get_hostid("test1"), "host-test1.example.com")
        self.assertEquals(hostmap.get_hostid("test2"), "host-test2.example.com")

    def test_suffixed_names(self):
        hostmap = HostMap()
        hostmap.add_hostref("test1:somecrazysuffix_thatisreallylong")
        hostmap.add_hostref("test1.example.com")
        hostmap.add_hostref("test1")
        hostmap.add_hostref("test2.example.com")
        self.perform_mapping(hostmap)

        # These should be condensed down, if they resolve to the
        # same IP.  Otherwise, it does not assume that they are the same.
        self.assertEquals(len(hostmap.all_hostids()), 2)

        # It should use the longer name, as well, but not the crazy suffixed
        # one..
        self.assertEquals(hostmap.get_hostid("test1"), "host-test1.example.com")
        self.assertEquals(hostmap.get_hostid("test1:somecrazysuffix_thatisreallylong"), "host-test1.example.com")

    def test_localdomain(self):
        # See ZPS-1244 for details- in short, any hostname ending in .localdomain
        # will resolve to 127.0.0.1 on our hosts, and some tripleO deployment models
        # end up with hosts self-identifying with such hostnames.
        # While this will cause other issues, at least hostmap should not conflate
        # them.
        hostmap = HostMap()
        hostmap.add_hostref("test1.localdomain")
        hostmap.add_hostref("test2.localdomain")

        self.perform_mapping(hostmap)

        # We want this to resolve to two host IDs, not be consolidated into one.
        self.assertEquals(len(hostmap.all_hostids()), 2)

    def test_mixed_fqdns(self):
        # This is replicating results seen in the QA environment where
        # one host was being identified as 2, due to a mix of fqdn and short
        # names being reported in the nova services list.  (ZPS-1709)
        hostmap = HostMap()

        hostmap.add_hostref("ip-10-111-5-173", source="nova services")
        hostmap.add_hostref("ip-10-111-5-173.zenoss.loc", source="nova services")
        hostmap.add_hostref("ip-10-111-5-173@lvm", source="cinder services")
        hostmap.add_hostref("ip-10-111-5-173.zenoss.loc@lvm", source="cinder services")
        hostmap.add_hostref("10.111.5.173", source="Nova API URL")

        self.perform_mapping(hostmap)

        # We want this to consolidated into one hostid.
        self.assertEquals(len(hostmap.all_hostids()), 1)

    def test_case_insensitve_assert_host_id(self):
        hostmap = HostMap()
        hostmap.add_hostref("Test1")
        hostmap.assert_host_id("test1", "host-test1-forcedid")
        self.perform_mapping(hostmap)
        self.assertEquals(hostmap.get_hostid("test1"), "host-test1-forcedid")
        self.assertEquals(hostmap.get_hostid("Test1"), "host-test1-forcedid")


    def test_prefixed_hostmap(self):

        dc = self.dmd.Devices.createOrganizer('/Devices/OpenStack/Infrastructure')

        dc.setZenProperty('zPythonClass', 'ZenPacks.zenoss.OpenStackInfrastructure.Endpoint')
        dc.setZenProperty('zOpenStackHostDeviceClass', '/Server/SSH/Linux/NovaHost')
        dc.setZenProperty('zOpenStackHostLocalDomain', '')
        dc.setZenProperty('zOpenStackHostMapPrefix', '')

        os_a = dc.createInstance('zenoss.OpenStackInfrastructure.testDevice-a')
        os_a.setZenProperty('zOpenStackHostMapPrefix', 'qa')
        os_b = dc.createInstance('zenoss.OpenStackInfrastructure.testDevice-b')
        os_b.setZenProperty('zOpenStackHostMapPrefix', 'qb')

        hosts_a = [
            addContained(os_a, 'components', Host('host-linuxdev1')),
            addContained(os_a, 'components', Host('host-linuxdev2'))
        ]
        hosts_b = [
            addContained(os_b, 'components', Host('host-linuxdev3')),
            addContained(os_b, 'components', Host('host-linuxdev4')),
            addContained(os_b, 'components', Host('host-linuxdev5'))
        ]

        for host in hosts_a:
            self.assertIn('qa-', host.suggested_device_name())
        for host in hosts_b:
            self.assertIn('qb-', host.suggested_device_name())


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestHostMap))
    return suite


if __name__ == "__main__":
    from zope.testrunner.runner import Runner
    runner = Runner(found_suites=[test_suite()])
    runner.run()
