##############################################################################
#
# Copyright (C) Zenoss, Inc. 2019, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap

try:
    from ZenPacks.zenoss.DynamicView.tests import DynamicViewTestCase
except ImportError:
    import unittest

    @unittest.skip("tests require DynamicView >= 1.7.0")
    class DynamicViewTestCase(unittest.TestCase):
        """TestCase stub if DynamicViewTestCase isn't available."""

from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import create_model_data

# These are the expected impact relationships.
EXPECTED_IMPACTS = """
[endpoint/apiendpoint-zOpenStackAuthUrl]->[endpoint/region]

[endpoint]->[endpoint/controllerhost]
[endpoint]->[endpoint/computehost1]
[endpoint]->[endpoint/computehost2]

[endpoint/zone1]->[endpoint/region]
[endpoint/zone2]->[endpoint/region]

[endpoint/nova-api]->[endpoint/region]
[endpoint/nova-cert]->[endpoint/zone1]
[endpoint/nova-consoleauth]->[endpoint/zone1]
[endpoint/nova-scheduler]->[endpoint/zone1]
[endpoint/nova-compute1]->[endpoint/zone1]
[endpoint/nova-compute2]->[endpoint/zone2]
[endpoint/nova-conductor1]->[endpoint/zone1]
[endpoint/nova-conductor2]->[endpoint/zone2]

[endpoint/volume1]->[endpoint/instance1]
[endpoint/volume1]->[endpoint/volsnap1]

[endpoint/controllerhost]->[endpoint/nova-api]
[endpoint/controllerhost]->[endpoint/nova-cert]
[endpoint/controllerhost]->[endpoint/nova-consoleauth]
[endpoint/controllerhost]->[endpoint/nova-scheduler]
[endpoint/controllerhost]->[endpoint/zone1]

[p-controllerhost]->[endpoint/controllerhost]
[p-controllerhost]->[p-controllerhost/p-controllerhost_nova-api]
[p-controllerhost]->[p-controllerhost/p-controllerhost_nova-cert]
[p-controllerhost]->[p-controllerhost/p-controllerhost_nova-consoleauth]
[p-controllerhost]->[p-controllerhost/p-controllerhost_nova-scheduler]
[p-controllerhost/p-controllerhost_nova-api]->[endpoint/nova-api]
[p-controllerhost/p-controllerhost_nova-cert]->[endpoint/nova-cert]
[p-controllerhost/p-controllerhost_nova-consoleauth]->[endpoint/nova-consoleauth]
[p-controllerhost/p-controllerhost_nova-scheduler]->[endpoint/nova-scheduler]

[endpoint/computehost1]->[endpoint/hypervisor1]
[endpoint/computehost1]->[endpoint/nova-compute1]
[endpoint/computehost1]->[endpoint/nova-conductor1]
[endpoint/computehost1]->[endpoint/zone1]

[p-computehost1]->[endpoint/computehost1]
[p-computehost1]->[p-computehost1/p-computehost1_nova-compute]
[p-computehost1]->[p-computehost1/p-computehost1_nova-conductor]
[p-computehost1/p-computehost1_nova-compute]->[endpoint/nova-compute1]
[p-computehost1/p-computehost1_nova-conductor]->[endpoint/nova-conductor1]

[endpoint/computehost2]->[endpoint/hypervisor2]
[endpoint/computehost2]->[endpoint/nova-compute2]
[endpoint/computehost2]->[endpoint/nova-conductor2]
[endpoint/computehost2]->[endpoint/zone2]

[p-computehost2]->[endpoint/computehost2]
[p-computehost2]->[p-computehost2/p-computehost2_nova-compute]
[p-computehost2]->[p-computehost2/p-computehost2_nova-conductor]
[p-computehost2/p-computehost2_nova-compute]->[endpoint/nova-compute2]
[p-computehost2/p-computehost2_nova-conductor]->[endpoint/nova-conductor2]

[endpoint/hypervisor1]->[endpoint/instance1]
[endpoint/hypervisor1]->[endpoint/instance2]
[endpoint/hypervisor2]->[endpoint/instance3]
[endpoint/hypervisor2]->[endpoint/instance4]

[endpoint/instance1]->[endpoint/tenant-tenant1]
[endpoint/instance1]->[g-instance1]
[endpoint/instance1_vnic1]->[endpoint/instance1]
[endpoint/instance1_vnic2]->[endpoint/instance1]

[endpoint/instance2]->[endpoint/tenant-tenant2]
[endpoint/instance2]->[g-instance2]
[endpoint/instance2_vnic1]->[endpoint/instance2]
[endpoint/instance2_vnic2]->[endpoint/instance2]

[endpoint/instance3]->[endpoint/tenant-tenant1]
[endpoint/instance3]->[g-instance3]
[endpoint/instance3_vnic1]->[endpoint/instance3]
[endpoint/instance3_vnic2]->[endpoint/instance3]

[endpoint/instance4]->[endpoint/tenant-tenant2]
[endpoint/instance4_vnic1]->[endpoint/instance4]
[endpoint/instance4_vnic2]->[endpoint/instance4]

[g-instance1]->[g-instance1/eth0]
[g-instance1]->[g-instance1/eth1]

[g-instance2]->[g-instance2/eth0]
[g-instance2]->[g-instance2/eth1]

[g-instance3]->[g-instance3/eth0]
[g-instance3]->[g-instance3/eth1]
"""


class DynamicViewTests(DynamicViewTestCase):
    """DynamicView tests."""

    # ZenPacks to initialize for testing purposes.
    zenpacks = [
        "ZenPacks.zenoss.LinuxMonitor",
        "ZenPacks.zenoss.OpenStackInfrastructure",
    ]

    # Expected impact relationships.
    expected_impacts = EXPECTED_IMPACTS

    def get_devices(self):
        """Return Dict[str, Device] of devices to be used for testing."""
        data = create_model_data(self.dmd)
        guest_devices = data["guest_dc"].devices._getOb
        phys_devices = data["phys_dc"].devices._getOb

        return {
            "endoint": data["endpoint"],
            "g-instance1": guest_devices("g-instance1"),
            "g-instance2": guest_devices("g-instance2"),
            "g-instance3": guest_devices("g-instance3"),
            "p-computehost1": phys_devices("p-computehost1"),
            "p-computehost2": phys_devices("p-computehost2"),
            "p-controllerhost": phys_devices("p-controllerhost"),
        }

    def test_impacts(self):
        self.check_impacts()
