from novaclient.v1_1 import networks
from novaclient.tests import utils
from novaclient.tests.v1_1 import fakes


cs = fakes.FakeClient()


class NetworksTest(utils.TestCase):

    def test_list_networks(self):
        fl = cs.networks.list()
        cs.assert_called('GET', '/os-networks')
        [self.assertTrue(isinstance(f, networks.Network)) for f in fl]

    def test_get_network(self):
        f = cs.networks.get(1)
        cs.assert_called('GET', '/os-networks/1')
        self.assertTrue(isinstance(f, networks.Network))

    def test_delete(self):
        cs.networks.delete('networkdelete')
        cs.assert_called('DELETE', '/os-networks/networkdelete')

    def test_create(self):
        f = cs.networks.create(label='foo')
        cs.assert_called('POST', '/os-networks',
                         {'network': {'label': 'foo'}})
        self.assertTrue(isinstance(f, networks.Network))

    def test_create_allparams(self):
        params = {
            'label': 'bar',
            'bridge': 'br0',
            'bridge_interface': 'int0',
            'cidr': '192.0.2.0/24',
            'cidr_v6': '2001:DB8::/32',
            'dns1': '1.1.1.1',
            'dns2': '1.1.1.2',
            'fixed_cidr': '198.51.100.0/24',
            'gateway': '192.0.2.1',
            'gateway_v6': '2001:DB8::1',
            'multi_host': 'T',
            'priority': '1',
            'project_id': '1',
            'vlan_start': 1,
            'vpn_start': 1
        }

        f = cs.networks.create(**params)
        cs.assert_called('POST', '/os-networks', {'network': params})
        self.assertTrue(isinstance(f, networks.Network))

    def test_associate_project(self):
        cs.networks.associate_project('networktest')
        cs.assert_called('POST', '/os-networks/add',
                         {'id': 'networktest'})

    def test_associate_host(self):
        cs.networks.associate_host('networktest', 'testHost')
        cs.assert_called('POST', '/os-networks/networktest/action',
                         {'associate_host': 'testHost'})

    def test_disassociate(self):
        cs.networks.disassociate('networkdisassociate')
        cs.assert_called('POST',
                         '/os-networks/networkdisassociate/action',
                         {'disassociate': None})

    def test_disassociate_host_only(self):
        cs.networks.disassociate('networkdisassociate', True, False)
        cs.assert_called('POST',
                         '/os-networks/networkdisassociate/action',
                         {'disassociate_host': None})

    def test_disassociate_project(self):
        cs.networks.disassociate('networkdisassociate', False, True)
        cs.assert_called('POST',
                         '/os-networks/networkdisassociate/action',
                         {'disassociate_project': None})

    def test_add(self):
        cs.networks.add('networkadd')
        cs.assert_called('POST', '/os-networks/add',
                         {'id': 'networkadd'})
