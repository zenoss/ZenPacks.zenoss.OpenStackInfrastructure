#!/usr/bin/env python

##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
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
from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import setup_crochet

from twisted.internet import defer

unused(Globals)

crochet = setup_crochet()


class TestHostMap(BaseTestCase):
    '''
    Test suite for HostMap
    '''

    disableLogging = False

    def setUp(self):
        def resolve_names(names):
            return defer.maybeDeferred(lambda: {
                'test1': '1.2.3.4',
                'test1.example.com': '1.2.3.4',
                'test2': '1.2.3.5',
                'test2.example.com': '1.2.3.5'
            })
        self._real_resolve_names = hostmap.resolve_names
        hostmap.resolve_names = resolve_names

    def tearDown(self):
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


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestHostMap))
    return suite


if __name__ == "__main__":
    from zope.testrunner.runner import Runner
    runner = Runner(found_suites=[test_suite()])
    runner.run()
