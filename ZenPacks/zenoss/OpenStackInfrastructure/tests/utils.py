##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2018, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
LOG = logging.getLogger('zen.OpenStack')

import Globals

import functools
import importlib
import re
import unittest
import zope.component
from zope.event import notify
from zope.traversing.adapters import DefaultTraversable

from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.Five import zcml
from Products.ZenModel.ManagedEntity import ManagedEntity
from Products.ZenRelations.RelationshipBase import RelationshipBase
from Products.ZenRelations.ToManyContRelationship import ToManyContRelationship
from Products.ZenTestCase.BaseTestCase import ZenossTestCaseLayer
from Products.ZenUtils.IpUtil import ipToDecimal, decimalIpToStr
from Products.ZenUtils.Utils import unused
from Products.Zuul.catalog.events import IndexingEvent

from ZenPacks.zenoss.ZenPackLib import zenpacklib
# Required before zenpacklib.TestCase can be used.
zenpacklib.enableTesting()

unused(Globals)


def require_zenpack(zenpack_name, default=None):
    '''
    Decorator with mandatory zenpack_name argument.

    If zenpack_name can't be imported, the decorated function or method
    will return default. Otherwise it will execute and return as
    written.

    Usage looks like the following:

        @require_zenpack('ZenPacks.zenoss.Impact')
        @require_zenpack('ZenPacks.zenoss.vCloud')
        def dothatthingyoudo(args):
            return "OK"

        @require_zenpack('ZenPacks.zenoss.Impact', [])
        def returnalistofthings(args):
            return [1, 2, 3]
    '''
    def wrap(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                importlib.import_module(zenpack_name)
            except ImportError:
                return

            return f(*args, **kwargs)

        return wrapper

    return wrap


def setup_crochet():
    """Setup and return crochet for testing Twisted code."""
    try:
        import crochet
    except ImportError as e:
        print "\n\nERROR: Unable to import crochet: {}".format(e)
        print "  You must install it: pip install --no-deps crochet\n"
        raise

    crochet.setup()
    return crochet


class FilteredLog(logging.Filter):
    # Context manager that filters/ignores log messages that contain a substring.

    def __init__(self, loggers, filter_msgs):
        super(FilteredLog, self).__init__()
        self.loggers = loggers
        self.filter_msgs = filter_msgs

    def __enter__(self):
        for logger in self.loggers:
            logging.getLogger(logger).addFilter(self)

    def __exit__(self, type, value, traceback):
        for logger in self.loggers:
            logging.getLogger(logger).removeFilter(self)

    def filter(self, record):
        for msg in self.filter_msgs:
            if msg in record.getMessage():
                return False
        return True


# When a manually-created python object is first added to its container, we
# need to reload it, as its in-memory representation is changed.
def addContained(object, relname, target):
    # print "addContained(" + str(object) + "." + relname + " => " + str(target) + ")"
    rel = getattr(object, relname)

    # contained via a relationship
    if isinstance(rel, ToManyContRelationship):
        rel._setObject(target.id, target)
        return rel._getOb(target.id)

    elif isinstance(rel, RelationshipBase):
        rel.addRelation(target)
        return rel._getOb(target.id)

    # contained via a property
    else:
        # note: in this scenario, you must have the target object's ID the same
        #       as the relationship from the parent object.

        assert(relname == target.id)
        object._setObject(target.id, target)
        return getattr(object, relname)


def addNonContained(object, relname, target):
    rel = getattr(object, relname)
    rel.addRelation(target)
    return target


def create_model_data(dmd):
    '''
    Return an Endpoint suitable for Impact functional testing.
    '''
    # DeviceClass
    dc = dmd.Devices.createOrganizer('/OpenStack/Infrastructure')
    dc.setZenProperty('zPythonClass', 'ZenPacks.zenoss.OpenStackInfrastructure.Endpoint')

    # OSProcessClasses
    osc = dmd.Processes.createOrganizer('/OpenStack')
    for binary in ['nova-cert', 'nova-conductor', 'nova-consoleauth', 'nova-scheduler', 'nova-compute', 'nova-api']:
        osc.manage_addOSProcessClass(binary)

    # Endpoint
    endpoint = dc.createInstance('endpoint')

    # API Endpoint for keystone
    from ZenPacks.zenoss.OpenStackInfrastructure.ApiEndpoint import ApiEndpoint
    keystone_apiendpoint = addContained(endpoint, "components", ApiEndpoint("apiendpoint-zOpenStackAuthUrl"))
    keystone_apiendpoint.url = 'http://127.0.0.1:5000/v2.0'
    keystone_apiendpoint.title = keystone_apiendpoint.url

    # non-public api endpoint for load balanced keystone
    keystone_apiendpoint2 = addContained(endpoint, "components", ApiEndpoint("apiendpoint-a8450514a5ca012fab799579ae4d7eec"))
    keystone_apiendpoint2.url = 'http://127.0.0.1:1234/v2.0'
    keystone_apiendpoint2.title = keystone_apiendpoint2.url

    # Org Structure
    from ZenPacks.zenoss.OpenStackInfrastructure.Region import Region
    from ZenPacks.zenoss.OpenStackInfrastructure.AvailabilityZone import AvailabilityZone
    region = addContained(endpoint, "components", Region("region"))
    zone1 = addContained(endpoint, "components", AvailabilityZone("zone1"))
    zone2 = addContained(endpoint, "components", AvailabilityZone("zone2"))
    addNonContained(region, "childOrgs", zone1)
    addNonContained(region, "childOrgs", zone2)

    # Tenants
    from ZenPacks.zenoss.OpenStackInfrastructure.Tenant import Tenant
    tenant1 = addContained(endpoint, "components", Tenant("tenant-tenant1"))
    tenant2 = addContained(endpoint, "components", Tenant("tenant-tenant2"))

    # Flavor
    from ZenPacks.zenoss.OpenStackInfrastructure.Flavor import Flavor
    flavor1 = addContained(endpoint, "components", Flavor("flavor1"))

    # Image
    from ZenPacks.zenoss.OpenStackInfrastructure.Image import Image
    image1 = addContained(endpoint, "components", Image("image1"))

    # Host
    from ZenPacks.zenoss.OpenStackInfrastructure.Host import Host
    computehost1 = addContained(endpoint, "components", Host("computehost1"))
    addNonContained(computehost1, "orgComponent", zone1)
    computehost2 = addContained(endpoint, "components", Host("computehost2"))
    addNonContained(computehost2, "orgComponent", zone2)
    controllerhost = addContained(endpoint, "components", Host("controllerhost"))
    addNonContained(controllerhost, "orgComponent", zone1)

    # SoftwareComponents
    from ZenPacks.zenoss.OpenStackInfrastructure.NovaService import NovaService
    from ZenPacks.zenoss.OpenStackInfrastructure.NovaApi import NovaApi
    nova_consoleauth = addContained(endpoint, "components", NovaService("nova-consoleauth"))
    nova_consoleauth.binary = 'nova-consoleauth'
    addNonContained(nova_consoleauth, "hostedOn", controllerhost)
    addNonContained(nova_consoleauth, "orgComponent", zone1)
    nova_scheduler = addContained(endpoint, "components", NovaService("nova-scheduler"))
    nova_scheduler.binary = 'nova-scheduler'
    addNonContained(nova_scheduler, "hostedOn", controllerhost)
    addNonContained(nova_scheduler, "orgComponent", zone1)
    nova_conductor1 = addContained(endpoint, "components", NovaService("nova-conductor1"))
    nova_conductor1.binary = 'nova-conductor'
    nova_conductor2 = addContained(endpoint, "components", NovaService("nova-conductor2"))
    nova_conductor2.binary = 'nova-conductor'
    addNonContained(nova_conductor1, "hostedOn", computehost1)
    addNonContained(nova_conductor1, "orgComponent", zone1)
    addNonContained(nova_conductor2, "hostedOn", computehost2)
    addNonContained(nova_conductor2, "orgComponent", zone2)
    nova_compute1 = addContained(endpoint, "components", NovaService("nova-compute1"))
    nova_compute1.binary = 'nova-compute'
    nova_compute2 = addContained(endpoint, "components", NovaService("nova-compute2"))
    nova_compute2.binary = 'nova-compute'
    addNonContained(nova_compute1, "hostedOn", computehost1)
    addNonContained(nova_compute1, "orgComponent", zone1)
    addNonContained(nova_compute2, "hostedOn", computehost2)
    addNonContained(nova_compute2, "orgComponent", zone2)
    nova_cert = addContained(endpoint, "components", NovaService("nova-cert"))
    nova_cert.binary = 'nova-cert'
    addNonContained(nova_cert, "hostedOn", controllerhost)
    addNonContained(nova_cert, "orgComponent", zone1)
    nova_api = addContained(endpoint, "components", NovaApi("nova-api"))
    nova_api.binary = 'nova-api'
    addNonContained(nova_api, "hostedOn", controllerhost)
    addNonContained(nova_api, "orgComponent", region)

    # Hypervisor
    from ZenPacks.zenoss.OpenStackInfrastructure.Hypervisor import Hypervisor
    hypervisor1 = addContained(endpoint, "components", Hypervisor("hypervisor1"))
    hypervisor2 = addContained(endpoint, "components", Hypervisor("hypervisor2"))
    addNonContained(hypervisor1, "host", computehost1)
    addNonContained(hypervisor2, "host", computehost2)

    # Instance
    from ZenPacks.zenoss.OpenStackInfrastructure.Instance import Instance
    instance1 = addContained(endpoint, "components", Instance("instance1"))
    instance2 = addContained(endpoint, "components", Instance("instance2"))
    instance3 = addContained(endpoint, "components", Instance("instance3"))
    instance4 = addContained(endpoint, "components", Instance("instance4"))
    addNonContained(instance1, "flavor", flavor1)
    addNonContained(instance2, "flavor", flavor1)
    addNonContained(instance3, "flavor", flavor1)
    addNonContained(instance4, "flavor", flavor1)
    addNonContained(instance1, "image", image1)
    addNonContained(instance2, "image", image1)
    addNonContained(instance3, "image", image1)
    addNonContained(instance4, "image", image1)
    addNonContained(instance1, "hypervisor", hypervisor1)
    addNonContained(instance2, "hypervisor", hypervisor1)
    addNonContained(instance3, "hypervisor", hypervisor2)
    addNonContained(instance4, "hypervisor", hypervisor2)
    addNonContained(instance1, "tenant", tenant1)
    addNonContained(instance2, "tenant", tenant2)
    addNonContained(instance3, "tenant", tenant1)
    addNonContained(instance4, "tenant", tenant2)

    # Vnic
    from ZenPacks.zenoss.OpenStackInfrastructure.Vnic import Vnic
    instance1vnic1 = addContained(instance1, "vnics", Vnic("instance1_vnic1"))
    instance1vnic1.macaddress = 'de:ad:be:ef:01:01'
    instance1vnic1.index_object()
    instance1vnic2 = addContained(instance1, "vnics", Vnic("instance1_vnic2"))
    instance1vnic2.macaddress = 'de:ad:be:ef:01:02'
    instance1vnic2.index_object()
    instance2vnic1 = addContained(instance2, "vnics", Vnic("instance2_vnic1"))
    instance2vnic1.macaddress = 'de:ad:be:ef:02:01'
    instance2vnic1.index_object()
    instance2vnic2 = addContained(instance2, "vnics", Vnic("instance2_vnic2"))
    instance2vnic2.macaddress = 'de:ad:be:ef:02:02'
    instance2vnic2.index_object()
    instance3vnic1 = addContained(instance3, "vnics", Vnic("instance3_vnic1"))
    instance3vnic1.macaddress = 'de:ad:be:ef:03:01'
    instance3vnic1.index_object()
    instance3vnic2 = addContained(instance3, "vnics", Vnic("instance3_vnic2"))
    instance3vnic2.macaddress = 'de:ad:be:ef:03:02'
    instance3vnic2.index_object()
    instance4vnic1 = addContained(instance4, "vnics", Vnic("instance4_vnic1"))
    instance4vnic1.macaddress = 'de:ad:be:ef:04:01'
    instance4vnic1.index_object()
    instance4vnic2 = addContained(instance4, "vnics", Vnic("instance4_vnic2"))
    instance4vnic2.macaddress = 'de:ad:be:ef:04:02'
    instance4vnic2.index_object()

    # Linux guest devices (Virtual)
    # make sure that the interfaces line up.
    guest_dc = dmd.Devices.createOrganizer('/Server/SSH/Linux')
    guest_dc.setZenProperty('zPythonClass', 'Products.ZenModel.Device')
    guest_instance1 = guest_dc.createInstance("g-instance1")
    guest_instance2 = guest_dc.createInstance("g-instance2")
    guest_instance3 = guest_dc.createInstance("g-instance3")
    # instance4 is not monitored by zenoss.

    from Products.ZenModel.IpInterface import IpInterface

    def add_linux_interface_mac(device, interface_name, macaddress):
        eth_if = IpInterface(interface_name)
        device.os.interfaces._setObject(eth_if.id, eth_if)
        eth_if = device.os.interfaces._getOb(eth_if.id)
        eth_if.macaddress = macaddress
        eth_if.index_object()
        device.index_object()

    add_linux_interface_mac(guest_instance1, 'eth0', 'de:ad:be:ef:01:01')
    add_linux_interface_mac(guest_instance1, 'eth1', 'de:ad:be:ef:01:02')
    add_linux_interface_mac(guest_instance2, 'eth0', 'de:ad:be:ef:02:01')
    add_linux_interface_mac(guest_instance2, 'eth1', 'de:ad:be:ef:02:02')
    add_linux_interface_mac(guest_instance3, 'eth0', 'de:ad:be:ef:03:01')
    add_linux_interface_mac(guest_instance3, 'eth1', 'de:ad:be:ef:03:02')

    # Linux devices (Physical)
    # (link to host1 and host2)
    phys_dc = dmd.Devices.createOrganizer('/Server/SSH/Linux/NovaHost')
    phys_dc.setZenProperty('zPythonClass', 'Products.ZenModel.Device')
    phys_computehost1 = phys_dc.createInstance("p-computehost1")
    phys_computehost2 = phys_dc.createInstance("p-computehost2")
    phys_controllerhost = phys_dc.createInstance("p-controllerhost")

    # Link the host components to the physical hosts.
    computehost1.claim_proxy_device(phys_computehost1)
    computehost2.claim_proxy_device(phys_computehost2)
    controllerhost.claim_proxy_device(phys_controllerhost)

    # Add OSprocesses for each of the software components.
    from ZenPacks.zenoss.OpenStackInfrastructure.SoftwareComponent import SoftwareComponent
    from Products.ZenModel.OSProcess import OSProcess
    for component in endpoint.components():
        if isinstance(component, SoftwareComponent):
            binary = component.binary
            linux_device = component.hostedOn().ensure_proxy_device()

            process_id = '%s_%s' % (linux_device.id, binary)
            process = OSProcess(process_id)
            linux_device.os.processes._setObject(process_id, process)
            process = linux_device.os.processes._getOb(process_id)

            process_class = re.sub(r'\d+$', '', binary)
            process.setOSProcessClass("Processes/OpenStack/osProcessClasses/%s" % process_class)

    # Cinder
    from ZenPacks.zenoss.OpenStackInfrastructure.Volume import Volume
    from ZenPacks.zenoss.OpenStackInfrastructure.VolSnapshot import VolSnapshot
    volume1 = addContained(endpoint, "components", Volume("volume1"))
    volsnap1 = addContained(endpoint, "components", VolSnapshot("volsnap1"))
    addNonContained(instance1, "volumes", volume1)
    addNonContained(volume1, "volSnapshots", volsnap1)

    return {
        'endpoint': endpoint,
        'phys_dc': phys_dc,
        'guest_dc': guest_dc
    }


def is_iterable(obj):
    """
    Returns true of the supplied object is iterable, but not a string.
    """

    if isinstance(obj, basestring):
        return False
    try:
        iter(obj)
        return True
    except TypeError:
        return False


def all_objmaps(iterable):
    """
    Loop through an iterable (list, etc) and through any nested iterables,
    finding all objmaps and yielding them.  This includes objmaps nested in
    relationshipmaps and/or other objmaps, lists of lists, etc.
    """
    for item in iterable:
        if isinstance(item, ObjectMap):
            yield item

            # look for any attribute values in the objmap that contain
            # nested objmaps.
            for k, v in item.items():
                if is_iterable(v):
                    for r_item in all_objmaps(v):
                        yield r_item

        elif is_iterable(item):
            for r_item in all_objmaps(item):
                yield r_item


current_ip_address = [ipToDecimal("10.0.0.12")]


def next_ip_address():
    current_ip_address[0] += 1
    return decimalIpToStr(current_ip_address[0])


def component_to_tests(component, one_sided=True):
    device_path = '/'.join(component.device().getPrimaryPath())
    component_path = '/'.join(component.getPrimaryPath())
    component_path = re.sub('^' + device_path + '/', '', component_path)

    me = ManagedEntity('')
    propnames = sorted(set(component.propertyIds()) -
                       set(me.propertyIds()))
    relnames = sorted(set(component.getRelationshipNames()) -
                      set(me.getRelationshipNames()) -
                      set(('depedencies', 'dependents', 'maintenanceWindows')))

    if one_sided:
        # remove relationships that are not alphabetically the first
        # one between themselves and the remote end of of the relationship.
        # This assumes that we'll be building tests for the other side of the
        # relationship and avoids duplicate tests.
        new_relnames = []
        for relname in relnames:
            rel = component._getOb(relname)
            if rel.id < rel.remoteName():
                new_relnames.append(relname)
        relnames = new_relnames

    out = []
    out.append("        component = self.device.getObjByPath(%r)" % component_path)
    for propname in ['title'] + propnames:
        out.append("        self.assertEquals(component.%s, %r)" % (propname, getattr(component, propname)))

    for relname in relnames:
        rel = getattr(component, relname)
        objs = rel()
        if objs is None:
            out.append("        self.assertIsNone(component.%s())" % relname)
        elif isinstance(objs, list):
            out.append("        self.assertIsNotNone(component.%s())" % relname)
            objids = sorted([x.id for x in objs])
            out.append("        self.assertEquals(sorted([x.id for x in component.%s()]), %r)" % (relname, objids))
        else:
            out.append("        self.assertIsNotNone(component.%s())" % relname)
            out.append("        self.assertEquals(component.%s().id, %r)" % (relname, objs.id))

    return "\n".join(out)


def device_to_tests(device):
    tests = {}
    out = []

    for component in device.getDeviceComponents():
        component_type = component.__class__.__name__
        tests.setdefault(component_type, [])
        tests[component_type].append(component_to_tests(component))

    for component_type in sorted(tests.keys()):
        out.append("")
        out.append("    def test_%s(self):" % component_type)
        for test in tests[component_type]:
            out.append(test)
            out.append("")

    return "\n".join(out)


class SharedModelTestLayer(ZenossTestCaseLayer):
    tc = None
    device = None

    # Note: This will only get run *once* across all layers.  If you want something to
    # be invoked for each layer, put it in ModelTestCaseLayer.setUp() instead.
    @classmethod
    def setUp(cls):
        zope.component.testing.setUp(cls)
        zope.component.provideAdapter(DefaultTraversable, (None,))
        import Products.ZenTestCase
        zcml.load_config('testing-noevent.zcml', Products.ZenTestCase)
        import Products.ZenTestCase
        zcml.load_config('testing-noevent.zcml', Products.ZenTestCase)
        import ZenPacks.zenoss.OpenStackInfrastructure
        zcml.load_config('configure.zcml', ZenPacks.zenoss.OpenStackInfrastructure)

        # Silly trickery here.
        # We create a single TestCase, and share the environment that it creates
        # across all our ModelTestCases (which we have inheriting from unittest.TestCase
        # instead)
        class DummyTestCase(zenpacklib.TestCase):
            disableLogging = False
            maxDiff = None
            zenpack_module_name = 'ZenPacks.zenoss.OpenStackInfrastructure'

            def test_donothing(self):
                pass
        cls.tc = DummyTestCase("test_donothing")
        cls.tc.setUp()
        cls.tc.afterSetUp()
        cls.tc.dmd.REQUEST = None

        # Workaround for IMP-389:
        # When Impact 5.2.1-5.2.3 (at least) are installed, setProdState
        # is patched to re-index the object in the global catalog specifically
        # on the productionState column, but at least on older verions of RM,
        # the sandboxed version of global_catalog does not index that column,
        # which causes setProdState to fail.  Add the index for now, to
        # work around this.
        if (hasattr(cls.tc.dmd.global_catalog, 'indexes') and
                'productionState' not in cls.tc.dmd.global_catalog.indexes()):
            from Products.ZenUtils.Search import makeCaseSensitiveFieldIndex
            cls.tc.dmd.global_catalog.addIndex('productionState', makeCaseSensitiveFieldIndex('productionState'))
            cls.tc.dmd.global_catalog.addColumn('productionState')

        dc = cls.tc.dmd.Devices.createOrganizer('/Devices/OpenStack/Infrastructure')

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

        # Create catalog
        try:
            from Products.ZenTestCase.BaseTestCase import init_model_catalog_for_tests
            init_model_catalog_for_tests()
        except ImportError:
            pass

    @classmethod
    def tearDown(cls):
        if cls.device:
            cls.device.deleteDevice()

    @classmethod
    def createDevice(cls, devname):
        # Due to ZEN-29804 we cannot rely on `findDevice()` results as it
        # uses catalog, which can be purged between tests.
        device = cls.device or cls.tc.dmd.Devices.findDevice(devname)
        if device:
            device.deleteDevice()

        dc = cls.tc.dmd.Devices.createOrganizer('/Devices/OpenStack/Infrastructure')
        cls.device = dc.createInstance(devname)
        cls.device.setPerformanceMonitor('localhost')
        cls.device.index_object()
        notify(IndexingEvent(cls.device))

        # ZEN-31147 workaround:
        from Products.Zuul.catalog.global_catalog import IIndexableWrapper
        from zope.component.interfaces import ComponentLookupError
        try:
            IIndexableWrapper(cls.device).searchIcon()
        except ComponentLookupError:
            import Products.ZenUtils.virtual_root
            Products.ZenUtils.virtual_root.register_cse_virtual_root()


class SharedModelTestCase(unittest.TestCase):
    layer = None
    device = None

    def createDevice(self, devname):
        self.layer.createDevice(devname)
        self.device = self.layer.device
        return self.device

    def setUp(self):
        super(SharedModelTestCase, self).setUp()

        import ZenPacks.zenoss.OpenStackInfrastructure
        zcml.load_config('configure.zcml', ZenPacks.zenoss.OpenStackInfrastructure)

        # Pull down the shared environment from the layer
        self.dmd = self.layer.tc.dmd
        self.device = self.layer.device
