#!/usr/bin/env python

##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
Unit test for impact
'''
import Globals

import transaction

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('zen.OpenStack')

import unittest

from zope.component import subscribers
from Products.Five import zcml

from Products.ZenUtils.guid.interfaces import IGUIDManager
from Products.ZenUtils.Utils import monkeypatch

from ZenPacks.zenoss.OpenStack.tests.test_utils import (
    require_zenpack,
    create_model_data,
    addContained, addNonContained,
    )

from Products.ZenUtils.Utils import unused
unused(Globals)

from ZenPacks.zenoss.OpenStack import zenpacklib
# Required before zenpacklib.TestCase can be used.
zenpacklib.enableTesting()


@monkeypatch('Products.Zuul')
def get_dmd():
    '''
    Retrieve the DMD object. Handle unit test connection oddities.

    This has to be monkeypatched on Products.Zuul instead of
    Products.Zuul.utils because it's already imported into Products.Zuul
    by the time this monkeypatch happens.
    '''
    try:
        # original is injected by the monkeypatch decorator.
        return original()

    except AttributeError:
        connections = transaction.get()._synchronizers.data.values()[:]
        for cxn in connections:
            app = cxn.root()['Application']
            if hasattr(app, 'zport'):
                return app.zport.dmd


def impacts_for(thing):
    '''
    Return a two element tuple.

    First element is a list of object ids impacted by thing. Second element is
    a list of object ids impacting thing.
    '''
    from ZenPacks.zenoss.Impact.impactd.interfaces \
        import IRelationshipDataProvider

    impacted_by = []
    impacting = []

    guid_manager = IGUIDManager(thing.getDmd())
    for subscriber in subscribers([thing], IRelationshipDataProvider):
        for edge in subscriber.getEdges():
            source = guid_manager.getObject(edge.source)
            impacted = guid_manager.getObject(edge.impacted)

            if source.id == thing.id:
                impacted_by.append(impacted.id)
            elif impacted.id == thing.id:
                impacting.append(source.id)

    return (impacted_by, impacting)


def states_for(thing, event=None):
    '''
    Return list of tuples representing
    '''
    from ZenPacks.zenoss.Impact.stated.stated import _getEventStates

    return _getEventStates(thing, event=event)


def triggers_for(thing):
    '''
    Return a dictionary of triggers for thing.

    Returned dictionary keys will be triggerId of a Trigger instance and
    values will be the corresponding Trigger instance.
    '''
    from ZenPacks.zenoss.Impact.impactd.interfaces import INodeTriggers

    triggers = {}

    for sub in subscribers((thing,), INodeTriggers):
        for trigger in sub.get_triggers():
            triggers[trigger.triggerId] = trigger

    return triggers


class TestImpact(zenpacklib.TestCase):
    '''
    Test suite for Impact within OpenStack.
    '''

    def afterSetUp(self):
        # needed if this is run directly on the commandline,
        # since otherwise it will be __main__, and ZPL's afterSetup
        # will get confused.
        self.__module__ = 'ZenPacks.zenoss.OpenStack.tests.test_impact'

        super(TestImpact, self).afterSetUp()

        import Products.ZenEvents
        zcml.load_config('meta.zcml', Products.ZenEvents)

        # For Zenoss 4.1.1
        zcml.load_string('''
            <configure>
                <include package="zope.viewlet" file="meta.zcml" />
            </configure>''')

        try:
            import ZenPacks.zenoss.DynamicView
            zcml.load_config('configure.zcml', ZenPacks.zenoss.DynamicView)
        except ImportError:
            return

        try:
            import ZenPacks.zenoss.Impact
            zcml.load_config('meta.zcml', ZenPacks.zenoss.Impact)
            zcml.load_config('configure.zcml', ZenPacks.zenoss.Impact)
        except ImportError:
            return

        import ZenPacks.zenoss.OpenStack
        zcml.load_config('configure.zcml', ZenPacks.zenoss.OpenStack)

    def model_data(self):
        if not hasattr(self, '_model_data'):
            self._model_data = create_model_data(self.dmd)
        return self._model_data

    def endpoint(self):
        '''
        Return a OpenStackEndpoint populated in a suitable way for Impact
        testing.
        '''
        return self.model_data()['endpoint']

    def linuxguest(self, guestid):
        return self.model_data()['guest_dc'].getObjByPath('devices/' + guestid)

    def linuxguests(self):
        return self.model_data()['guest_dc'].getDevices()

    def linuxhost(self, hostid):
        return self.model_data()['phys_dc'].getObjByPath('devices/' + hostid)

    def linuxhosts(self):
        return self.model_data()['phys_dc'].getDevices()

    def assertTriggersExist(self, triggers, expected_trigger_ids):
        '''
        Assert that each expected_trigger_id exists in triggers.
        '''
        for trigger_id in expected_trigger_ids:
            self.assertTrue(
                trigger_id in triggers, 'missing trigger: %s' % trigger_id)

    @require_zenpack('ZenPacks.zenoss.Impact')
    def test_Endpoint(self):
        impacts, impacted_by = impacts_for(self.endpoint())

        # Endpoint -> Host
        self.assertTrue('computehost1' in impacts,
                        msg="endpoint impacts computehost1")
        self.assertTrue('computehost2' in impacts,
                        msg="endpoint impacts computehost2")
        self.assertTrue('controllerhost' in impacts,
                        msg="endpoint impacts controllerhost")

    @require_zenpack('ZenPacks.zenoss.Impact')
    def test_Host(self):
        hosts = self.endpoint().getDeviceComponents(type='OpenStackHost')
        self.assertNotEqual(len(hosts), 0)

        for host in hosts:
            impacts, impacted_by = impacts_for(host)

            # host -> software running on the host
            self.assertNotEqual(host.hostedSoftware.countObjects(), 0)
            for software in host.hostedSoftware():
                self.assertTrue(software.id in impacts,
                                msg="host %s impacts %s running upon it" % (host.id, software.id))

            # host -> hypervisor
            if host.hypervisor():
                # would only be on compute nodes
                self.assertTrue(host.hypervisor().id in impacts,
                                msg="host %s impacts hypervisor %s running upon it" % (host.id, host.hypervisor().id))

            # host -> cell or zone
            self.assertIsNotNone(host.orgComponent(),
                                 msg="host %s has no orgComponent associated with it" % (host.id))
            self.assertTrue(host.orgComponent().id in impacts,
                            msg="host %s impacts %s " % (host.id, host.orgComponent().id))

            # endpoint -> host
            self.assertTrue(self.endpoint().id in impacted_by,
                            msg="host %s impacted by endpoint" % (host.id))

            # (proxy) linux device -> host
            linuxhost = self.linuxhost("p-" + host.id)
            self.assertIsNotNone(linuxhost)

            self.assertTrue(linuxhost.id in impacted_by,
                            msg="host %s impacted by linux device %s" % (host.id, linuxhost.id))

    @require_zenpack('ZenPacks.zenoss.Impact')
    def test_NovaApi(self):

        nova_api = self.endpoint().getObjByPath("components/nova-api")
        impacts, impacted_by = impacts_for(nova_api)

        region = nova_api.orgComponent()
        self.assertIsNotNone(region)
        self.assertEquals(region.meta_type, "OpenStackRegion")

        self.assertTrue(region.id in impacts,
                        msg="%s impacts region %s" % (nova_api.id, region.id))

        host = nova_api.hostedOn()
        self.assertIsNotNone(host)

        self.assertTrue(host.id in impacted_by,
                        msg="%s is impacted by host %s it runs upon" % (nova_api.id, host.id))

        osprocess = nova_api.osprocess_component()
        if osprocess:
            # not all processes run on all boxes, so only check for the ones that seem to
            # be running there.
            self.assertIsNotNone(osprocess)
            self.assertTrue(osprocess.id in impacted_by,
                            msg="%s is impacted by osprocess component %s" % (nova_api.id, osprocess.id))

    @require_zenpack('ZenPacks.zenoss.Impact')
    def test_NovaService(self):
        nova_services = self.endpoint().getDeviceComponents(type='OpenStackNovaService')
        self.assertNotEqual(len(nova_services), 0)

        for nova_service in nova_services:
            impacts, impacted_by = impacts_for(nova_service)

            zone = nova_service.orgComponent()
            self.assertIsNotNone(zone)
            self.assertEquals(zone.meta_type, "OpenStackAvailabilityZone")

            self.assertTrue(zone.id in impacts,
                            msg="%s impacts zone %s" % (nova_service.id, zone.id))

            host = nova_service.hostedOn()
            self.assertIsNotNone(host)

            self.assertTrue(host.id in impacted_by,
                            msg="%s is impacted by host %s it runs upon" % (nova_service.id, host.id))

            osprocess = nova_service.osprocess_component()
            if osprocess:
                # not all processes run on all boxes, so only check for the ones that seem to
                # be running there.
                self.assertIsNotNone(osprocess)
                self.assertTrue(osprocess.id in impacted_by,
                                msg="%s is impacted by osprocess component %s" % (nova_service.id, osprocess.id))

    @require_zenpack('ZenPacks.zenoss.Impact')
    def test_Hypervisor(self):
        hypervisors = self.endpoint().getDeviceComponents(type='OpenStackHypervisor')
        self.assertNotEqual(len(hypervisors), 0)

        for hypervisor in hypervisors:
            impacts, impacted_by = impacts_for(hypervisor)

            host = hypervisor.host()
            self.assertIsNotNone(host)
            self.assertTrue(host.id in impacted_by,
                            msg="Hypervisor %s is impacted by its host %s" % (hypervisor.id, host.id))

            for instance in hypervisor.instances():
                self.assertTrue(instance.id in impacts,
                                msg="Hypervisor %s impacts instance %s" % (hypervisor.id, instance.id))

    @require_zenpack('ZenPacks.zenoss.Impact')
    @unittest.expectedFailure    # Cells aren't yet implemented
    def test_Cell(self):
        cells = self.endpoint().getDeviceComponents(type='OpenStackCell')
        self.assertNotEqual(len(cells), 0)

        for cell in cells:
            impacts, impacted_by = impacts_for(cell)

            org = cell.parentOrg()
            self.assertIsNotNone(org)

            if org.meta_type == 'OpenStackAvailabilityZone':
                zone = org
                self.assertTrue(zone.id in impacts,
                                msg="Cell %s impacts its zone %s" % (cell.id, zone.id))
            elif org.meta_type == 'OpenStackCell':
                parentcell = org
                self.assertTrue(parentcell.id in impacts,
                                msg="Cell %s impacts its parent cell %s" % (cell.id, cell.id))
            else:
                self.assertTrue(False, msg="Unrecognized cell parent type %s" % (org.meta_type))

            for childOrg in cell.childOrgs():
                if childOrg.meta_type == 'OpenStackCell':
                    self.assertTrue(childOrg.id in impacted_by,
                                    msg="Cell %s is impacted by its child cell %s" % (cell.id, childOrg.id))
                else:
                    self.assertTrue(False, msg="Unrecognized Cell child type %s" % (childOrg.meta_type))

    @require_zenpack('ZenPacks.zenoss.Impact')
    def test_AvailabilityZone(self):
        zones = self.endpoint().getDeviceComponents(type='OpenStackAvailabilityZone')
        self.assertNotEqual(len(zones), 0)

        for zone in zones:
            impacts, impacted_by = impacts_for(zone)

            region = zone.parentOrg()
            self.assertIsNotNone(region)

            self.assertTrue(region.id in impacts,
                            msg="Zone %s impacts its region %s" % (zone.id, region.id))

            for softwareComponent in zone.softwareComponents():
                self.assertTrue(softwareComponent.id in impacted_by,
                                msg="Zone %s is impacted by software component %s" % (zone.id, softwareComponent.id))

            for host in zone.hosts():
                self.assertTrue(host.id in impacted_by,
                                msg="Zone %s is impacted by host %s" % (zone.id, host.id))

            for childOrg in zone.childOrgs():
                if childOrg.meta_type == 'OpenStackCell':
                    self.assertTrue(childOrg.id in impacted_by,
                                    msg="Zone %s is impacted by its child cell %s" % (zone.id, childOrg.id))
                else:
                    self.assertTrue(False, msg="Unrecognized Zone child type %s" % (childOrg.meta_type))

    @require_zenpack('ZenPacks.zenoss.Impact')
    def test_Region(self):
        region = self.endpoint().getObjByPath("components/region")
        self.assertIsNotNone(region)

        impacts, impacted_by = impacts_for(region)

        for softwareComponent in region.softwareComponents():
                self.assertTrue(softwareComponent.id in impacted_by,
                                msg="Region %s is impacted by software component %s" % (region.id, softwareComponent.id))

        for childOrg in region.childOrgs():
            if childOrg.meta_type == 'OpenStackAvailabilityZone':
                self.assertTrue(childOrg.id in impacted_by,
                                msg="Region %s is impacted by its child Availability Zone %s" % (region.id, childOrg.id))
            else:
                self.assertTrue(False, msg="Unrecognized Region child type %s" % (childOrg.meta_type))

    @require_zenpack('ZenPacks.zenoss.Impact')
    @unittest.expectedFailure
    # Have not yet implemented openstackInstance()
    def test_Instance(self):
        instances = self.endpoint().getDeviceComponents(type='OpenStackInstance')
        self.assertNotEqual(len(instances), 0)

        for instance in instances:
            impacts, impacted_by = impacts_for(instance)

            for vnic in instance.vnics():
                self.assertTrue(vnic.id in impacted_by,
                                msg="Instance %s impacted by vnic %s" % (instance.id, vnic.id))

            hypervisor = instance.hypervisor()
            self.assertTrue(hypervisor.id in impacted_by,
                            msg="Instance %s impacted by hypervisor %s" % (instance.id, hypervisor.id))

            guest = self.linuxguest("g-" + instance.id)
            if guest:
                self.assertTrue(guest.id in impacts,
                                msg="Instance %s impacts guest %s" % (instance.id, guest.id))

            tenant = instance.tenant()
            self.assertTrue(tenant.id in impacts,
                            msg="Instance %s impacts tenant %s" % (instance.id, tenant.id))

    @require_zenpack('ZenPacks.zenoss.Impact')
    def test_Vnic(self):
        vnics = self.endpoint().getDeviceComponents(type='OpenStackVnic')
        self.assertNotEqual(len(vnics), 0)

        for vnic in vnics:
            impacts, impacted_by = impacts_for(vnic)
            instance = vnic.instance()
            self.assertTrue(instance.id in impacts,
                            msg="Vnic %s impacts instance %s" % (vnic.id, instance.id))



    @require_zenpack('ZenPacks.zenoss.Impact')
    def test_Tenant(self):
        tenants = self.endpoint().getDeviceComponents(type='OpenStackTenant')
        self.assertNotEqual(len(tenants), 0)

        for tenant in tenants:
            impacts, impacted_by = impacts_for(tenant)

            for instance in tenant.instances():                
                self.assertTrue(instance.id in impacted_by,
                                msg="Tenant %s impacted by instance %s" % (tenant.id, instance.id))



    @require_zenpack('ZenPacks.zenoss.Impact')
    @unittest.expectedFailure
    # Have not yet implemented openstackInstance()
    def test_GuestDevice(self):
        guests = self.linuxguests()
        self.assertNotEqual(len(guests), 0)

        for guest in guests:
            impacts, impacted_by = impacts_for(guest)
            instance = guest.openstackInstance()
            self.assertIsNotNone(instance, msg="Guest device %s is an openstack instance" % guest.id)
            self.assertTrue(instance.id in impacted_by,
                            msg="Guest %s is impacted by instance %s" % (guest.id, instance.id))

    @require_zenpack('ZenPacks.zenoss.Impact')
    def test_HostDevice(self):
        hostdevices = self.linuxhosts()
        self.assertNotEqual(len(hostdevices), 0)

        for hostdevice in hostdevices:
            impacts, impacted_by = impacts_for(hostdevice)
            host = hostdevice.openstack_hostComponent()
            self.assertIsNotNone(host, msg="Host device %s is an openstack host" % hostdevice.id)
            self.assertTrue(host.id in impacts,
                            msg="Host Device %s impacts host component %s" % (hostdevice.id, host.id))

    @require_zenpack('ZenPacks.zenoss.Impact')
    def test_OSProcess(self):
        from ZenPacks.zenoss.OpenStack.SoftwareComponent import SoftwareComponent
        passes = 0
        for component in self.endpoint().getDeviceComponents():
            if isinstance(component, SoftwareComponent):
                osprocess = component.osprocess_component()
                if osprocess:
                    impacts, impacted_by = impacts_for(osprocess)
                    self.assertTrue(component.id in impacts,
                                    msg="OSProcess %s is impacts software component %s" % (osprocess.id, component.id))
                    passes += 1

        self.assertTrue(passes > 0, msg="OSProcesses found with which to test")                    

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestImpact))
    return suite


if __name__ == "__main__":
    from zope.testrunner.runner import Runner
    runner = Runner(found_suites=[test_suite()])
    runner.run()
