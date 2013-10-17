# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 IBM Corp.
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
from novaclient.v1_1 import floating_ips_bulk
from novaclient.tests import utils
from novaclient.tests.v1_1 import fakes


cs = fakes.FakeClient()


class FloatingIPsBulkTest(utils.TestCase):

    def test_list_floating_ips_bulk(self):
        fl = cs.floating_ips_bulk.list()
        cs.assert_called('GET', '/os-floating-ips-bulk')
        [self.assertTrue(isinstance(f, floating_ips_bulk.FloatingIP))
         for f in fl]

    def test_list_floating_ips_bulk_host_filter(self):
        fl = cs.floating_ips_bulk.list('testHost')
        cs.assert_called('GET', '/os-floating-ips-bulk/testHost')
        [self.assertTrue(isinstance(f, floating_ips_bulk.FloatingIP))
         for f in fl]

    def test_create_floating_ips_bulk(self):
        fl = cs.floating_ips_bulk.create('192.168.1.0/30')
        body = {'floating_ips_bulk_create': {'ip_range': '192.168.1.0/30'}}
        cs.assert_called('POST', '/os-floating-ips-bulk', body)
        self.assertEqual(fl.ip_range,
                         body['floating_ips_bulk_create']['ip_range'])

    def test_create_floating_ips_bulk_with_pool_and_host(self):
        fl = cs.floating_ips_bulk.create('192.168.1.0/30', 'poolTest',
                                         'interfaceTest')
        body = {'floating_ips_bulk_create':
                    {'ip_range': '192.168.1.0/30', 'pool': 'poolTest',
                     'interface': 'interfaceTest'}}
        cs.assert_called('POST', '/os-floating-ips-bulk', body)
        self.assertEqual(fl.ip_range,
                         body['floating_ips_bulk_create']['ip_range'])
        self.assertEqual(fl.pool,
                         body['floating_ips_bulk_create']['pool'])
        self.assertEqual(fl.interface,
                         body['floating_ips_bulk_create']['interface'])

    def test_delete_floating_ips_bulk(self):
        fl = cs.floating_ips_bulk.delete('192.168.1.0/30')
        body = {'ip_range': '192.168.1.0/30'}
        cs.assert_called('PUT', '/os-floating-ips-bulk/delete', body)
        self.assertEqual(fl.floating_ips_bulk_delete, body['ip_range'])
