# Copyright 2012 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from novaclient.tests import utils
from novaclient.tests.v1_1 import fakes


cs = fakes.FakeClient()


class HypervisorsTest(utils.TestCase):
    def compare_to_expected(self, expected, hyper):
        for key, value in expected.items():
            self.assertEqual(getattr(hyper, key), value)

    def test_hypervisor_index(self):
        expected = [
            dict(id=1234, hypervisor_hostname='hyper1'),
            dict(id=5678, hypervisor_hostname='hyper2'),
            ]

        result = cs.hypervisors.list(False)
        cs.assert_called('GET', '/os-hypervisors')

        for idx, hyper in enumerate(result):
            self.compare_to_expected(expected[idx], hyper)

    def test_hypervisor_detail(self):
        expected = [
            dict(id=1234,
                 service=dict(id=1, host='compute1'),
                 vcpus=4,
                 memory_mb=10 * 1024,
                 local_gb=250,
                 vcpus_used=2,
                 memory_mb_used=5 * 1024,
                 local_gb_used=125,
                 hypervisor_type="xen",
                 hypervisor_version=3,
                 hypervisor_hostname="hyper1",
                 free_ram_mb=5 * 1024,
                 free_disk_gb=125,
                 current_workload=2,
                 running_vms=2,
                 cpu_info='cpu_info',
                 disk_available_least=100),
            dict(id=2,
                 service=dict(id=2, host="compute2"),
                 vcpus=4,
                 memory_mb=10 * 1024,
                 local_gb=250,
                 vcpus_used=2,
                 memory_mb_used=5 * 1024,
                 local_gb_used=125,
                 hypervisor_type="xen",
                 hypervisor_version=3,
                 hypervisor_hostname="hyper2",
                 free_ram_mb=5 * 1024,
                 free_disk_gb=125,
                 current_workload=2,
                 running_vms=2,
                 cpu_info='cpu_info',
                 disk_available_least=100)]

        result = cs.hypervisors.list()
        cs.assert_called('GET', '/os-hypervisors/detail')

        for idx, hyper in enumerate(result):
            self.compare_to_expected(expected[idx], hyper)

    def test_hypervisor_search(self):
        expected = [
            dict(id=1234, hypervisor_hostname='hyper1'),
            dict(id=5678, hypervisor_hostname='hyper2'),
            ]

        result = cs.hypervisors.search('hyper')
        cs.assert_called('GET', '/os-hypervisors/hyper/search')

        for idx, hyper in enumerate(result):
            self.compare_to_expected(expected[idx], hyper)

    def test_hypervisor_servers(self):
        expected = [
            dict(id=1234,
                 hypervisor_hostname='hyper1',
                 servers=[
                    dict(name='inst1', uuid='uuid1'),
                    dict(name='inst2', uuid='uuid2')]),
            dict(id=5678,
                 hypervisor_hostname='hyper2',
                 servers=[
                    dict(name='inst3', uuid='uuid3'),
                    dict(name='inst4', uuid='uuid4')]),
            ]

        result = cs.hypervisors.search('hyper', True)
        cs.assert_called('GET', '/os-hypervisors/hyper/servers')

        for idx, hyper in enumerate(result):
            self.compare_to_expected(expected[idx], hyper)

    def test_hypervisor_get(self):
        expected = dict(
            id=1234,
            service=dict(id=1, host='compute1'),
            vcpus=4,
            memory_mb=10 * 1024,
            local_gb=250,
            vcpus_used=2,
            memory_mb_used=5 * 1024,
            local_gb_used=125,
            hypervisor_type="xen",
            hypervisor_version=3,
            hypervisor_hostname="hyper1",
            free_ram_mb=5 * 1024,
            free_disk_gb=125,
            current_workload=2,
            running_vms=2,
            cpu_info='cpu_info',
            disk_available_least=100)

        result = cs.hypervisors.get(1234)
        cs.assert_called('GET', '/os-hypervisors/1234')

        self.compare_to_expected(expected, result)

    def test_hypervisor_uptime(self):
        expected = dict(
            id=1234,
            hypervisor_hostname="hyper1",
            uptime="fake uptime")

        result = cs.hypervisors.uptime(1234)
        cs.assert_called('GET', '/os-hypervisors/1234/uptime')

        self.compare_to_expected(expected, result)

    def test_hypervisor_statistics(self):
        expected = dict(
            count=2,
            vcpus=8,
            memory_mb=20 * 1024,
            local_gb=500,
            vcpus_used=4,
            memory_mb_used=10 * 1024,
            local_gb_used=250,
            free_ram_mb=10 * 1024,
            free_disk_gb=250,
            current_workload=4,
            running_vms=4,
            disk_available_least=200,
            )

        result = cs.hypervisors.statistics()
        cs.assert_called('GET', '/os-hypervisors/statistics')

        self.compare_to_expected(expected, result)
