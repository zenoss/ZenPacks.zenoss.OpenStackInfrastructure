#!/usr/bin/env python

###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2017, Zenoss Inc.
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
from Products.ZenUtils.Utils import unused

from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import setup_crochet
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
    "host-10-0-0-1.openstacklocal.": "10.0.0.1",
    "host-10-0-0-2.openstacklocal.": "10.0.0.2",
    "host-10-0-0-3.openstacklocal.": "10.0.0.3",
    "host-172-24-4-226.openstacklocal.": "172.24.4.226",
    "overcloud-controller-1.localdomain": "10.88.0.100"
}


# Test the 'process' method of the modeler with some variants on the normal data
# Starting with the case where the neutron 'agents' call doesn't work on
# the target environment.  (ZPS-1243)


class TestModelProcessVariants(BaseTestCase):

    disableLogging = False

    def tearDown(self):
        super(TestModelProcessVariants, self).tearDown()
        DeviceProxyComponent.getHostByName = self._real_getHostByName
        Device.getHostByName = self._real_getHostByName
        hostmap.resolve_names = self._real_resolve_names

    def afterSetUp(self):
        super(TestModelProcessVariants, self).afterSetUp()

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

        self._real_getHostByName = DeviceProxyComponent.getHostByName
        DeviceProxyComponent.getHostByName = getHostByName
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

    @crochet.wait_for(timeout=30)
    def _preprocessHosts(self, modeler, results):
        return modeler.preprocess_hosts(self.d, results)

    def _loadTestData(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'data',
                               'modeldata.json')) as json_file:
            return json.load(json_file)

    def _processTestData(self, data):
        modeler = OpenStackInfrastructureModeler()
        self._preprocessHosts(modeler, data)
        for data_map in modeler.process(self.d, data, log):
            self.applyDataMap(self.d, data_map)

    def testNoAgents(self):
        data = self._loadTestData()

        # no neutron agents available on this target..
        data['agents'] = []

        # We basically just want this to not throw any exceptions.
        self._processTestData(data)


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestModelProcessVariants))
    return suite


if __name__ == "__main__":
    from zope.testrunner.runner import Runner
    runner = Runner(found_suites=[test_suite()])
    runner.run()
