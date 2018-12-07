#!/usr/bin/env python

###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2017-2018, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

from collections import Counter
import os
import json
import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('zen.OpenStackInfrastructure')

from twisted.internet import defer

import Globals

from Products.DataCollector.DeviceProxy import DeviceProxy
from Products.ZenTestCase.BaseTestCase import BaseTestCase
from Products.ZenUtils.Utils import unused

from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import setup_crochet
from ZenPacks.zenoss.OpenStackInfrastructure.modeler.plugins.zenoss.OpenStackInfrastructure \
    import OpenStackInfrastructure as OpenStackInfrastructureModeler

from Products.ZenModel import Device
from ZenPacks.zenoss.OpenStackInfrastructure import hostmap
from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import all_objmaps


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


# Test the 'process' method of the modeler with the normal test data, as well
# as some variations

class TestModelProcess(BaseTestCase):

    disableLogging = False

    def tearDown(self):
        super(TestModelProcess, self).tearDown()
        Device.getHostByName = self._real_getHostByName
        hostmap.resolve_names = self._real_resolve_names

    def afterSetUp(self):
        super(TestModelProcess, self).afterSetUp()

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

        self.d = DeviceProxy()
        self.d.zOpenStackHostDeviceClass = '/Server/SSH/Linux/NovaHost'
        self.d.zOpenStackRegionName = 'RegionOne'
        self.d.zOpenStackAuthUrl = 'http://1.2.3.4:5000/v2.0'
        self.d.zOpenStackNovaApiHosts = []
        self.d.zOpenStackExtraHosts = []
        self.d.zOpenStackHostMapToId = []
        self.d.zOpenStackHostMapSame = []
        self.d.zOpenStackHostLocalDomain = ''
        self.d.zOpenStackExtraApiEndpoints = []
        self.d.get_host_mappings = {}

        # # Required to prevent erroring out when trying to define viewlets in
        # # ../browser/configure.zcml.
        # import zope.viewlet
        # zcml.load_config('meta.zcml', zope.viewlet)

        # import ZenPacks.zenoss.OpenStackInfrastructure
        # zcml.load_config('configure.zcml', ZenPacks.zenoss.OpenStackInfrastructure)
        self.data = self._loadTestData()

    @crochet.wait_for(timeout=30)
    def _preprocessHosts(self, modeler, results):
        return modeler.preprocess_hosts(self.d, results)

    def _loadTestData(self):
        with open(os.path.join(os.path.dirname(__file__),
                               'data',
                               'model',
                               'base.json')) as json_file:
            return json.load(json_file)

    def _processTestData(self, data):
        modeler = OpenStackInfrastructureModeler()
        self._preprocessHosts(modeler, data)
        return modeler.process(self.d, data, log)

    def testNoAgents(self):
        # Test situation where the neutron 'agents' call doesn't work on
        # the target environment.  (ZPS-1243)

        data = self.data.copy()

        # no neutron agents available on this target..
        data['agents'] = []

        # We basically just want this to not throw any exceptions.
        self._processTestData(data)

    def testAccessIPs(self):
        # the test data doesn't have any instances with these properties set-
        # just go ahead and add them, and make sure we model them.
        data = self.data.copy()

        data['servers'][0]['accessIPv4'] = "127.0.0.1"
        data['servers'][0]['accessIPv6'] = "::1"
        server_id = 'server-' + data['servers'][0]['id']

        for objmap in all_objmaps(self._processTestData(data)):
            if getattr(objmap, 'id', None) == server_id:
                self.assertIn("127.0.0.1", objmap.publicIps)
                self.assertIn("::1", objmap.publicIps)

    def testDefaultModel(self):
        data = self.data.copy()
        obj_map = {}
        type_count = Counter()
        for om in all_objmaps(self._processTestData(data)):
            om_dict = {k: v for k, v in om.__dict__.iteritems() if k != '_attrs'}
            obj_map[getattr(om, 'id', None)] = om_dict
            type_count[om.modname] += 1

        # from pprint import pformat
        # for id_ in sorted(obj_map):
        #     print "        self.assertEquals(obj_map['%s'], %s)" % (id_, pformat(obj_map[id_]))
        #     print ""

        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.ApiEndpoint'], 1)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.AvailabilityZone'], 2)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.CinderApi'], 1)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.CinderService'], 3)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Endpoint'], 1)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Flavor'], 5)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.FloatingIp'], 4)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Host'], 6)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Hypervisor'], 1)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Image'], 1)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Instance'], 1)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Network'], 2)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.NeutronAgent'], 5)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.NovaApi'], 1)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.NovaService'], 5)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Pool'], 1)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Port'], 4)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Quota'], 3)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Region'], 1)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Router'], 1)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Subnet'], 2)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Tenant'], 3)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.VolSnapshot'], 1)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.VolType'], 2)
        self.assertEquals(type_count['ZenPacks.zenoss.OpenStackInfrastructure.Volume'], 2)

        self.assertEquals(obj_map['agent-37c80256-d843-45c3-a9b6-fb0fde13ac89'], {
            'agentId': u'37c80256-d843-45c3-a9b6-fb0fde13ac89',
            'binary': u'f5-oslbaasv1-agent',
            'enabled': True,
            'id': 'agent-37c80256-d843-45c3-a9b6-fb0fde13ac89',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.NeutronAgent',
            'operStatus': 'UP',
            'set_hostedOn': 'host-overcloud-controller-1.localdomain',
            'set_networks': [],
            'set_orgComponent': 'region-RegionOne',
            'set_routers': [],
            'set_subnets': [],
            'title': 'Loadbalancer agent@overcloud-controller-1.localdomain',
            'type': u'Loadbalancer agent'})

        self.assertEquals(obj_map['agent-ee6407f6-9b13-4df4-8da0-cb751c410af5'], {
            'agentId': u'ee6407f6-9b13-4df4-8da0-cb751c410af5',
            'binary': u'neutron-l3-agent',
            'enabled': True,
            'id': 'agent-ee6407f6-9b13-4df4-8da0-cb751c410af5',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.NeutronAgent',
            'operStatus': 'UP',
            'set_hostedOn': 'host-liberty.zenoss.local',
            'set_networks': ['network-a13b2c35-d734-4021-9850-432dfa7fa7a3'],
            'set_orgComponent': 'zone-nova',
            'set_routers': ['router-88b70ee0-4204-4a88-b9c5-dd49588d5c1a'],
            'set_subnets': ['subnet-efe34b3a-a35c-4a0e-9769-e1fd79d7ca2d'],
            'title': 'L3 agent@liberty.zenoss.local',
            'type': u'L3 agent'})

        self.assertEquals(obj_map['agent-f3b165ca-d869-4a1f-a8da-361f2177da5b'], {
            'agentId': u'f3b165ca-d869-4a1f-a8da-361f2177da5b',
            'binary': u'neutron-metadata-agent',
            'enabled': True,
            'id': 'agent-f3b165ca-d869-4a1f-a8da-361f2177da5b',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.NeutronAgent',
            'operStatus': 'UP',
            'set_hostedOn': 'host-liberty.zenoss.local',
            'set_networks': [],
            'set_orgComponent': 'zone-nova',
            'set_routers': [],
            'set_subnets': [],
            'title': 'Metadata agent@liberty.zenoss.local',
            'type': u'Metadata agent'})

        self.assertEquals(obj_map['agent-f9697d9c-580e-4917-8c87-1b69ab53e5a6'], {
            'agentId': u'f9697d9c-580e-4917-8c87-1b69ab53e5a6',
            'binary': u'neutron-openvswitch-agent',
            'enabled': True,
            'id': 'agent-f9697d9c-580e-4917-8c87-1b69ab53e5a6',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.NeutronAgent',
            'operStatus': 'UP',
            'set_hostedOn': 'host-liberty.zenoss.local',
            'set_networks': [],
            'set_orgComponent': 'zone-nova',
            'set_routers': [],
            'set_subnets': [],
            'title': 'Open vSwitch agent@liberty.zenoss.local',
            'type': u'Open vSwitch agent'})

        self.assertEquals(obj_map['agent-fade4d15-487c-4998-ac80-bff91b4532e9'], {
            'agentId': u'fade4d15-487c-4998-ac80-bff91b4532e9',
            'binary': u'neutron-dhcp-agent',
            'enabled': True,
            'id': 'agent-fade4d15-487c-4998-ac80-bff91b4532e9',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.NeutronAgent',
            'operStatus': 'UP',
            'set_hostedOn': 'host-liberty.zenoss.local',
            'set_networks': ['network-7a2d66f2-35e6-4459-92b9-260411a39039',
                             'network-a13b2c35-d734-4021-9850-432dfa7fa7a3'],
            'set_orgComponent': 'zone-nova',
            'set_routers': [],
            'set_subnets': ['subnet-85085b15-4f2f-4457-ae31-0cfe1d5d301c',
                            'subnet-efe34b3a-a35c-4a0e-9769-e1fd79d7ca2d'],
            'title': 'DHCP agent@liberty.zenoss.local',
            'type': u'DHCP agent'})

        self.assertEquals(obj_map['apiendpoint-zOpenStackAuthUrl'], {
            'id': 'apiendpoint-zOpenStackAuthUrl',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.ApiEndpoint',
            'service_type': 'identity',
            'source': 'zOpenStackAuthUrl',
            'title': 'http://1.2.3.4:5000/v2.0',
            'url': 'http://1.2.3.4:5000/v2.0'})

        self.assertEquals(obj_map['flavor-1'], {
            'flavorDisk': 1073741824,
            'flavorId': u'1',
            'flavorRAM': 536870912,
            'flavorType': 'True',
            'flavorVCPUs': 1,
            'id': 'flavor-1',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Flavor',
            'title': u'm1.tiny'})

        self.assertEquals(obj_map['flavor-2'], {
            'flavorDisk': 21474836480,
            'flavorId': u'2',
            'flavorRAM': 2147483648,
            'flavorType': 'True',
            'flavorVCPUs': 1,
            'id': 'flavor-2',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Flavor',
            'title': u'm1.small'})

        self.assertEquals(obj_map['flavor-3'], {
            'flavorDisk': 42949672960,
            'flavorId': u'3',
            'flavorRAM': 4294967296,
            'flavorType': 'True',
            'flavorVCPUs': 2,
            'id': 'flavor-3',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Flavor',
            'title': u'm1.medium'})

        self.assertEquals(obj_map['flavor-4'], {
            'flavorDisk': 85899345920,
            'flavorId': u'4',
            'flavorRAM': 8589934592,
            'flavorType': 'True',
            'flavorVCPUs': 4,
            'id': 'flavor-4',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Flavor',
            'title': u'm1.large'})

        self.assertEquals(obj_map['flavor-5'], {
            'flavorDisk': 171798691840,
            'flavorId': u'5',
            'flavorRAM': 17179869184,
            'flavorType': 'False',
            'flavorVCPUs': 8,
            'id': 'flavor-5',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Flavor',
            'title': u'm1.xlarge'})

        self.assertEquals(obj_map['floatingip-7fc91b6e-6135-4ca3-932b-7f437c77ff45'], {
            'fixed_ip_address': None,
            'floating_ip_address': u'10.239.180.102',
            'floatingipId': u'7fc91b6e-6135-4ca3-932b-7f437c77ff45',
            'id': 'floatingip-7fc91b6e-6135-4ca3-932b-7f437c77ff45',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.FloatingIp',
            'set_network': 'network-a13b2c35-d734-4021-9850-432dfa7fa7a3',
            'set_port': 'port-2ce7575f-5368-4a33-b67d-17b4718cf77c',
            'set_router': 'router-88b70ee0-4204-4a88-b9c5-dd49588d5c1a',
            'set_tenant': 'tenant-e6bae7721b8745ce8b14f3908de17b8c',
            'status': u'DOWN'})

        self.assertEquals(obj_map['floatingip-8a5b5177-4100-445e-b085-836276a3e0c6'], {
            'fixed_ip_address': None,
            'floating_ip_address': u'10.239.180.103',
            'floatingipId': u'8a5b5177-4100-445e-b085-836276a3e0c6',
            'id': 'floatingip-8a5b5177-4100-445e-b085-836276a3e0c6',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.FloatingIp',
            'set_network': 'network-a13b2c35-d734-4021-9850-432dfa7fa7a3',
            'set_port': 'port-2ce7575f-5368-4a33-b67d-17b4718cf77c',
            'set_router': 'router-88b70ee0-4204-4a88-b9c5-dd49588d5c1a',
            'set_tenant': 'tenant-e6bae7721b8745ce8b14f3908de17b8c',
            'status': u'DOWN'})

        self.assertEquals(obj_map['floatingip-c3d558d1-5ed7-4488-9529-1ed8d47412c1'], {
            'fixed_ip_address': None,
            'floating_ip_address': u'10.239.180.101',
            'floatingipId': u'c3d558d1-5ed7-4488-9529-1ed8d47412c1',
            'id': 'floatingip-c3d558d1-5ed7-4488-9529-1ed8d47412c1',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.FloatingIp',
            'set_network': 'network-a13b2c35-d734-4021-9850-432dfa7fa7a3',
            'set_port': 'port-2ce7575f-5368-4a33-b67d-17b4718cf77c',
            'set_router': 'router-88b70ee0-4204-4a88-b9c5-dd49588d5c1a',
            'set_tenant': 'tenant-e6bae7721b8745ce8b14f3908de17b8c',
            'status': u'ACTIVE'})

        self.assertEquals(obj_map['floatingip-d61d4dff-b941-4359-bd95-db6110364796'], {
            'fixed_ip_address': None,
            'floating_ip_address': u'10.239.180.100',
            'floatingipId': u'd61d4dff-b941-4359-bd95-db6110364796',
            'id': 'floatingip-d61d4dff-b941-4359-bd95-db6110364796',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.FloatingIp',
            'set_network': 'network-a13b2c35-d734-4021-9850-432dfa7fa7a3',
            'set_port': 'port-2ce7575f-5368-4a33-b67d-17b4718cf77c',
            'set_router': 'router-88b70ee0-4204-4a88-b9c5-dd49588d5c1a',
            'set_tenant': 'tenant-28a2787a215a4187b22f800f51e58665',
            'status': u'DOWN'})

        self.assertEquals(obj_map['host-bugs.zenoss.local'], {
            'host_ip': None,
            'hostname': 'bugs.zenoss.local',
            'id': 'host-bugs.zenoss.local',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Host',
            'set_orgComponent': 'zone-internal',
            'title': 'bugs.zenoss.local'})

        self.assertEquals(obj_map['host-leghorn.zenoss.local'], {
            'host_ip': None,
            'hostname': 'leghorn.zenoss.local',
            'id': 'host-leghorn.zenoss.local',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Host',
            'set_orgComponent': 'zone-internal',
            'title': 'leghorn.zenoss.local'})

        self.assertEquals(obj_map['host-liberty.zenoss'], {
            'host_ip': None,
            'hostname': 'liberty.zenoss',
            'id': 'host-liberty.zenoss',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Host',
            'set_orgComponent': 'zone-nova',
            'title': 'liberty.zenoss'})

        self.assertEquals(obj_map['host-liberty.zenoss.local'], {
            'host_ip': '192.168.56.122',
            'hostname': 'liberty.zenoss.local',
            'id': 'host-liberty.zenoss.local',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Host',
            'set_orgComponent': 'zone-internal',
            'title': 'liberty.zenoss.local'})

        self.assertEquals(obj_map['host-overcloud-controller-1.localdomain'], {
            'host_ip': '10.88.0.100',
            'hostname': 'overcloud-controller-1.localdomain',
            'id': 'host-overcloud-controller-1.localdomain',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Host',
            'set_orgComponent': 'region-RegionOne',
            'title': 'overcloud-controller-1.localdomain'})

        self.assertEquals(obj_map['host-wily.zenoss.local'], {
            'host_ip': None,
            'hostname': 'wily.zenoss.local',
            'id': 'host-wily.zenoss.local',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Host',
            'set_orgComponent': 'zone-internal',
            'title': 'wily.zenoss.local'})

        self.assertEquals(obj_map['hypervisor-1'], {
            'disk': 17,
            'disk_free': 16,
            'disk_used': 1,
            'host_ip': u'10.0.2.34',
            'hstate': u'UP',
            'hstatus': u'ENABLED',
            'hypervisorId': 1,
            'hypervisor_type': u'QEMU',
            'hypervisor_version': '1.5.3',
            'id': 'hypervisor-1',
            'memory': 3791,
            'memory_free': 2767,
            'memory_used': 1024,
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Hypervisor',
            'set_hostByName': u'liberty.zenoss.local',
            'set_instances': [],
            'title': 'liberty.zenoss.local.1',
            'vcpus': 1,
            'vcpus_used': 1})

        self.assertEquals(obj_map['image-b5ac0c5f-bf91-4ab6-bcaa-d895a8df90bb'], {
            'id': 'image-b5ac0c5f-bf91-4ab6-bcaa-d895a8df90bb',
            'imageCreated': '2015/10/30 16:00:13.000',
            'imageId': u'b5ac0c5f-bf91-4ab6-bcaa-d895a8df90bb',
            'imageStatus': u'ACTIVE',
            'imageUpdated': '2015/10/30 16:00:15.000',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Image',
            'title': u'cirros'})

        self.assertEquals(obj_map['network-7a2d66f2-35e6-4459-92b9-260411a39039'], {
            'admin_state_up': True,
            'id': 'network-7a2d66f2-35e6-4459-92b9-260411a39039',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Network',
            'netExternal': False,
            'netId': u'7a2d66f2-35e6-4459-92b9-260411a39039',
            'netStatus': u'ACTIVE',
            'netType': u'VXLAN',
            'set_tenant': 'tenant-28a2787a215a4187b22f800f51e58665',
            'title': u'private'})

        self.assertEquals(obj_map['network-a13b2c35-d734-4021-9850-432dfa7fa7a3'], {
            'admin_state_up': True,
            'id': 'network-a13b2c35-d734-4021-9850-432dfa7fa7a3',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Network',
            'netExternal': True,
            'netId': u'a13b2c35-d734-4021-9850-432dfa7fa7a3',
            'netStatus': u'ACTIVE',
            'netType': u'VXLAN',
            'set_tenant': 'tenant-e6bae7721b8745ce8b14f3908de17b8c',
            'title': u'public'})

        self.assertEquals(obj_map['pool-liberty.zenoss.local_lvm_lvm'], {
            'allocated_capacity': ('2 GB',),
            'driver_version': u'3.0.0',
            'free_capacity': ('17.6 GB',),
            'id': 'pool-liberty.zenoss.local_lvm_lvm',
            'location': u'LVMVolumeDriver:liberty.zenoss.local:cinder-volumes:default:0',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Pool',
            'qos_support': False,
            'reserved_percentage': '0%',
            'storage_protocol': u'iSCSI',
            'title': u'liberty.zenoss.local@lvm#lvm',
            'total_capacity': ('20.6 GB',),
            'vendor_name': u'Open Source',
            'volume_backend': 0})

        self.assertEquals(obj_map['port-027d0591-d2d7-412c-977e-5a42fd2d0277'], {
            'admin_state_up': True,
            'device_owner': u'network:router_gateway',
            'fixed_ip_list': u'172.24.4.226',
            'id': 'port-027d0591-d2d7-412c-977e-5a42fd2d0277',
            'mac_address': u'FA:16:3E:1F:6A:CC',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Port',
            'portId': u'027d0591-d2d7-412c-977e-5a42fd2d0277',
            'set_network': 'network-a13b2c35-d734-4021-9850-432dfa7fa7a3',
            'set_subnets': ['subnet-efe34b3a-a35c-4a0e-9769-e1fd79d7ca2d'],
            'status': u'DOWN',
            'title': u'',
            'vif_type': u'ovs'})

        self.assertEquals(obj_map['port-2ce7575f-5368-4a33-b67d-17b4718cf77c'], {
            'admin_state_up': True,
            'device_owner': u'compute:nova',
            'fixed_ip_list': u'10.0.0.3',
            'id': 'port-2ce7575f-5368-4a33-b67d-17b4718cf77c',
            'mac_address': u'FA:16:3E:04:6D:E6',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Port',
            'portId': u'2ce7575f-5368-4a33-b67d-17b4718cf77c',
            'set_instance': 'server-0aa87c33-aa73-4c02-976b-321f5e2df205',
            'set_network': 'network-7a2d66f2-35e6-4459-92b9-260411a39039',
            'set_subnets': ['subnet-85085b15-4f2f-4457-ae31-0cfe1d5d301c'],
            'set_tenant': 'tenant-28a2787a215a4187b22f800f51e58665',
            'status': u'ACTIVE',
            'title': u'',
            'vif_type': u'ovs'})

        self.assertEquals(obj_map['port-65fae58a-3d6b-4e8d-acc1-f9a43c0b7d31'], {
            'admin_state_up': True,
            'device_owner': u'network:router_interface',
            'fixed_ip_list': u'10.0.0.1',
            'id': 'port-65fae58a-3d6b-4e8d-acc1-f9a43c0b7d31',
            'mac_address': u'FA:16:3E:BF:BE:AF',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Port',
            'portId': u'65fae58a-3d6b-4e8d-acc1-f9a43c0b7d31',
            'set_network': 'network-7a2d66f2-35e6-4459-92b9-260411a39039',
            'set_router': 'router-88b70ee0-4204-4a88-b9c5-dd49588d5c1a',
            'set_subnets': ['subnet-85085b15-4f2f-4457-ae31-0cfe1d5d301c'],
            'set_tenant': 'tenant-28a2787a215a4187b22f800f51e58665',
            'status': u'ACTIVE',
            'title': u'',
            'vif_type': u'ovs'})

        self.assertEquals(obj_map['port-d95c191c-f9fc-4933-9d13-af8f7524046a'], {
            'admin_state_up': True,
            'device_owner': u'network:dhcp',
            'fixed_ip_list': u'10.0.0.2',
            'id': 'port-d95c191c-f9fc-4933-9d13-af8f7524046a',
            'mac_address': u'FA:16:3E:FF:E5:8E',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Port',
            'portId': u'd95c191c-f9fc-4933-9d13-af8f7524046a',
            'set_network': 'network-7a2d66f2-35e6-4459-92b9-260411a39039',
            'set_subnets': ['subnet-85085b15-4f2f-4457-ae31-0cfe1d5d301c'],
            'set_tenant': 'tenant-28a2787a215a4187b22f800f51e58665',
            'status': u'ACTIVE',
            'title': u'',
            'vif_type': u'ovs'})

        self.assertEquals(obj_map['quota-28a2787a215a4187b22f800f51e58665'], {
            'backup_bytes': 1000,
            'backups': 10,
            'bytes': 1000,
            'id': 'quota-28a2787a215a4187b22f800f51e58665',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Quota',
            'set_tenant': 'tenant-28a2787a215a4187b22f800f51e58665',
            'snapshots': 10,
            'tenant_name': u'demo',
            'volumes': 10})

        self.assertEquals(obj_map['quota-5b79c3f4df73447a9850887b2ea17372'], {
            'backup_bytes': 1000,
            'backups': 10,
            'bytes': 1000,
            'id': 'quota-5b79c3f4df73447a9850887b2ea17372',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Quota',
            'set_tenant': 'tenant-5b79c3f4df73447a9850887b2ea17372',
            'snapshots': 10,
            'tenant_name': u'services',
            'volumes': 10})

        self.assertEquals(obj_map['quota-e6bae7721b8745ce8b14f3908de17b8c'], {
            'backup_bytes': 1000,
            'backups': 10,
            'bytes': 1000,
            'id': 'quota-e6bae7721b8745ce8b14f3908de17b8c',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Quota',
            'set_tenant': 'tenant-e6bae7721b8745ce8b14f3908de17b8c',
            'snapshots': 10,
            'tenant_name': u'admin',
            'volumes': 10})

        self.assertEquals(obj_map['region-RegionOne'], {
            'id': 'region-RegionOne',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Region',
            'title': 'RegionOne'})

        self.assertEquals(obj_map['router-88b70ee0-4204-4a88-b9c5-dd49588d5c1a'], {
            'admin_state_up': True,
            'gateways': [u'172.24.4.226'],
            'id': 'router-88b70ee0-4204-4a88-b9c5-dd49588d5c1a',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Router',
            'routerId': u'88b70ee0-4204-4a88-b9c5-dd49588d5c1a',
            'routes': [],
            'set_network': 'network-a13b2c35-d734-4021-9850-432dfa7fa7a3',
            'set_subnets': ['subnet-85085b15-4f2f-4457-ae31-0cfe1d5d301c',
                            'subnet-efe34b3a-a35c-4a0e-9769-e1fd79d7ca2d'],
            'set_tenant': 'tenant-28a2787a215a4187b22f800f51e58665',
            'status': u'ACTIVE',
            'title': u'router1'})

        self.assertEquals(obj_map['server-0aa87c33-aa73-4c02-976b-321f5e2df205'], {
            'hostId': u'859a4c2e77ea1fc6c2afde71dd6a5d98c0696f1065e3cc6855e91b03',
            'hostName': u'tiny1',
            'id': 'server-0aa87c33-aa73-4c02-976b-321f5e2df205',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Instance',
            'powerState': 'shutdown',
            'privateIps': [u'10.0.0.3'],
            'publicIps': [],
            'resourceId': u'0aa87c33-aa73-4c02-976b-321f5e2df205',
            'serverBackupDaily': 'DISABLED',
            'serverBackupEnabled': False,
            'serverBackupWeekly': 'DISABLED',
            'serverId': u'0aa87c33-aa73-4c02-976b-321f5e2df205',
            'serverStatus': u'shutoff',
            'set_flavor': 'flavor-1',
            'set_image': 'image-b5ac0c5f-bf91-4ab6-bcaa-d895a8df90bb',
            'set_tenant': 'tenant-28a2787a215a4187b22f800f51e58665',
            'taskState': 'no task in progress',
            'title': u'tiny1',
            'vmState': u'stopped'})

        self.assertEquals(obj_map['service-cinder-api-liberty.zenoss.local-RegionOne'], {
            'binary': 'cinder-api',
            'id': 'service-cinder-api-liberty.zenoss.local-RegionOne',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.CinderApi',
            'set_hostedOn': 'host-liberty.zenoss.local',
            'set_orgComponent': 'region-RegionOne',
            'title': 'cinder-api@liberty.zenoss.local (RegionOne)'})

        self.assertEquals(obj_map['service-cinder-backup-liberty.zenoss.local-nova'], {
            'binary': u'cinder-backup',
            'enabled': False,
            'id': 'service-cinder-backup-liberty.zenoss.local-nova',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.CinderService',
            'operStatus': 'DOWN',
            'set_hostedOn': 'host-liberty.zenoss.local',
            'set_orgComponent': 'zone-nova',
            'title': 'cinder-backup@liberty.zenoss.local (nova)'})

        self.assertEquals(obj_map['service-cinder-scheduler-liberty.zenoss-nova'], {
            'binary': u'cinder-scheduler',
            'enabled': True,
            'id': 'service-cinder-scheduler-liberty.zenoss-nova',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.CinderService',
            'operStatus': 'UP',
            'set_hostedOn': 'host-liberty.zenoss',
            'set_orgComponent': 'zone-nova',
            'title': 'cinder-scheduler@liberty.zenoss (nova)'})

        self.assertEquals(obj_map['service-cinder-volume-liberty.zenoss.local-nova'], {
            'binary': u'cinder-volume',
            'enabled': True,
            'id': 'service-cinder-volume-liberty.zenoss.local-nova',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.CinderService',
            'operStatus': 'UP',
            'set_hostedOn': 'host-liberty.zenoss.local',
            'set_orgComponent': 'zone-nova',
            'title': 'cinder-volume@liberty.zenoss.local (nova)'})

        self.assertEquals(obj_map['service-nova-api-liberty.zenoss.local-RegionOne'], {
            'binary': 'nova-api',
            'id': 'service-nova-api-liberty.zenoss.local-RegionOne',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.NovaApi',
            'set_hostedOn': 'host-liberty.zenoss.local',
            'set_orgComponent': 'region-RegionOne',
            'title': 'nova-api@liberty.zenoss.local (RegionOne)'})

        self.assertEquals(obj_map['service-nova-cert-leghorn.zenoss.local-internal'], {
            'binary': u'nova-cert',
            'enabled': True,
            'id': 'service-nova-cert-leghorn.zenoss.local-internal',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.NovaService',
            'operStatus': 'UP',
            'set_hostedOn': 'host-leghorn.zenoss.local',
            'set_orgComponent': 'zone-internal',
            'title': 'nova-cert@leghorn.zenoss.local (internal)'})

        self.assertEquals(obj_map['service-nova-compute-liberty.zenoss.local-nova'], {
            'binary': u'nova-compute',
            'enabled': True,
            'id': 'service-nova-compute-liberty.zenoss.local-nova',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.NovaService',
            'operStatus': 'UP',
            'set_hostedOn': 'host-liberty.zenoss.local',
            'set_orgComponent': 'zone-nova',
            'title': 'nova-compute@liberty.zenoss.local (nova)'})

        self.assertEquals(obj_map['service-nova-conductor-wily.zenoss.local-internal'], {
            'binary': u'nova-conductor',
            'enabled': True,
            'id': 'service-nova-conductor-wily.zenoss.local-internal',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.NovaService',
            'operStatus': 'UP',
            'set_hostedOn': 'host-wily.zenoss.local',
            'set_orgComponent': 'zone-internal',
            'title': 'nova-conductor@wily.zenoss.local (internal)'})

        self.assertEquals(obj_map['service-nova-consoleauth-liberty.zenoss.local-internal'], {
            'binary': u'nova-consoleauth',
            'enabled': True,
            'id': 'service-nova-consoleauth-liberty.zenoss.local-internal',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.NovaService',
            'operStatus': 'UP',
            'set_hostedOn': 'host-liberty.zenoss.local',
            'set_orgComponent': 'zone-internal',
            'title': 'nova-consoleauth@liberty.zenoss.local (internal)'})

        self.assertEquals(obj_map['service-nova-scheduler-bugs.zenoss.local-internal'], {
            'binary': u'nova-scheduler',
            'enabled': True,
            'id': 'service-nova-scheduler-bugs.zenoss.local-internal',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.NovaService',
            'operStatus': 'UP',
            'set_hostedOn': 'host-bugs.zenoss.local',
            'set_orgComponent': 'zone-internal',
            'title': 'nova-scheduler@bugs.zenoss.local (internal)'})

        self.assertEquals(obj_map['snapshot-7bae1e24-47db-4d63-90e1-a5b02d112fb1'], {
            'created_at': u'2015-12-16 19:45:59.000000',
            'description': u'Linux volume 1 GB snapshot',
            'id': 'snapshot-7bae1e24-47db-4d63-90e1-a5b02d112fb1',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.VolSnapshot',
            'set_tenant': 'tenant-28a2787a215a4187b22f800f51e58665',
            'set_volume': 'volume-281a7105-935a-4bcf-a4b5-cf5e652d2daa',
            'size': 1,
            'status': u'AVAILABLE',
            'title': u'vol-GB1-snapshot'})

        self.assertEquals(obj_map['subnet-85085b15-4f2f-4457-ae31-0cfe1d5d301c'], {
            'cidr': u'10.0.0.0/24',
            'dns_nameservers': [],
            'gateway_ip': u'10.0.0.1',
            'id': 'subnet-85085b15-4f2f-4457-ae31-0cfe1d5d301c',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Subnet',
            'set_network': 'network-7a2d66f2-35e6-4459-92b9-260411a39039',
            'set_tenant': 'tenant-28a2787a215a4187b22f800f51e58665',
            'subnetId': u'85085b15-4f2f-4457-ae31-0cfe1d5d301c',
            'title': u'private_subnet'})

        self.assertEquals(obj_map['subnet-efe34b3a-a35c-4a0e-9769-e1fd79d7ca2d'], {
            'cidr': u'172.24.4.224/28',
            'dns_nameservers': [],
            'gateway_ip': u'172.24.4.225',
            'id': 'subnet-efe34b3a-a35c-4a0e-9769-e1fd79d7ca2d',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Subnet',
            'set_network': 'network-a13b2c35-d734-4021-9850-432dfa7fa7a3',
            'set_tenant': 'tenant-e6bae7721b8745ce8b14f3908de17b8c',
            'subnetId': u'efe34b3a-a35c-4a0e-9769-e1fd79d7ca2d',
            'title': u'public_subnet'})

        self.assertEquals(obj_map['tenant-28a2787a215a4187b22f800f51e58665'], {
            'description': u'default tenant',
            'id': 'tenant-28a2787a215a4187b22f800f51e58665',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Tenant',
            'tenantId': u'28a2787a215a4187b22f800f51e58665',
            'title': u'demo'})

        self.assertEquals(obj_map['tenant-5b79c3f4df73447a9850887b2ea17372'], {
            'description': u'Tenant for the openstack services',
            'id': 'tenant-5b79c3f4df73447a9850887b2ea17372',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Tenant',
            'tenantId': u'5b79c3f4df73447a9850887b2ea17372',
            'title': u'services'})

        self.assertEquals(obj_map['tenant-e6bae7721b8745ce8b14f3908de17b8c'], {
            'description': u'admin tenant',
            'id': 'tenant-e6bae7721b8745ce8b14f3908de17b8c',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Tenant',
            'tenantId': u'e6bae7721b8745ce8b14f3908de17b8c',
            'title': u'admin'})

        self.assertEquals(obj_map['volType-033af14f-b609-45e3-aed2-5b2e02d44c8f'], {
            'id': 'volType-033af14f-b609-45e3-aed2-5b2e02d44c8f',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.VolType',
            'title': u'ceph'})

        self.assertEquals(obj_map['volType-6e2e993c-110e-4aaf-a79b-a44acc533051'], {
            'id': 'volType-6e2e993c-110e-4aaf-a79b-a44acc533051',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.VolType',
            'title': u'lvm'})

        self.assertEquals(obj_map['volume-281a7105-935a-4bcf-a4b5-cf5e652d2daa'], {
            'avzone': u'nova',
            'bootable': u'FALSE',
            'created_at': u'2015-10-30 18:15:46.000000',
            'backend': u'liberty.zenoss.local@lvm#lvm',
            'id': 'volume-281a7105-935a-4bcf-a4b5-cf5e652d2daa',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Volume',
            'set_instance': 'server-0aa87c33-aa73-4c02-976b-321f5e2df205',
            'set_tenant': 'tenant-28a2787a215a4187b22f800f51e58665',
            'size': 1,
            'sourceVolumeId': None,
            'status': u'IN-USE',
            'title': u'vol-GB1',
            'volumeId': u'281a7105-935a-4bcf-a4b5-cf5e652d2daa'})

        self.assertEquals(obj_map['volume-c3aabf8c-9f44-41c7-b962-e50e1f5936ff'], {
            'avzone': u'nova',
            'bootable': u'FALSE',
            'created_at': u'2015-12-16 19:44:25.000000',
            'backend': u'liberty.zenoss.local@lvm#lvm',
            'id': 'volume-c3aabf8c-9f44-41c7-b962-e50e1f5936ff',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.Volume',
            'set_tenant': 'tenant-28a2787a215a4187b22f800f51e58665',
            'size': 1,
            'sourceVolumeId': None,
            'status': u'AVAILABLE',
            'title': u'vol-GB1-2',
            'volumeId': u'c3aabf8c-9f44-41c7-b962-e50e1f5936ff'})

        self.assertEquals(obj_map['zone-internal'], {
            'id': 'zone-internal',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.AvailabilityZone',
            'set_parentOrg': 'region-RegionOne',
            'title': u'internal'})

        self.assertEquals(obj_map['zone-nova'], {
            'id': 'zone-nova',
            'modname': 'ZenPacks.zenoss.OpenStackInfrastructure.AvailabilityZone',
            'set_parentOrg': 'region-RegionOne',
            'title': u'nova'})


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestModelProcess))
    return suite


if __name__ == "__main__":
    from zope.testrunner.runner import Runner
    runner = Runner(found_suites=[test_suite()])
    runner.run()
