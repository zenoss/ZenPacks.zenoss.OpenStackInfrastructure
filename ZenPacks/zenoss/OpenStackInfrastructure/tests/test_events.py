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
Unit test for event
'''
import os
import json

import Globals

import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('zen.OpenStack')

from zExceptions import NotFound
from Products.ZenEvents.Event import buildEventFromDict
from Products.ZenUtils.Utils import monkeypatch

from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import create_model_data

from Products.ZenUtils.Utils import unused
unused(Globals)

from ZenPacks.zenoss.OpenStackInfrastructure.events import process as process_event
from ZenPacks.zenoss.OpenStackInfrastructure import zenpacklib
# Required before zenpacklib.TestCase can be used.
zenpacklib.enableTesting()


class TestEventTransforms(zenpacklib.TestCase):

    disableLogging = False
    _eventData = None
    _eventsloaded = False

    def afterSetUp(self):
        # needed if this is run directly on the commandline,
        # since otherwise it will be __main__, and ZPL's afterSetup
        # will get confused.
        self.__module__ = 'ZenPacks.zenoss.OpenStackInfrastructure.tests.test_impact'
        super(TestEventTransforms, self).afterSetUp()

        # Quiet down some noisy logging.
        # logging.getLogger('zen.OpenStackDeviceProxyComponent').setLevel(logging.ERROR)

        self._loadEventsData()

    def _loadEventsData(self):
        if self._eventsloaded:
            return

        with open(os.path.join(os.path.dirname(__file__),
                               'data',
                               'eventdata.json')) as json_file:
            self._eventData = json.load(json_file)

        if self._eventData:
            self._eventsloaded = True

    def model_data(self):
        if not hasattr(self, '_model_data'):
            self._model_data = create_model_data(self.dmd)
        return self._model_data

    def endpoint(self):
        '''
        Return a OpenStackInfrastructureEndpoint populated in a suitable way for Impact
        testing.
        '''
        return self.model_data()['endpoint']

    def getObjByPath(self, path):
        try:
            return self.endpoint().getObjByPath(path)
        except NotFound:
            return None

    def process_event(self, evt):
        changes = process_event(evt, self.endpoint(), self.dmd, None)
        log.info("Processed event (eventClassKey=%s, summary=%s, %d objmaps, component=%s)" %
                 (evt.eventClassKey, evt.summary, changes, evt.component))

    def test_instance_creation(self):
        self.assertTrue(self._eventsloaded)

        evt = buildEventFromDict(self._eventData['scheduler.run_instance.end'])
        self.process_event(evt)

        evt = buildEventFromDict(self._eventData['compute.instance.create.start'])
        self.process_event(evt)

        instance5 = self.getObjByPath('components/server-instance5')

        self.assertIsNotNone(instance5, msg="Incremental model created instance 'instance5'")

        self.assertTrue(instance5.publicIps is None or instance5.publicIps == [])
        self.assertTrue(instance5.privateIps is None or instance5.privateIps == [])

        evt = buildEventFromDict(self._eventData['compute.instance.create.end'])
        # json would not allow evt.trait_fixed_ips to be a string
        # but events.py requires it to be a string
        evt.trait_fixed_ips = str(evt.trait_fixed_ips)
        self.process_event(evt)

        self.assertTrue(instance5.privateIps == [u'172.24.4.229'])
        self.assertTrue(instance5.publicIps is None or instance5.publicIps == [])

    def _create_instance5(self):
        self.assertTrue(self._eventsloaded)

        # # Dummy up the instance (as if test_instance_creation had run, and we had instance5 in the system)

        from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import addContained, addNonContained
        from ZenPacks.zenoss.OpenStackInfrastructure.Instance import Instance
        instance1 = self.getObjByPath('components/instance1')
        instance5 = self.getObjByPath('components/server-instance5')

        self.assertIsNotNone(instance1, msg="Instance1 is missing from the model!")
        self.assertIsNone(instance5, msg="Instance5 is already present in model!")

        instance5 = addContained(self.endpoint(), "components", Instance("server-instance5"))
        instance5.title = u'instance5'
        instance5.hostName = 'instance5'
        instance5.resourceId = u'instance5'
        instance5.serverId = u'instance5'
        instance5.serverStatus = u'ACTIVE'
        addNonContained(instance5, "flavor", instance1.flavor())
        addNonContained(instance5, "image", instance1.image())
        addNonContained(instance5, "hypervisor", instance1.hypervisor())
        addNonContained(instance5, "tenant", instance1.tenant())

    def test_instance_power_off(self):
        self.assertTrue(self._eventsloaded)

        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        self.assertTrue(instance5.serverStatus.lower() == 'active')

        evt = buildEventFromDict(self._eventData['compute.instance.power_off.start'])
        self.process_event(evt)

        self.assertTrue(instance5.serverStatus.lower() == 'active')

        evt = buildEventFromDict(self._eventData['compute.instance.power_off.end'])
        self.process_event(evt)

        self.assertTrue(instance5.serverStatus.lower() == 'stopped')
        self.assertTrue(evt.summary == 'Instance instance5 powered off (status changed to stopped)')

    def test_instance_power_on(self):
        self.assertTrue(self._eventsloaded)

        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)
        instance5.serverStatus = 'stopped'

        self.assertTrue(instance5.serverStatus.lower() == 'stopped')

        evt = buildEventFromDict(self._eventData['compute.instance.power_on.start'])
        self.process_event(evt)

        self.assertTrue(instance5.serverStatus.lower() == 'stopped')

        evt = buildEventFromDict(self._eventData['compute.instance.power_on.end'])
        self.process_event(evt)

        self.assertTrue(instance5.serverStatus.lower() == 'active')
        self.assertTrue(evt.summary == 'Instance instance5 powered on (status changed to active)')

    def test_instance_reboot(self):
        self.assertTrue(self._eventsloaded)

        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        self.assertTrue(instance5.serverStatus.lower() == 'active')

        evt = buildEventFromDict(self._eventData['compute.instance.reboot.start'])
        self.process_event(evt)

        evt = buildEventFromDict(self._eventData['compute.instance.reboot.end'])
        self.process_event(evt)
        self.assertTrue(evt.summary == 'Instance instance5 rebooted (status changed to active)')

    def test_instance_rebuild(self):
        self.assertTrue(self._eventsloaded)

        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        evt = buildEventFromDict(self._eventData['compute.instance.rebuild.start'])
        self.process_event(evt)

        evt = buildEventFromDict(self._eventData['compute.instance.power_off.start'])
        self.process_event(evt)

        evt = buildEventFromDict(self._eventData['compute.instance.power_off.end'])
        self.process_event(evt)

        evt = buildEventFromDict(self._eventData['compute.instance.rebuild.end'])
        self.process_event(evt)

    def test_instance_suspend_resume(self):
        self.assertTrue(self._eventsloaded)

        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        evt = buildEventFromDict(self._eventData['compute.instance.suspend'])
        self.process_event(evt)
        self.assertTrue(instance5.serverStatus.lower() == 'suspended')
        self.assertTrue(evt.summary == 'Instance instance5 suspended')

        evt = buildEventFromDict(self._eventData['compute.instance.resume'])
        self.process_event(evt)
        self.assertTrue(instance5.serverStatus.lower() == 'active')
        self.assertTrue(evt.summary == 'Instance instance5 resumed')

    def test_instance_delete(self):
        self.assertTrue(self._eventsloaded)

        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        evt = buildEventFromDict(self._eventData['compute.instance.delete.start'])
        self.process_event(evt)

        evt = buildEventFromDict(self._eventData['compute.instance.shutdown.start'])
        self.process_event(evt)

        evt = buildEventFromDict(self._eventData['compute.instance.shutdown.end'])
        self.process_event(evt)

        evt = buildEventFromDict(self._eventData['compute.instance.delete.end'])
        self.process_event(evt)

        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNone(instance5)

    def test_instance_rescue_unrescue(self):
        self.assertTrue(self._eventsloaded)

        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        evt = buildEventFromDict(self._eventData['compute.instance.rescue.start'])
        self.process_event(evt)

        evt = buildEventFromDict(self._eventData['compute.instance.exists'])
        self.process_event(evt)

        evt = buildEventFromDict(self._eventData['compute.instance.rescue.end'])
        self.process_event(evt)
        self.assertTrue(instance5.serverStatus.lower() == 'rescued')
        self.assertTrue(evt.summary == 'Instance instance5 placed in rescue mode')

        evt = buildEventFromDict(self._eventData['compute.instance.unrescue.start'])

        evt = buildEventFromDict(self._eventData['compute.instance.unrescue.end'])

        self.process_event(evt)
        self.assertTrue(instance5.serverStatus.lower() == 'active')
        self.assertTrue(evt.summary == 'Instance instance5 removed from rescue mode')

    def _create_network(self, network_id):
        self.assertTrue(self._eventsloaded)

        ''' Build network using events and network_id'''

        log.info("Create network '%s'" % network_id)
        evt = buildEventFromDict(self._eventData['network.create.end'])

        self.process_event(evt)
        network = self.getObjByPath('components/network-' + network_id)
        return network

    def _delete_network(self, network_id):
        self.assertTrue(self._eventsloaded)

        ''' Delete network using events and network_id'''
        log.info("Delete network '%s'" % network_id)

        evt = buildEventFromDict(self._eventData['network.delete.end'])

        self.process_event(evt)
        network = self.getObjByPath('components/network-' + network_id)
        return network

    def _create_subnet(self, network_id, subnet_id):
        self.assertTrue(self._eventsloaded)

        ''' Build subnet_id using events and network_id.
            The network/network_id must already exist.
        '''
        log.info("Create Subnet '%s'" % subnet_id)

        evt = buildEventFromDict(self._eventData['subnet.create.end'])

        self.process_event(evt)
        subnet = self.getObjByPath('components/subnet-' + subnet_id)
        return subnet

    def _delete_subnet(self, subnet_id):
        self.assertTrue(self._eventsloaded)

        ''' Delete subnet using events and subnet_id'''
        log.info("Delete Subnet '%s'" % subnet_id)

        evt = buildEventFromDict(self._eventData['subnet.delete.end'])

        self.process_event(evt)
        subnet = self.getObjByPath('components/subnet-' + subnet_id)
        return subnet

    def _create_port(self, network_id, port_id):
        self.assertTrue(self._eventsloaded)

        ''' Build port_id using events and network_id.
            The network/network_id must already exist.
        '''
        log.info("Create port '%s'" % port_id)

        evt = buildEventFromDict(self._eventData['port.create.end'])

        self.process_event(evt)
        port = self.getObjByPath('components/port-' + port_id)
        return port

    def _delete_port(self, port_id):
        self.assertTrue(self._eventsloaded)

        ''' Delete port using events and port_id'''
        log.info("Delete port '%s'" % port_id)

        evt = buildEventFromDict(self._eventData['port.delete.end'])

        self.process_event(evt)
        port = self.getObjByPath('components/port-' + port_id)
        return port

    def _create_router(self, network_id, subnet_id, router_id):
        self.assertTrue(self._eventsloaded)

        ''' Build router_id using events, network_id, subnet_id.
            The network_id, subnet_id must already exist.
        '''
        log.info("Create router '%s'" % router_id)

        gateway_info = "{u'network_id': u'%s', u'enable_snat': True, " \
               "u'external_fixed_ips': [{u'subnet_id':  u'%s', " \
               "u'ip_address': u'192.168.117.226'}]}" \
               % (network_id, subnet_id)

        evt = buildEventFromDict(self._eventData['router.create.end'])

        self.process_event(evt)
        router = self.getObjByPath('components/router-' + router_id)
        return router

    def _delete_router(self, router_id):
        self.assertTrue(self._eventsloaded)

        ''' Delete router using events and router_id'''
        log.info("Delete router '%s'" % router_id)

        evt = buildEventFromDict(self._eventData['router.delete.end'])

        self.process_event(evt)
        router = self.getObjByPath('components/router-' + router_id)
        return router

    def _create_floatingip(self, network_id, router_id, port_id, floatingip_id):
        self.assertTrue(self._eventsloaded)

        ''' Build floatingip_id using events, network_id, subnet_id.
            The network_id, subnet_id must already exist.
        '''
        log.info("Create floatingip '%s'" % floatingip_id)

        evt = buildEventFromDict(self._eventData['floatingip.create.end'])

        self.process_event(evt)
        floatingip = self.getObjByPath('components/floatingip-' + floatingip_id)
        return floatingip

    def _delete_floatingip(self, floatingip_id):
        self.assertTrue(self._eventsloaded)

        ''' Delete floatingip using events and floatingip_id'''
        log.info("Delete floatingip '%s'" % floatingip_id)

        evt = buildEventFromDict(self._eventData['floatingip.delete.end'])

        self.process_event(evt)
        floatingip = self.getObjByPath('components/floatingip-' + floatingip_id)
        return floatingip

    def _create_securitygroup(self, securitygroup_id):
        self.assertTrue(self._eventsloaded)

        ''' Build securitygroup_id using events.
        '''
        log.info("Create securityGroup '%s'" % securitygroup_id)

        evt = buildEventFromDict(self._eventData['security_group.create.end'])

        self.process_event(evt)
        securitygroup = self.getObjByPath('components/securitygroup-' + securitygroup_id)
        return securitygroup

    def _delete_securitygroup(self, securitygroup_id):
        self.assertTrue(self._eventsloaded)

        ''' Delete securitygroup using events and securitygroup_id'''
        log.info("Delete securityGroup '%s'" % securitygroup_id)

        evt = buildEventFromDict(self._eventData['security_group.delete.end'])

        self.process_event(evt)
        securitygroup = self.getObjByPath('components/securitygroup-' + securitygroup_id)
        return securitygroup

    def test_network(self):
        ''' Test Creation/Deletion of network '''
        net = self._create_network("test")
        self.assertIsNotNone(net, msg="Failure: nework doesn't exist!")

        net = self._delete_network(net.netId)
        self.assertIsNone(net, msg="Failure: network exists!")

    def test_subnet(self):
        ''' Test Creation/Deletion of subnet '''
        net = self._create_network("test")
        self.assertIsNotNone(net, msg="Subnet: network doesn't exist!")

        subnet = self._create_subnet(net.netId, 'test')
        self.assertIsNotNone(subnet, msg="Failure: subnet doesn't exist!")

        subnet = self._delete_subnet(subnet.subnetId)
        self.assertIsNone(subnet, msg="Failure: subnet exist!")

    def test_port(self):
        self.assertTrue(self._eventsloaded)

        ''' Test Creation/Deletion of port '''
        net = self._create_network("test")
        self.assertIsNotNone(net, msg="CreatePort: network doesn't exist!")

        port = self._create_port(net.netId, 'test')
        self.assertIsNotNone(port, msg="CreatePort: port doesn't exist!")

        port = self._delete_port(port.portId)
        self.assertIsNone(port, msg="Failure: port exists!")

    def test_router_and_floatingip(self):
        self.assertTrue(self._eventsloaded)

        ''' Test Creation/Deletion of port '''
        net = self._create_network("test")
        subnet = self._create_subnet(net.netId, 'test')
        port = self._create_port(net.netId, 'test')

        router = self._create_router(net.netId, subnet.subnetId, 'test')
        self.assertIsNotNone(router, msg="CreateRouter: router doesn't exist!")

        f_ip = self._create_floatingip(net.netId,
                                       router.routerId,
                                       port.portId,
                                       'test')
        self.assertIsNotNone(f_ip, msg="CreateRouter: FloatingIP doesn't exist!")

        router = self._delete_router(router.routerId)
        self.assertIsNone(router, msg="Failure: router exists!")

        f_ip = self._delete_floatingip(f_ip.floatingipId)
        self.assertIsNone(f_ip, msg="Failure: floatingip exists!")

    def test_security_group(self):
        '''
            Test Creation/Deletion of SecurityGroup
            Currently we do not process security group events, which causes
            securitygroup object to be None.
            Update this test once we decide to process security group
            events
        '''

        securitygroup = self._create_securitygroup('test')
        self.assertIsNone(securitygroup)

        securitygroup = self._delete_securitygroup('test')
        self.assertIsNone(securitygroup)


    def _create_volume_start(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Create volume '%s'" % volume_id)

        evt = buildEventFromDict(self._eventData['volume.create.start'])

        self.process_event(evt)
        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume


    def _create_volume_end(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Create volume '%s'" % volume_id)

        evt = buildEventFromDict(self._eventData['volume.create.end'])

        self.process_event(evt)
        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume


    def _update_volume_start(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Update volume '%s'" % volume_id)

        evt = buildEventFromDict(self._eventData['volume.update.start'])

        self.process_event(evt)
        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume


    def _update_volume_end(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Update volume '%s'" % volume_id)

        evt = buildEventFromDict(self._eventData['volume.update.end'])

        self.process_event(evt)
        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume


    def _attach_volume_start(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Attach volume '%s'" % volume_id)

        evt = buildEventFromDict(self._eventData['volume.attach.start'])

        self.process_event(evt)
        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume


    def _attach_volume_end(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Attach volume '%s'" % volume_id)

        evt = buildEventFromDict(self._eventData['volume.attach.end'])

        self.process_event(evt)
        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume


    def _detach_volume_start(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Detach volume '%s'" % volume_id)

        evt = buildEventFromDict(self._eventData['volume.detach.start'])

        self.process_event(evt)
        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume


    def _detach_volume_end(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Detach volume '%s'" % volume_id)

        evt = buildEventFromDict(self._eventData['volume.detach.end'])

        self.process_event(evt)
        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume


    def _delete_volume_start(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Delete volume '%s'" % volume_id)

        evt = buildEventFromDict(self._eventData['volume.delete.start'])

        self.process_event(evt)
        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume


    def _delete_volume_end(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Delete volume '%s'" % volume_id)

        evt = buildEventFromDict(self._eventData['volume.delete.end'])

        self.process_event(evt)
        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume


    def _create_volsnapshot_start(self, volsnapshot_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume snapshot using events.
        '''
        log.info("Create volume snapshot '%s'" % volsnapshot_id)

        evt = buildEventFromDict(self._eventData['volsnapshot.create.start'])

        self.process_event(evt)
        volsnapshot = self.getObjByPath('components/volsnapshot-' + volsnapshot_id)
        return volsnapshot


    def _create_volsnapshot_end(self, volsnapshot_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume snapshot using events.
        '''
        log.info("Create volume snapshot '%s'" % volsnapshot_id)

        evt = buildEventFromDict(self._eventData['volsnapshot.create.end'])

        self.process_event(evt)
        volsnapshot = self.getObjByPath('components/volsnapshot-' + volsnapshot_id)
        return volsnapshot


    def _delete_volsnapshot_start(self, volsnapshot_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume snapshot using events.
        '''
        log.info("Delete volume snapshot '%s'" % volsnapshot_id)

        evt = buildEventFromDict(self._eventData['volsnapshot.delete.start'])

        self.process_event(evt)
        volsnapshot = self.getObjByPath('components/volsnapshot-' + volsnapshot_id)
        return volsnapshot


    def _delete_volsnapshot_end(self, volsnapshot_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume snapshot using events.
        '''
        log.info("Delete volume snapshot '%s'" % volsnapshot_id)

        evt = buildEventFromDict(self._eventData['volsnapshot.delete.end'])

        self.process_event(evt)
        volsnapshot = self.getObjByPath('components/volsnapshot-' + volsnapshot_id)
        return volsnapshot


    def test_volume_create_start(self):
        '''
            volume create start
            This event does not return a volume object
        '''

        volume = self._create_volume_start('test')
        self.assertIsNone(volume)


    def test_volume_create_end(self):
        '''
            volume create end
            This event does return a volume object
        '''

        volume = self._create_volume_end('test')
        self.assertIsNotNone(volume)
        self.assertEquals(volume.tenant.id, 'tenant')
        self.assertEquals(volume.id, 'volume-test')
        self.assertEquals(volume.size, '1')


    def test_volume_update_start(self):
        '''
            volume update start
            This event does not return a volume object
        '''

        volume = self._create_volume_end('test')
        self.assertIsNotNone(volume)
        volume = self._update_volume_start('test')
        self.assertIsNotNone(volume)


    def test_volume_update_end(self):
        '''
            volume update end
            This event does return a volume object
        '''

        volume = self._create_volume_end('test')
        self.assertIsNotNone(volume)
        volume = self._update_volume_end('test')
        self.assertIsNotNone(volume)
        self.assertEquals(volume.tenant.id, 'tenant')
        self.assertEquals(volume.id, 'volume-test')
        self.assertEquals(volume.size, '2')


    def test_volume_attach_start(self):
        '''
            volume attach start
            This event does not return a volume object
        '''

        self._create_instance5()
        volume = self._attach_volume_start('test')
        self.assertIsNone(volume)


    def test_volume_attach_end(self):
        '''
            volume attach end
            This event does return a volume object
        '''

        self._create_instance5()
        volume = self._attach_volume_end('test')
        self.assertIsNotNone(volume)
        self.assertEquals(volume.tenant.id, 'tenant')
        self.assertEquals(volume.id, 'volume-test')
        self.assertEquals(volume.size, '1')
        self.assertEquals(volume.title, 'test volume')


    def test_volume_detach_start(self):
        '''
            volume detach start
            This event does not return a volume object
        '''

        self._create_instance5()
        volume = self._attach_volume_end('test')
        self.assertIsNotNone(volume)
        volume = self._detach_volume_start('test')
        self.assertIsNotNone(volume)


    def test_volume_detach_end(self):
        '''
            volume detach end
            This event does return a volume object
        '''

        self._create_instance5()
        volume = self._attach_volume_end('test')
        self.assertIsNotNone(volume)
        volume = self._detach_volume_end('test')
        self.assertIsNotNone(volume)
        self.assertEquals(volume.tenant.id, 'tenant')
        self.assertEquals(volume.id, 'volume-test')
        self.assertEquals(volume.size, '1')
        self.assertEquals(volume.title, 'test volume')


    def test_volume_delete_start(self):
        '''
            volume delete start
            This event does not return a volume object
        '''

        volume = self._create_volume_end('test')
        self.assertIsNotNone(volume)
        volume = self._delete_volume_start('test')
        self.assertIsNotNone(volume)


    def test_volume_delete_end(self):
        '''
            volume delete end
            This event does not return a volume object
        '''

        volume = self._create_volume_end('test')
        self.assertIsNotNone(volume)
        volume = self._delete_volume_end('test')
        self.assertIsNone(volume)


    def test_volsnapshot_create_start(self):
        '''
            volume snapshot create start
            This event does not return a volume snapshot object
        '''

        volume = self._create_volume_end('test')
        self.assertIsNotNone(volume)
        volsnapshot = self._create_volsnapshot_start('test')
        self.assertIsNone(volsnapshot)


    def test_volsnapshot_create_end(self):
        '''
            volume snapshot create end
            This event does return a volume snapshot object
        '''

        volume = self._create_volume_end('test')
        self.assertIsNotNone(volume)
        volsnapshot = self._create_volsnapshot_end('test')
        self.assertIsNotNone(volsnapshot)
        self.assertEquals(volsnapshot.tenant.id, 'tenant')
        self.assertEquals(volsnapshot.id, 'volsnapshot-test')


    def test_volsnapshot_delete_start(self):
        '''
            volsnapshot delete start
            This event does not return a volsnapshot object
        '''

        volume = self._create_volume_end('test')
        self.assertIsNotNone(volume)
        volsnapshot = self._create_volsnapshot_end('test')
        self.assertIsNotNone(volsnapshot)
        volsnapshot = self._delete_volsnapshot_start('test')
        self.assertIsNotNone(volsnapshot)


    def test_volsnapshot_delete_end(self):
        '''
            volsnapshot delete end
            This event does not return a volsnapshot object
        '''

        volume = self._create_volume_end('test')
        self.assertIsNotNone(volume)
        volsnapshot = self._create_volsnapshot_end('test')
        self.assertIsNotNone(volsnapshot)
        volsnapshot = self._delete_volsnapshot_end('test')
        self.assertIsNone(volsnapshot)

    def test_ZPS1750(self):
        self.assertTrue(self._eventsloaded)

        # These events are deliberately wrong- they are the result of
        # a misconfigured openstack (missing our event_definitions.yaml).
        #
        # We should process them as well as we can.

        evt = buildEventFromDict(self._eventData['ZPS1750_port.update.start'])
        self.process_event(evt)

        evt = buildEventFromDict(self._eventData['ZPS1750_volume.detach.start'])
        self.process_event(evt)

        evt = buildEventFromDict(self._eventData['ZPS1750_snapshot.create.end'])
        self.process_event(evt)

@monkeypatch('Products.DataCollector.ApplyDataMap.ApplyDataMap')
def logChange(self, device, compname, eventClass, msg):
    logging.getLogger('zen.ApplyDataMap').info(msg)

def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestEventTransforms))
    return suite


if __name__ == "__main__":
    from zope.testrunner.runner import Runner
    runner = Runner(found_suites=[test_suite()])
    runner.run()
