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


from zExceptions import NotFound
from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.DataCollector.ApplyDataMap import ApplyDataMap
from Products.ZenEvents.Event import buildEventFromDict
from Products.ZenUtils.Utils import monkeypatch

from ZenPacks.zenoss.OpenStack.tests.test_utils import create_model_data

from Products.ZenUtils.Utils import unused
unused(Globals)

from ZenPacks.zenoss.OpenStack.events import process as process_event
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

class TestEventTransforms(zenpacklib.TestCase):
    
    disableLogging = False

    def afterSetUp(self):
        # needed if this is run directly on the commandline,
        # since otherwise it will be __main__, and ZPL's afterSetup
        # will get confused.
        self.__module__ = 'ZenPacks.zenoss.OpenStack.tests.test_impact'        
        super(TestEventTransforms, self).afterSetUp()


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

    def getObjByPath(self, path):
        try:
            return self.endpoint().getObjByPath(path)
        except NotFound:
            return None

    def process_event(self, evt):
        changes = process_event(evt, self.endpoint(), self.dmd, None)
        log.info("Processed event (eventClassKey=%s, summary=%s, %d objmaps)" %
                 (evt.eventClassKey, evt.summary, changes))

    def test_vm_creation(self):
        evt = buildEventFromDict({
            'device': 'packstack',
            'eventClassKey': u'scheduler.run_instance.end',
            'eventKey': u'07180940-d533-43ee-b5a7-930108e6238f',
            'severity': 2,
            'summary': '',
            u'trait_request_id': u'req-28e885ca-6d7d-4e5d-8182-830edd2eb2b3',
            u'trait_service': u'scheduler.computehost1',
            u'trait_tenant_id': u'tenant1'
        })
        self.process_event(evt)

        evt = buildEventFromDict({
            'device': 'packstack',
            'eventClassKey': u'compute.instance.create.start',
            'eventKey': u'bc58885b-7677-4a10-9f4a-133a696dc6ab',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance4',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'm1.tiny',
            u'trait_host_name': u'computehost1',
            u'trait_image_name': u'cirros',
            u'trait_instance_id': u'instance5',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-28e885ca-6d7d-4e5d-8182-830edd2eb2b3',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'building',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'08beb1b8cb43459bac38c048c8ebc967',
            u'trait_vcpus': 1
        })
        self.process_event(evt)

        instance5 = self.getObjByPath('components/server-instance5')

        self.assertIsNotNone(instance5, msg="Incremental model created instance 'instance5'")

        evt = buildEventFromDict({
            'device': 'packstack',
            'eventClassKey': u'compute.instance.create.end',
            'eventKey': u'd207460b-2e8a-48e0-917a-cebb07b063a5',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_fixed_ips': u"[{u'floating_ips': [], u'label': u'public', u'version': 4, u'meta': {}, u'address': u'172.24.4.229', u'type': u'fixed'}]",
            u'trait_flavor_name': u'm1.tiny',
            u'trait_host_name': u'computehost1',
            u'trait_image_name': u'cirros',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-09-02T20:20:24.933700',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-28e885ca-6d7d-4e5d-8182-830edd2eb2b3',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'active',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'08beb1b8cb43459bac38c048c8ebc967',
            u'trait_vcpus': 1
        })
        self.process_event(evt)

    def _create_instance5(self):
        # Dummy up the instance (as if test_vm_creation had run, and we had instance5 in the system)
        adm = ApplyDataMap()
        adm._applyDataMap(self.endpoint(), ObjectMap(
            modname='ZenPacks.zenoss.OpenStack.Instance',
            compname='',
            data={
                'id': 'server-instance5',
                'relname': 'components',
                'resourceId': u'instance5',
                'serverId': u'instance5',
                'serverStatus': u'active',
                'set_flavor_name': u'm1.tiny',
                'set_host_name': u'computehost1',
                'set_tenant': u'tenant1',
                'title': u'instance5'
            }
        ))


    def test_vm_power_off(self):
        self._create_instance5()
        instance5 = self.getObjByPath('components/server-instance5')
        self.assertIsNotNone(instance5)

        self.assertTrue(instance5.serverStatus == 'active')        

        evt = buildEventFromDict({
            'device': 'packstack',
            'eventClassKey': u'compute.instance.power_off.start',
            'eventKey': u'e7be253c-7e5a-445a-aed7-15e09f56c7ac',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'm1.tiny',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-08-05T01:01:02.000000',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-d9b7ee3f-cc3d-4a4b-9f9d-707939a18f35',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'active',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'08beb1b8cb43459bac38c048c8ebc967',
            u'trait_vcpus': 1
        })
        self.process_event(evt)

        self.assertTrue(instance5.serverStatus == 'active')        

        evt = buildEventFromDict({
            'device': 'packstack',
            'eventClassKey': u'compute.instance.power_off.end',
            'eventKey': u'c8f2f937-0737-4f2c-b5b1-6b14b162e3e7',
            'severity': 2,
            'summary': '',
            u'trait_disk_gb': 1,
            u'trait_display_name': u'instance5',
            u'trait_ephemeral_gb': 0,
            u'trait_flavor_name': u'm1.tiny',
            u'trait_host_name': u'computehost1',
            u'trait_instance_id': u'instance5',
            u'trait_launched_at': u'2014-08-05T01:01:02.000000',
            u'trait_memory_mb': 512,
            u'trait_request_id': u'req-d9b7ee3f-cc3d-4a4b-9f9d-707939a18f35',
            u'trait_root_gb': 1,
            u'trait_service': u'compute',
            u'trait_state': u'stopped',
            u'trait_tenant_id': u'tenant1',
            u'trait_user_id': u'08beb1b8cb43459bac38c048c8ebc967',
            u'trait_vcpus': 1
        })
        self.process_event(evt)

        self.assertTrue(instance5.serverStatus == 'stopped')        


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
