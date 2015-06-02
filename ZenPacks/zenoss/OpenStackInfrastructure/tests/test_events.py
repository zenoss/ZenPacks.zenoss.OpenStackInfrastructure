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

    def afterSetUp(self):
        # needed if this is run directly on the commandline,
        # since otherwise it will be __main__, and ZPL's afterSetup
        # will get confused.
        self.__module__ = 'ZenPacks.zenoss.OpenStackInfrastructure.tests.test_impact'
        super(TestEventTransforms, self).afterSetUp()

        # Quiet down some noisy logging.
        # logging.getLogger('zen.OpenStackDeviceProxyComponent').setLevel(logging.ERROR)

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
        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|scheduler.run_instance.end',
            'eventKey': u'07180940-d533-43ee-b5a7-930108e6238f',
            'severity': 2,
            'summary': '',
            u'trait_request_id': u'req-28e885ca-6d7d-4e5d-8182-830edd2eb2b3',
            u'trait_service': u'scheduler.computehost1',
            u'trait_tenant_id': u'tenant1'
        })
        self.process_event(evt)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.create.start',
            'eventKey': u'bc58885b-7677-4a10-9f4a-133a696dc6ab',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_image_name': u'image1',
            u'trait_instance_id': u'instance5',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-28e885ca-6d7d-4e5d-8182-830edd2eb2b3',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'building',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1
        })
        self.process_event(evt)

        instance5 = self.getObjByPath('components/server-instance5')

        self.assertIsNotNone(instance5, msg="Incremental model created instance 'instance5'")

        self.assertTrue(instance5.publicIps is None or instance5.publicIps == [])
        self.assertTrue(instance5.privateIps is None or instance5.privateIps == [])

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.create.end',
            'eventKey': u'd207460b-2e8a-48e0-917a-cebb07b063a5',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_fixed_ips': u"[{u'floating_ips': [], u'label': u'public', u'version': 4, u'meta': {}, u'address': u'172.24.4.229', u'type': u'fixed'}]",
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_image_name': u'image1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-02T20:20:24.933700',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-28e885ca-6d7d-4e5d-8182-830edd2eb2b3',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'active',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1
        })
        self.process_event(evt)

        self.assertTrue(instance5.privateIps == [u'172.24.4.229'])
        self.assertTrue(instance5.publicIps is None or instance5.publicIps == [])

    def _create_instance5(self):
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
        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        self.assertTrue(instance5.serverStatus.lower() == 'active')

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.power_off.start',
            'eventKey': u'e7be253c-7e5a-445a-aed7-15e09f56c7ac',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-08-05T01:01:02.000000',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-d9b7ee3f-cc3d-4a4b-9f9d-707939a18f35',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'active',
            u'trait_state_description': u'powering-off',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1
        })
        self.process_event(evt)

        self.assertTrue(instance5.serverStatus.lower() == 'active')

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.power_off.end',
            'eventKey': u'c8f2f937-0737-4f2c-b5b1-6b14b162e3e7',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-08-05T01:01:02.000000',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-d9b7ee3f-cc3d-4a4b-9f9d-707939a18f35',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'stopped',
            u'trait_state_description': u'',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1
        })
        self.process_event(evt)

        self.assertTrue(instance5.serverStatus.lower() == 'stopped')
        self.assertTrue(evt.summary == 'Instance instance5 powered off (status changed to stopped)')

    def test_instance_power_on(self):
        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)
        instance5.serverStatus = 'stopped'

        self.assertTrue(instance5.serverStatus.lower() == 'stopped')

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.power_on.start',
            'eventKey': u'66a24089-185b-4df2-ae3c-29854f1c783d',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-05T01:48:54.000000',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-245217ba-e4d9-4c7e-8d59-9cc93b648ac0',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'stopped',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)

        self.assertTrue(instance5.serverStatus.lower() == 'stopped')

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.power_on.end',
            'eventKey': u'05a0aecb-0bbd-4799-b3bc-2db3e89b5654',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-05T01:48:54.000000',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-245217ba-e4d9-4c7e-8d59-9cc93b648ac0',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'active',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)

        self.assertTrue(instance5.serverStatus.lower() == 'active')
        self.assertTrue(evt.summary == 'Instance instance5 powered on (status changed to active)')

    def test_instance_reboot(self):
        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        self.assertTrue(instance5.serverStatus.lower() == 'active')

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.reboot.start',
            'eventKey': u'ab29f32e-125f-4e89-8702-11a734042d4b',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-05T01:48:54.000000',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-29bb4086-13a6-4cbe-af29-892693089b15',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'active',
            u'trait_state_description': u'reboot_pending',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.reboot.end',
            'eventKey': u'94485eb4-763e-40e5-8e97-1c61129e2430',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-05T01:48:54.000000',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-29bb4086-13a6-4cbe-af29-892693089b15',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'active',
            u'trait_state_description': u'',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)
        self.assertTrue(evt.summary == 'Instance instance5 rebooted (status changed to active)')

    def test_instance_rebuild(self):
        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.rebuild.start',
            'eventKey': u'598a5770-bab0-4de3-ac13-4839c6d9e6e3',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_image_name': u'image1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-05T01:48:54.000000',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-a032a4bb-df97-4cf1-b588-f303373f9a39',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'stopped',
            u'trait_state_description': u'rebuilding',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.power_off.start',
            'eventKey': u'f3016ce9-bfb9-40fa-b7c2-05a9d15312bd',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-05T19:50:11.067069',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-a032a4bb-df97-4cf1-b588-f303373f9a39',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'active',
            u'trait_state_description': u'powering-off',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.power_off.end',
            'eventKey': u'189946bf-5727-4800-9d48-1003b5f99a96',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-05T19:50:11.067069',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-a032a4bb-df97-4cf1-b588-f303373f9a39',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'stopped',
            u'trait_state_description': u'',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.rebuild.end',
            'eventKey': u'd6846392-bd1d-4860-87c2-07cb66e7787a',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_fixed_ips': u"[{u'floating_ips': [], u'label': u'public', u'version': 4, u'meta': {}, u'address': u'172.24.4.227', u'type': u'fixed'}]",
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_image_name': u'image1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-05T19:50:11.067069',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-a032a4bb-df97-4cf1-b588-f303373f9a39',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'stopped',
            u'trait_state_description': u'',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)

    def test_instance_suspend_resume(self):
        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.suspend',
            'eventKey': u'252a9e83-cc66-42ab-838a-832f2f49f4bd',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-05T19:50:11.000000',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-b59f0f93-bf8a-41e4-8b4e-bc7c50fb20bb',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'suspended',
            u'trait_state_description': u'',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)
        self.assertTrue(instance5.serverStatus.lower() == 'suspended')
        self.assertTrue(evt.summary == 'Instance instance5 suspended')

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.resume',
            'eventKey': u'd46b69a0-e9bb-4201-83e7-8c46d3172fe9',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-05T19:50:11.000000',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-1ad65fd8-2d7f-477f-96e3-682ef8779064',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'active',
            u'trait_state_description': u'',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)
        self.assertTrue(instance5.serverStatus.lower() == 'active')
        self.assertTrue(evt.summary == 'Instance instance5 resumed')

    def test_instance_delete(self):
        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.delete.start',
            'eventKey': u'a7a5b4d3-d1d3-438c-b973-381eed5e4109',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-05T19:50:11.000000',
            u'trait_memory_mb': 512,
            u'trait_priority': u'INFO',
            u'trait_request_id': u'req-a894fc28-9bb5-413f-9b96-2b61ac8b559b',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'active',
            u'trait_state_description': u'deleting',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.shutdown.start',
            'eventKey': u'6b6f59e1-7420-4472-b1ac-32b0455e0d73',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-05T19:50:11.000000',
            u'trait_memory_mb': 512,
            u'trait_priority': u'INFO',
            u'trait_request_id': u'req-a894fc28-9bb5-413f-9b96-2b61ac8b559b',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'active',
            u'trait_state_description': u'deleting',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.shutdown.end',
            'eventKey': u'c822e4dd-3071-4bc0-b67a-386757475163',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-05T19:50:11.000000',
            u'trait_memory_mb': 512,
            u'trait_priority': u'INFO',
            u'trait_request_id': u'req-a894fc28-9bb5-413f-9b96-2b61ac8b559b',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'active',
            u'trait_state_description': u'deleting',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.delete.end',
            'eventKey': u'dc5e13b1-ff07-4db9-9100-4aaf29b5aaa5',
            'severity': 2,
            'summary': '',
            u'trait_deleted_at': u'2014-09-05T21:32:34.249362',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-05T19:50:11.000000',
            u'trait_memory_mb': 512,
            u'trait_priority': u'INFO',
            u'trait_request_id': u'req-a894fc28-9bb5-413f-9b96-2b61ac8b559b',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'deleted',
            u'trait_state_description': u'',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)

        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNone(instance5)

    def test_instance_rescue_unrescue(self):
        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.rescue.start',
            'eventKey': u'5c84b158-6539-4025-9ca2-f7a9b2f68ed5',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_fixed_ips': u"[{u'floating_ips': [], u'label': u'public', u'version': 4, u'meta': {}, u'address': u'172.24.4.228', u'type': u'fixed'}]",
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-06T01:41:28.000000',
            u'trait_memory_mb': 512,
            u'trait_priority': u'INFO',
            u'trait_request_id': u'req-67f60df2-a0d1-41c3-b265-1c268c3f646c',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'active',
            u'trait_state_description': u'',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.exists',
            'eventKey': u'89e3ee5d-eaca-4fa8-97df-090047dcd98a',
            'severity': 2,
            'summary': '',
            u'trait_audit_period_beginning': u'2014-09-01T00:00:00.000000',
            u'trait_audit_period_ending': u'2014-09-06T01:42:08.918917',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-06T01:41:28.000000',
            u'trait_memory_mb': 512,
            u'trait_priority': u'INFO',
            u'trait_request_id': u'req-67f60df2-a0d1-41c3-b265-1c268c3f646c',
            u'trait_root_gb': 1,
            u'trait_service': u'conductor',
            u'trait_state': u'active',
            u'trait_state_description': u'',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.rescue.end',
            'eventKey': u'621d4147-45f7-482c-9c67-4a2fb5d77449',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_fixed_ips': u"[{u'floating_ips': [], u'label': u'public', u'version': 4, u'meta': {}, u'address': u'172.24.4.228', u'type': u'fixed'}]",
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-06T01:42:09.126933',
            u'trait_memory_mb': 512,
            u'trait_priority': u'INFO',
            u'trait_request_id': u'req-67f60df2-a0d1-41c3-b265-1c268c3f646c',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'rescued',
            u'trait_state_description': u'',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})
        self.process_event(evt)
        self.assertTrue(instance5.serverStatus.lower() == 'rescued')
        self.assertTrue(evt.summary == 'Instance instance5 placed in rescue mode')

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.unrescue.start',
            'eventKey': u'bc85c40c-ea3c-4c8b-b37c-7086a6b55bbb',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_fixed_ips': u"[{u'floating_ips': [], u'label': u'public', u'version': 4, u'meta': {}, u'address': u'172.24.4.228', u'type': u'fixed'}]",
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-06T01:42:09.000000',
            u'trait_memory_mb': 512,
            u'trait_priority': u'INFO',
            u'trait_request_id': u'req-89c9b727-8ec5-4b30-8b78-93068c2e7032',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'rescued',
            u'trait_state_description': u'',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|compute.instance.unrescue.end',
            'eventKey': u'f27cd55d-8f19-4630-922c-682a772b63a2',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_fixed_ips': u"[{u'floating_ips': [], u'label': u'public', u'version': 4, u'meta': {}, u'address': u'172.24.4.228', u'type': u'fixed'}]",
            u'trait_flavor_name': u'flavor1',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-06T01:42:09.000000',
            u'trait_memory_mb': 512,
            u'trait_priority': u'INFO',
            u'trait_request_id': u'req-89c9b727-8ec5-4b30-8b78-93068c2e7032',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'active',
            u'trait_state_description': u'',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'user1',
            u'trait_vcpus': 1})

        self.process_event(evt)
        self.assertTrue(instance5.serverStatus.lower() == 'active')
        self.assertTrue(evt.summary == 'Instance instance5 removed from rescue mode')

    def _create_network(self, network_id):
        ''' Build network using events and network_id'''

        log.info("Create network '%s'" % network_id)
        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|network.create.end',
            'eventKey': u'7ccdf8c7-9d7d-4b0e-bc10-65aafa37f52c',
            'severity': 2,
            'summary': '',
            'trait_admin_state_up': True,
            'trait_id': network_id,
            'trait_name': network_id,
            'trait_router:external': False,
            'trait_status': 'ACTIVE',
            'trait_tenant_id': 'tenant1',
        })

        self.process_event(evt)
        network = self.getObjByPath('components/network-' + network_id)
        return network

    def _delete_network(self, network_id):
        ''' Delete network using events and network_id'''
        log.info("Delete network '%s'" % network_id)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|network.delete.end',
            'eventKey': u'7dcdf8c7-9d7d-4b0e-bc10-65aafa37f52c',
            'severity': 2,
            'summary': '',
            'trait_id': network_id,
        })

        self.process_event(evt)
        network = self.getObjByPath('components/network-' + network_id)
        return network

    def _create_subnet(self, network_id, subnet_id):
        ''' Build subnet_id using events and network_id.
            The network/network_id must already exist.
        '''
        log.info("Create Subnet '%s'" % subnet_id)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|subnet.create.end',
            'eventKey': u'8ccdf8c7-9d7d-4b0e-bc10-65aafa37f52c',
            'severity': 2,
            'summary': '',
            'trait_cidr': '10.10.10.0/24',
            'trait_dns_nameserver': ['10.6.1.10','10.6.1.11'],
            'trait_gateway_ip': '10.10.10.1',
            'trait_id': subnet_id,
            'trait_name': subnet_id,
            'trait_network_id': network_id,
            'trait_tenant_id': 'tenant1',
        })

        self.process_event(evt)
        subnet = self.getObjByPath('components/subnet-' + subnet_id)
        return subnet

    def _delete_subnet(self, subnet_id):
        ''' Delete subnet using events and subnet_id'''
        log.info("Delete Subnet '%s'" % subnet_id)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|subnet.delete.end',
            'eventKey': u'8dcdf8c7-9d7d-4b0e-bc10-65aafa37f52c',
            'severity': 2,
            'summary': '',
            'trait_id': subnet_id,
        })

        self.process_event(evt)
        subnet = self.getObjByPath('components/subnet-' + subnet_id)
        return subnet

    def _create_port(self, network_id, port_id):
        ''' Build port_id using events and network_id.
            The network/network_id must already exist.
        '''
        log.info("Create port '%s'" % port_id)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|port.create.end',
            'eventKey': u'9ccdf8c7-9d7d-4b0e-bc10-65aafa37f52c',
            'severity': 2,
            'summary': '',
            'trait_admin_state_up': True,
            'trait_binding:vif_type': 'ovs',
            'trait_device_owner': 'zenoss',
            'trait_id': port_id,
            'trait_mac_address': 'fa:16:3e:23:bd:ce',
            'trait_name': port_id,
            'trait_network_id': network_id,
            'trait_status': 'ACTIVE',
            'trait_tenant_id': 'tenant1',
        })

        self.process_event(evt)
        port = self.getObjByPath('components/port-' + port_id)
        return port

    def _delete_port(self, port_id):
        ''' Delete port using events and port_id'''
        log.info("Delete port '%s'" % port_id)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|port.delete.end',
            'eventKey': u'9dcdf8c7-9d7d-4b0e-bc10-65aafa37f52c',
            'severity': 2,
            'summary': '',
            'trait_id': port_id,
        })

        self.process_event(evt)
        port = self.getObjByPath('components/port-' + port_id)
        return port

    def _create_router(self, network_id, subnet_id, router_id):
        ''' Build router_id using events, network_id, subnet_id.
            The network_id, subnet_id must already exist.
        '''
        log.info("Create router '%s'" % router_id)

        gateway_info = "{u'network_id': u'%s', u'enable_snat': True, " \
               "u'external_fixed_ips': [{u'subnet_id':  u'%s', " \
               "u'ip_address': u'192.168.117.226'}]}" \
               % (network_id, subnet_id)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|router.create.end',
            'eventKey': u'9ccdf8c7-9d7d-4b0e-bc10-65aafa37f52c',
            'severity': 2,
            'summary': '',
            'trait_admin_state_up': True,
            'trait_id': router_id,
            'trait_external_gateway': gateway_info,
            'trait_name': router_id,
            'trait_network_id': network_id,
            'trait_routes': [],
            'trait_status': 'ACTIVE',
            'trait_tenant_id': 'tenant1',
        })

        self.process_event(evt)
        router = self.getObjByPath('components/router-' + router_id)
        return router

    def _delete_router(self, router_id):
        ''' Delete router using events and router_id'''
        log.info("Delete router '%s'" % router_id)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|router.delete.end',
            'eventKey': u'9dddf8c7-9d7d-4b0e-bc10-65aafa37f52c',
            'severity': 2,
            'summary': '',
            'trait_id': router_id,
        })

        self.process_event(evt)
        router = self.getObjByPath('components/router-' + router_id)
        return router

    def _create_floatingip(self, network_id, router_id, port_id, floatingip_id):
        ''' Build floatingip_id using events, network_id, subnet_id.
            The network_id, subnet_id must already exist.
        '''
        log.info("Create floatingip '%s'" % floatingip_id)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|floatingip.create.end',
            'eventKey': u'01cdf8c7-9d7d-4b0e-bc10-65aafa37f52c',
            'severity': 2,
            'summary': '',
            'trait_fixed_ip_address': '10.1.7.100',
            'trait_floating_ip_address': '10.31.7.3',
            'trait_floating_network_id': network_id,
            'trait_id': floatingip_id,
            'trait_port_id': port_id,
            'trait_router_id': router_id,
            'trait_status': 'ACTIVE',
            'trait_tenant_id': 'tenant1',
        })

        self.process_event(evt)
        floatingip = self.getObjByPath('components/floatingip-' + floatingip_id)
        return floatingip

    def _delete_floatingip(self, floatingip_id):
        ''' Delete floatingip using events and floatingip_id'''
        log.info("Delete floatingip '%s'" % floatingip_id)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|floatingip.delete.end',
            'eventKey': u'0dddf8c7-9d7d-4b0e-bc10-65aafa37f52c',
            'severity': 2,
            'summary': '',
            'trait_id': floatingip_id,
        })

        self.process_event(evt)
        floatingip = self.getObjByPath('components/floatingip-' + floatingip_id)
        return floatingip

    def _create_securitygroup(self, securitygroup_id):
        ''' Build securitygroup_id using events.
        '''
        log.info("Create securityGroup '%s'" % securitygroup_id)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|security_group.create.end',
            'eventKey': u'bccdf8c7-9d7d-4b0e-bc10-65aafa37f52c',
            'severity': 2,
            'summary': '',
            'trait_id': securitygroup_id,
            'trait_name': securitygroup_id,
            'trait_tenant_id': 'tenant1',
        })

        self.process_event(evt)
        securitygroup = self.getObjByPath('components/securitygroup-' + securitygroup_id)
        return securitygroup

    def _delete_securitygroup(self, securitygroup_id):
        ''' Delete securitygroup using events and securitygroup_id'''
        log.info("Delete securityGroup '%s'" % securitygroup_id)

        evt = buildEventFromDict({
            'device': 'endpoint',
            'eventClassKey': u'openstack|security_group.delete.end',
            'eventKey': u'0dddf8c7-9d7d-4b0e-bc10-65aafa37f52c',
            'severity': 2,
            'summary': '',
            'trait_id': securitygroup_id,
        })

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
        ''' Test Creation/Deletion of port '''
        net = self._create_network("test")
        self.assertIsNotNone(net, msg="CreatePort: network doesn't exist!")

        port = self._create_port(net.netId, 'test')
        self.assertIsNotNone(port, msg="CreatePort: port doesn't exist!")

        port = self._delete_port(port.portId)
        self.assertIsNone(port, msg="Failure: port exists!")

    def test_router_and_floatingip(self):
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

    # def test_security_group(self):
    #     ''' Test Creation/Deletion of SecurityGroup '''

    #     securitygroup = self._create_securitygroup('test')
    #     self.assertIsNotNone(securitygroup, msg="SG: securitygroup doesn't exist!")

    #     securitygroup = self._delete_securitygroup(securitygroup.sgId)
    #     self.assertIsNone(securitygroup, msg="Failure: securitygroup exists!")

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
