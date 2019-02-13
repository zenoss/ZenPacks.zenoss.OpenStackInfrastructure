#!/usr/bin/env python

##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2019, all rights reserved.
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
import re

import Globals

import logging
logging.basicConfig(level=logging.ERROR)
log = logging.getLogger('zen.OpenStack')

from zExceptions import NotFound
from Products.ZenUtils.Utils import monkeypatch
from Products.DataCollector.ApplyDataMap import ApplyDataMap

from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import create_model_data
from ZenPacks.zenoss.OpenStackInfrastructure.datamaps import ConsolidatingObjectMapQueue

from Products.ZenUtils.Utils import unused
unused(Globals)

from ZenPacks.zenoss.OpenStackInfrastructure.events import map_event
from ZenPacks.zenoss.ZenPackLib import zenpacklib
# Required before zenpacklib.TestCase can be used.
zenpacklib.enableTesting()


class TestEventMappings(zenpacklib.TestCase):

    disableLogging = False
    _eventData = None
    _eventsloaded = False

    def afterSetUp(self):
        # needed if this is run directly on the commandline,
        # since otherwise it will be __main__, and ZPL's afterSetup
        # will get confused.
        self.__module__ = 'ZenPacks.zenoss.OpenStackInfrastructure.tests.test_impact'
        super(TestEventMappings, self).afterSetUp()

        # Quiet down some noisy logging.
        # logging.getLogger('zen.OpenStackDeviceProxyComponent').setLevel(logging.ERROR)

        self._loadEventsData()

        self.adm = ApplyDataMap()

        self.queue = ConsolidatingObjectMapQueue()
        self.clock = 1000.0

        def _now():
            return self.clock
        self.queue.now = _now

    def _loadEventsData(self):
        if self._eventsloaded:
            return

        with open(os.path.join(os.path.dirname(__file__),
                               'data',
                               'eventdata.json')) as json_file:
            self._eventData = json.load(json_file)

            for event in self._eventData.values():
                event['openstack_event_type'] = \
                    re.sub(r'^openstack-', '', event.get('eventClassKey', ''))

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
        objmap = map_event(evt)
        if objmap:
            self.adm._applyDataMap(self.endpoint(), objmap)

    def test_instance_creation(self):
        self.assertTrue(self._eventsloaded)

        self.process_event(self._eventData['scheduler.run_instance.end'])
        self.process_event(self._eventData['compute.instance.create.start'])
        self.process_event(self._eventData['compute.instance.create.end'])

        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5, msg="Incremental model created instance 'instance5'")

        self.assertTrue(instance5.publicIps is None or instance5.publicIps == [])
        self.assertTrue(instance5.privateIps is None or instance5.privateIps == [])

        evt = self._eventData['compute.instance.create.end']
        # json would not allow evt.trait_fixed_ips to be a string
        # but events.py requires it to be a string
        evt['trait_fixed_ips'] = str(evt['trait_fixed_ips'])
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

        return instance5

    def test_instance_power_off(self):
        self.assertTrue(self._eventsloaded)

        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        self.process_event(self._eventData['compute.instance.power_off.start'])
        self.process_event(self._eventData['compute.instance.power_off.end'])

        self.assertTrue(instance5.serverStatus == 'shutoff')
        self.assertTrue(instance5.vmState == 'stopped')
        self.assertTrue(instance5.powerState == 'shutdown')

    def test_instance_power_on(self):
        self.assertTrue(self._eventsloaded)

        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)
        instance5.serverStatus = 'shutoff'

        self.assertTrue(instance5.serverStatus == 'shutoff')

        self.process_event(self._eventData['compute.instance.power_on.start'])
        self.process_event(self._eventData['compute.instance.power_on.end'])

        self.assertTrue(instance5.serverStatus == 'active')
        self.assertTrue(instance5.powerState == 'running')

    def test_instance_reboot(self):
        self.assertTrue(self._eventsloaded)

        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        self.process_event(self._eventData['compute.instance.reboot.start'])
        self.process_event(self._eventData['compute.instance.reboot.end'])
        self.assertTrue(instance5.serverStatus == 'active')

    def test_instance_rebuild(self):
        self.assertTrue(self._eventsloaded)

        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        self.process_event(self._eventData['compute.instance.rebuild.start'])
        self.process_event(self._eventData['compute.instance.power_off.start'])
        self.process_event(self._eventData['compute.instance.power_off.end'])
        self.process_event(self._eventData['compute.instance.rebuild.end'])

    def test_instance_suspend_resume(self):
        self.assertTrue(self._eventsloaded)

        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        self.process_event(self._eventData['compute.instance.suspend'])
        self.assertTrue(instance5.serverStatus == 'suspended')
        self.assertTrue(instance5.powerState == 'suspended')

        self.process_event(self._eventData['compute.instance.resume'])
        self.assertTrue(instance5.serverStatus == 'active')
        self.assertTrue(instance5.powerState == 'running')

    def test_instance_delete(self):
        self.assertTrue(self._eventsloaded)

        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        self.process_event(self._eventData['compute.instance.delete.start'])
        self.process_event(self._eventData['compute.instance.shutdown.start'])
        self.process_event(self._eventData['compute.instance.shutdown.end'])
        self.process_event(self._eventData['compute.instance.delete.end'])

        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNone(instance5)

    def test_instance_rescue_unrescue(self):
        self.assertTrue(self._eventsloaded)

        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        self.process_event(self._eventData['compute.instance.rescue.start'])
        self.process_event(self._eventData['compute.instance.exists'])
        self.process_event(self._eventData['compute.instance.rescue.end'])
        self.assertTrue(instance5.vmState == 'rescued')
        self.assertTrue(instance5.serverStatus == 'rescue')

        self.process_event(self._eventData['compute.instance.unrescue.start'])
        self.process_event(self._eventData['compute.instance.unrescue.end'])
        self.assertTrue(instance5.serverStatus == 'active')

    def _create_network(self, network_id):
        self.assertTrue(self._eventsloaded)

        ''' Build network using events and network_id'''

        log.info("Create network '%s'" % network_id)
        self.process_event(self._eventData['network.create.end'])

        network = self.getObjByPath('components/network-' + network_id)
        return network

    def _delete_network(self, network_id):
        self.assertTrue(self._eventsloaded)

        ''' Delete network using events and network_id'''
        log.info("Delete network '%s'" % network_id)

        self.process_event(self._eventData['network.delete.end'])

        network = self.getObjByPath('components/network-' + network_id)
        return network

    def _create_subnet(self, network_id, subnet_id):
        self.assertTrue(self._eventsloaded)

        ''' Build subnet_id using events and network_id.
            The network/network_id must already exist.
        '''
        log.info("Create Subnet '%s'" % subnet_id)

        self.process_event(self._eventData['subnet.create.end'])

        subnet = self.getObjByPath('components/subnet-' + subnet_id)
        return subnet

    def _delete_subnet(self, subnet_id):
        self.assertTrue(self._eventsloaded)

        ''' Delete subnet using events and subnet_id'''
        log.info("Delete Subnet '%s'" % subnet_id)

        self.process_event(self._eventData['subnet.delete.end'])

        subnet = self.getObjByPath('components/subnet-' + subnet_id)
        return subnet

    def _create_port(self, network_id, port_id):
        self.assertTrue(self._eventsloaded)

        ''' Build port_id using events and network_id.
            The network/network_id must already exist.
        '''
        log.info("Create port '%s'" % port_id)

        self.process_event(self._eventData['port.create.end'])

        port = self.getObjByPath('components/port-' + port_id)
        return port

    def _delete_port(self, port_id):
        self.assertTrue(self._eventsloaded)

        ''' Delete port using events and port_id'''
        log.info("Delete port '%s'" % port_id)

        self.process_event(self._eventData['port.delete.end'])

        port = self.getObjByPath('components/port-' + port_id)
        return port

    def _create_router(self, network_id, subnet_id, router_id):
        self.assertTrue(self._eventsloaded)

        ''' Build router_id using events, network_id, subnet_id.
            The network_id, subnet_id must already exist.
        '''
        log.info("Create router '%s'" % router_id)

        self.process_event(self._eventData['router.create.end'])

        router = self.getObjByPath('components/router-' + router_id)
        return router

    def _delete_router(self, router_id):
        self.assertTrue(self._eventsloaded)

        ''' Delete router using events and router_id'''
        log.info("Delete router '%s'" % router_id)

        self.process_event(self._eventData['router.delete.end'])

        router = self.getObjByPath('components/router-' + router_id)
        return router

    def _create_floatingip(self, network_id, router_id, port_id, floatingip_id):
        self.assertTrue(self._eventsloaded)

        ''' Build floatingip_id using events, network_id, subnet_id.
            The network_id, subnet_id must already exist.
        '''
        log.info("Create floatingip '%s'" % floatingip_id)

        self.process_event(self._eventData['floatingip.create.end'])

        floatingip = self.getObjByPath('components/floatingip-' + floatingip_id)
        return floatingip

    def _delete_floatingip(self, floatingip_id):
        self.assertTrue(self._eventsloaded)

        ''' Delete floatingip using events and floatingip_id'''
        log.info("Delete floatingip '%s'" % floatingip_id)

        self.process_event(self._eventData['floatingip.delete.end'])

        floatingip = self.getObjByPath('components/floatingip-' + floatingip_id)
        return floatingip

    def test_network(self):
        ''' Test Creation/Deletion of network '''
        net = self._create_network("test")
        self.assertIsNotNone(net, msg="Failure: network doesn't exist!")

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

    def _create_volume_start(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Create volume '%s'" % volume_id)

        self.process_event(self._eventData['volume.create.start'])

        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume

    def _create_volume_end(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Create volume '%s'" % volume_id)

        self.process_event(self._eventData['volume.create.end'])

        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume

    def _update_volume_start(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Update volume '%s'" % volume_id)

        self.process_event(self._eventData['volume.update.start'])

        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume

    def _update_volume_end(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Update volume '%s'" % volume_id)

        self.process_event(self._eventData['volume.update.end'])

        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume

    def _attach_volume_start(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Attach volume '%s'" % volume_id)

        self.process_event(self._eventData['volume.attach.start'])

        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume

    def _attach_volume_end(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Attach volume '%s'" % volume_id)

        self.process_event(self._eventData['volume.attach.end'])

        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume

    def _detach_volume_start(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Detach volume '%s'" % volume_id)

        self.process_event(self._eventData['volume.detach.start'])

        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume

    def _detach_volume_end(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Detach volume '%s'" % volume_id)

        self.process_event(self._eventData['volume.detach.end'])

        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume

    def _delete_volume_start(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Delete volume '%s'" % volume_id)

        self.process_event(self._eventData['volume.delete.start'])

        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume

    def _delete_volume_end(self, volume_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume_id using events.
        '''
        log.info("Delete volume '%s'" % volume_id)

        self.process_event(self._eventData['volume.delete.end'])

        volume = self.getObjByPath('components/volume-' + volume_id)
        return volume

    def _create_volsnapshot_start(self, volsnapshot_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume snapshot using events.
        '''
        log.info("Create volume snapshot '%s'" % volsnapshot_id)

        self.process_event(self._eventData['volsnapshot.create.start'])

        volsnapshot = self.getObjByPath('components/volsnapshot-' + volsnapshot_id)
        return volsnapshot

    def _create_volsnapshot_end(self, volsnapshot_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume snapshot using events.
        '''
        log.info("Create volume snapshot '%s'" % volsnapshot_id)

        self.process_event(self._eventData['volsnapshot.create.end'])

        volsnapshot = self.getObjByPath('components/volsnapshot-' + volsnapshot_id)
        return volsnapshot

    def _delete_volsnapshot_start(self, volsnapshot_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume snapshot using events.
        '''
        log.info("Delete volume snapshot '%s'" % volsnapshot_id)

        self.process_event(self._eventData['volsnapshot.delete.start'])

        volsnapshot = self.getObjByPath('components/volsnapshot-' + volsnapshot_id)
        return volsnapshot

    def _delete_volsnapshot_end(self, volsnapshot_id):
        self.assertTrue(self._eventsloaded)

        ''' Build volume snapshot using events.
        '''
        log.info("Delete volume snapshot '%s'" % volsnapshot_id)

        self.process_event(self._eventData['volsnapshot.delete.end'])

        volsnapshot = self.getObjByPath('components/volsnapshot-' + volsnapshot_id)
        return volsnapshot

    def test_volume_create_end(self):
        '''
            volume create end
            This event does return a volume object
        '''

        volume = self._create_volume_end('test')
        self.assertIsNotNone(volume)
        self.assertEquals(volume.tenant.id, 'tenant')
        self.assertEquals(volume.id, 'volume-test')
        self.assertEquals(volume.size, 1)

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
        self.assertEquals(volume.size, 2)

    def test_volume_attach_end(self):
        '''
            volume attach end
            This event does return a volume object
        '''

        instance5 = self._create_instance5()
        volume = self._create_volume_end('test')
        self.assertIsNotNone(volume)

        self._attach_volume_start('test')
        self._attach_volume_end('test')

        self.assertIsNotNone(volume.instance())
        self.assertEquals(volume.instance().id, instance5.id)

        self.assertEquals(volume.tenant.id, 'tenant')
        self.assertEquals(volume.id, 'volume-test')
        self.assertEquals(volume.size, 1)
        self.assertEquals(volume.title, 'test volume')

    def test_volume_detach_end(self):
        '''
            volume detach end
            This event does return a volume object
        '''

        self._create_instance5()
        volume = self._create_volume_end('test')
        self.assertIsNotNone(volume)

        self._attach_volume_start('test')
        self._attach_volume_end('test')
        self.assertIsNotNone(volume.instance())

        self._detach_volume_start('test')
        self._detach_volume_end('test')
        self.assertIsNone(volume.instance())

        self.assertEquals(volume.tenant.id, 'tenant')
        self.assertEquals(volume.id, 'volume-test')
        self.assertEquals(volume.size, 1)
        self.assertEquals(volume.title, 'test volume')

        self.assertIsNone(volume.instance())

    def test_volume_delete_end(self):
        '''
            volume delete end
            This event does not return a volume object
        '''

        volume = self._create_volume_end('test')
        self.assertIsNotNone(volume)
        volume = self._delete_volume_end('test')
        self.assertIsNone(volume)

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

    def test_instance_shortlived(self):
        self.assertTrue(self._eventsloaded)
        datamaps = []

        self.queue.append(map_event(self._eventData['scheduler.run_instance.end']))
        datamaps.extend(self.queue.drain())

        self.queue.append(map_event(self._eventData['compute.instance.create.start']))
        datamaps.extend(self.queue.drain())

        self.clock += 1.0
        self.queue.append(map_event(self._eventData['compute.instance.create.end']))
        datamaps.extend(self.queue.drain())

        self.clock += 1.0
        datamaps.extend(self.queue.drain())

        self.assertEquals(len(datamaps), 0, "No instances were created early")

        self.clock += 5.0
        self.queue.append(map_event(self._eventData['compute.instance.delete.start']))
        datamaps.extend(self.queue.drain())
        self.queue.append(map_event(self._eventData['compute.instance.shutdown.start']))
        datamaps.extend(self.queue.drain())

        self.clock += 1.0
        self.queue.append(map_event(self._eventData['compute.instance.shutdown.end']))
        datamaps.extend(self.queue.drain())
        self.queue.append(map_event(self._eventData['compute.instance.delete.end']))
        datamaps.extend(self.queue.drain())

        # indeed, there should be no objmaps at all.
        self.assertEquals(len(datamaps), 0, "No model changes were made")

    def test_instance_longerlived(self):
        self.assertTrue(self._eventsloaded)
        datamaps = []

        self.queue.append(map_event(self._eventData['scheduler.run_instance.end']))
        datamaps.extend(self.queue.drain())

        self.queue.append(map_event(self._eventData['compute.instance.create.start']))
        datamaps.extend(self.queue.drain())

        self.clock += 1.0
        self.queue.append(map_event(self._eventData['compute.instance.create.end']))
        datamaps.extend(self.queue.drain())

        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNone(instance5, msg="Incremental model deferred creation of instance 'instance5'")

        self.assertEquals(len(datamaps), 0, "No instances were created early")

        # allow time for the events to be released
        self.clock += 120.0
        datamaps.extend(self.queue.drain())

        self.assertEquals(len(datamaps), 1, "Instance created after sufficient time has passed")

        self.clock += 5.0
        self.queue.append(map_event(self._eventData['compute.instance.delete.start']))
        datamaps.extend(self.queue.drain())
        self.queue.append(map_event(self._eventData['compute.instance.shutdown.start']))
        datamaps.extend(self.queue.drain())

        self.clock += 1.0
        self.queue.append(map_event(self._eventData['compute.instance.shutdown.end']))
        datamaps.extend(self.queue.drain())
        self.queue.append(map_event(self._eventData['compute.instance.delete.end']))
        datamaps.extend(self.queue.drain())

        self.assertTrue(
            (len(datamaps) == 2 and datamaps[1]._remove),
            msg="Instance deleted as expected")


@monkeypatch('Products.DataCollector.ApplyDataMap.ApplyDataMap')
def logChange(self, device, compname, eventClass, msg):
    logging.getLogger('zen.ApplyDataMap').info(msg)


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestEventMappings))
    return suite


if __name__ == "__main__":
    from zope.testrunner.runner import Runner
    runner = Runner(found_suites=[test_suite()])
    runner.run()
