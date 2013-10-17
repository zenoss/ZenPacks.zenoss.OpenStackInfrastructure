# Copyright (c) 2011 X.commerce, a business unit of eBay Inc.
#
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

from novaclient.v1_1 import floating_ip_pools
from novaclient.tests import utils
from novaclient.tests.v1_1 import fakes


cs = fakes.FakeClient()


class TestFloatingIPPools(utils.TestCase):

    def test_list_floating_ips(self):
        fl = cs.floating_ip_pools.list()
        cs.assert_called('GET', '/os-floating-ip-pools')
        [self.assertTrue(isinstance(f, floating_ip_pools.FloatingIPPool))
                                                                   for f in fl]
