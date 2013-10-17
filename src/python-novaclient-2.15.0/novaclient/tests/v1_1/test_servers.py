# -*- coding: utf-8 -*-

import mock
import six

from novaclient import exceptions
from novaclient.v1_1 import servers
from novaclient.tests import utils
from novaclient.tests.v1_1 import fakes


cs = fakes.FakeClient()


class ServersTest(utils.TestCase):

    def test_list_servers(self):
        sl = cs.servers.list()
        cs.assert_called('GET', '/servers/detail')
        [self.assertTrue(isinstance(s, servers.Server)) for s in sl]

    def test_list_servers_undetailed(self):
        sl = cs.servers.list(detailed=False)
        cs.assert_called('GET', '/servers')
        [self.assertTrue(isinstance(s, servers.Server)) for s in sl]

    def test_list_servers_with_marker_limit(self):
        sl = cs.servers.list(marker=1234, limit=2)
        cs.assert_called('GET', '/servers/detail?marker=1234&limit=2')
        for s in sl:
            self.assertTrue(isinstance(s, servers.Server))

    def test_get_server_details(self):
        s = cs.servers.get(1234)
        cs.assert_called('GET', '/servers/1234')
        self.assertTrue(isinstance(s, servers.Server))
        self.assertEqual(s.id, 1234)
        self.assertEqual(s.status, 'BUILD')

    def test_get_server_promote_details(self):
        s1 = cs.servers.list(detailed=False)[0]
        s2 = cs.servers.list(detailed=True)[0]
        self.assertNotEquals(s1._info, s2._info)
        s1.get()
        self.assertEqual(s1._info, s2._info)

    def test_create_server(self):
        s = cs.servers.create(
            name="My server",
            image=1,
            flavor=1,
            meta={'foo': 'bar'},
            userdata="hello moto",
            key_name="fakekey",
            files={
                '/etc/passwd': 'some data',                 # a file
                '/tmp/foo.txt': six.StringIO('data'),   # a stream
            }
        )
        cs.assert_called('POST', '/servers')
        self.assertTrue(isinstance(s, servers.Server))

    def test_create_server_boot_from_volume_with_nics(self):
        old_boot = cs.servers._boot

        nics = [{'net-id': '11111111-1111-1111-1111-111111111111',
                 'v4-fixed-ip': '10.0.0.7'}]
        bdm = {"volume_size": "1",
               "volume_id": "11111111-1111-1111-1111-111111111111",
               "delete_on_termination": "0",
               "device_name": "vda"}

        def wrapped_boot(url, key, *boot_args, **boot_kwargs):
            self.assertEqual(boot_kwargs['block_device_mapping'], bdm)
            self.assertEqual(boot_kwargs['nics'], nics)
            return old_boot(url, key, *boot_args, **boot_kwargs)

        @mock.patch.object(cs.servers, '_boot', wrapped_boot)
        def test_create_server_from_volume():
            s = cs.servers.create(
                name="My server",
                image=1,
                flavor=1,
                meta={'foo': 'bar'},
                userdata="hello moto",
                key_name="fakekey",
                block_device_mapping=bdm,
                nics=nics
            )
            cs.assert_called('POST', '/os-volumes_boot')
            self.assertTrue(isinstance(s, servers.Server))

        test_create_server_from_volume()

    def test_create_server_userdata_file_object(self):
        s = cs.servers.create(
            name="My server",
            image=1,
            flavor=1,
            meta={'foo': 'bar'},
            userdata=six.StringIO('hello moto'),
            files={
                '/etc/passwd': 'some data',                 # a file
                '/tmp/foo.txt': six.StringIO('data'),   # a stream
            },
        )
        cs.assert_called('POST', '/servers')
        self.assertTrue(isinstance(s, servers.Server))

    def test_create_server_userdata_unicode(self):
        s = cs.servers.create(
            name="My server",
            image=1,
            flavor=1,
            meta={'foo': 'bar'},
            userdata=six.u('こんにちは'),
            key_name="fakekey",
            files={
                '/etc/passwd': 'some data',                 # a file
                '/tmp/foo.txt': six.StringIO('data'),   # a stream
            },
        )
        cs.assert_called('POST', '/servers')
        self.assertTrue(isinstance(s, servers.Server))

    def test_create_server_userdata_utf8(self):
        s = cs.servers.create(
            name="My server",
            image=1,
            flavor=1,
            meta={'foo': 'bar'},
            userdata='こんにちは',
            key_name="fakekey",
            files={
                '/etc/passwd': 'some data',                 # a file
                '/tmp/foo.txt': six.StringIO('data'),   # a stream
            },
        )
        cs.assert_called('POST', '/servers')
        self.assertTrue(isinstance(s, servers.Server))

    def _create_disk_config(self, disk_config):
        s = cs.servers.create(
            name="My server",
            image=1,
            flavor=1,
            disk_config=disk_config
        )
        cs.assert_called('POST', '/servers')
        self.assertTrue(isinstance(s, servers.Server))

        # verify disk config param was used in the request:
        last_request = cs.client.callstack[-1]
        body = last_request[-1]
        server = body['server']
        self.assertTrue('OS-DCF:diskConfig' in server)
        self.assertEqual(disk_config, server['OS-DCF:diskConfig'])

    def test_create_server_disk_config_auto(self):
        self._create_disk_config('AUTO')

    def test_create_server_disk_config_manual(self):
        self._create_disk_config('MANUAL')

    def test_update_server(self):
        s = cs.servers.get(1234)

        # Update via instance
        s.update(name='hi')
        cs.assert_called('PUT', '/servers/1234')
        s.update(name='hi')
        cs.assert_called('PUT', '/servers/1234')

        # Silly, but not an error
        s.update()

        # Update via manager
        cs.servers.update(s, name='hi')
        cs.assert_called('PUT', '/servers/1234')

    def test_delete_server(self):
        s = cs.servers.get(1234)
        s.delete()
        cs.assert_called('DELETE', '/servers/1234')
        cs.servers.delete(1234)
        cs.assert_called('DELETE', '/servers/1234')
        cs.servers.delete(s)
        cs.assert_called('DELETE', '/servers/1234')

    def test_delete_server_meta(self):
        s = cs.servers.delete_meta(1234, ['test_key'])
        cs.assert_called('DELETE', '/servers/1234/metadata/test_key')

    def test_set_server_meta(self):
        s = cs.servers.set_meta(1234, {'test_key': 'test_value'})
        reval = cs.assert_called('POST', '/servers/1234/metadata',
                         {'metadata': {'test_key': 'test_value'}})

    def test_find(self):
        server = cs.servers.find(name='sample-server')
        cs.assert_called('GET', '/servers', pos=-2)
        cs.assert_called('GET', '/servers/1234', pos=-1)
        self.assertEqual(server.name, 'sample-server')

        self.assertRaises(exceptions.NoUniqueMatch, cs.servers.find,
                          flavor={"id": 1, "name": "256 MB Server"})

        sl = cs.servers.findall(flavor={"id": 1, "name": "256 MB Server"})
        self.assertEqual([s.id for s in sl], [1234, 5678, 9012])

    def test_reboot_server(self):
        s = cs.servers.get(1234)
        s.reboot()
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.reboot(s, reboot_type='HARD')
        cs.assert_called('POST', '/servers/1234/action')

    def test_rebuild_server(self):
        s = cs.servers.get(1234)
        s.rebuild(image=1)
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.rebuild(s, image=1)
        cs.assert_called('POST', '/servers/1234/action')
        s.rebuild(image=1, password='5678')
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.rebuild(s, image=1, password='5678')
        cs.assert_called('POST', '/servers/1234/action')

    def _rebuild_resize_disk_config(self, disk_config, operation="rebuild"):
        s = cs.servers.get(1234)

        if operation == "rebuild":
            s.rebuild(image=1, disk_config=disk_config)
        elif operation == "resize":
            s.resize(flavor=1, disk_config=disk_config)
        cs.assert_called('POST', '/servers/1234/action')

        # verify disk config param was used in the request:
        last_request = cs.client.callstack[-1]
        body = last_request[-1]

        d = body[operation]
        self.assertTrue('OS-DCF:diskConfig' in d)
        self.assertEqual(disk_config, d['OS-DCF:diskConfig'])

    def test_rebuild_server_disk_config_auto(self):
        self._rebuild_resize_disk_config('AUTO')

    def test_rebuild_server_disk_config_manual(self):
        self._rebuild_resize_disk_config('MANUAL')

    def test_resize_server(self):
        s = cs.servers.get(1234)
        s.resize(flavor=1)
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.resize(s, flavor=1)
        cs.assert_called('POST', '/servers/1234/action')

    def test_resize_server_disk_config_auto(self):
        self._rebuild_resize_disk_config('AUTO', 'resize')

    def test_resize_server_disk_config_manual(self):
        self._rebuild_resize_disk_config('MANUAL', 'resize')

    def test_confirm_resized_server(self):
        s = cs.servers.get(1234)
        s.confirm_resize()
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.confirm_resize(s)
        cs.assert_called('POST', '/servers/1234/action')

    def test_revert_resized_server(self):
        s = cs.servers.get(1234)
        s.revert_resize()
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.revert_resize(s)
        cs.assert_called('POST', '/servers/1234/action')

    def test_migrate_server(self):
        s = cs.servers.get(1234)
        s.migrate()
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.migrate(s)
        cs.assert_called('POST', '/servers/1234/action')

    def test_add_fixed_ip(self):
        s = cs.servers.get(1234)
        s.add_fixed_ip(1)
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.add_fixed_ip(s, 1)
        cs.assert_called('POST', '/servers/1234/action')

    def test_remove_fixed_ip(self):
        s = cs.servers.get(1234)
        s.remove_fixed_ip('10.0.0.1')
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.remove_fixed_ip(s, '10.0.0.1')
        cs.assert_called('POST', '/servers/1234/action')

    def test_add_floating_ip(self):
        s = cs.servers.get(1234)
        s.add_floating_ip('11.0.0.1')
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.add_floating_ip(s, '11.0.0.1')
        cs.assert_called('POST', '/servers/1234/action')
        f = cs.floating_ips.list()[0]
        cs.servers.add_floating_ip(s, f)
        cs.assert_called('POST', '/servers/1234/action')
        s.add_floating_ip(f)
        cs.assert_called('POST', '/servers/1234/action')

    def test_add_floating_ip_to_fixed(self):
        s = cs.servers.get(1234)
        s.add_floating_ip('11.0.0.1', fixed_address='12.0.0.1')
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.add_floating_ip(s, '11.0.0.1',
                                   fixed_address='12.0.0.1')
        cs.assert_called('POST', '/servers/1234/action')
        f = cs.floating_ips.list()[0]
        cs.servers.add_floating_ip(s, f)
        cs.assert_called('POST', '/servers/1234/action')
        s.add_floating_ip(f)
        cs.assert_called('POST', '/servers/1234/action')

    def test_remove_floating_ip(self):
        s = cs.servers.get(1234)
        s.remove_floating_ip('11.0.0.1')
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.remove_floating_ip(s, '11.0.0.1')
        cs.assert_called('POST', '/servers/1234/action')
        f = cs.floating_ips.list()[0]
        cs.servers.remove_floating_ip(s, f)
        cs.assert_called('POST', '/servers/1234/action')
        s.remove_floating_ip(f)
        cs.assert_called('POST', '/servers/1234/action')

    def test_stop(self):
        s = cs.servers.get(1234)
        s.stop()
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.stop(s)
        cs.assert_called('POST', '/servers/1234/action')

    def test_force_delete(self):
        s = cs.servers.get(1234)
        s.force_delete()
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.force_delete(s)
        cs.assert_called('POST', '/servers/1234/action')

    def test_restore(self):
        s = cs.servers.get(1234)
        s.restore()
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.restore(s)
        cs.assert_called('POST', '/servers/1234/action')

    def test_start(self):
        s = cs.servers.get(1234)
        s.start()
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.start(s)
        cs.assert_called('POST', '/servers/1234/action')

    def test_rescue(self):
        s = cs.servers.get(1234)
        s.rescue()
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.rescue(s)
        cs.assert_called('POST', '/servers/1234/action')

    def test_unrescue(self):
        s = cs.servers.get(1234)
        s.unrescue()
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.unrescue(s)
        cs.assert_called('POST', '/servers/1234/action')

    def test_lock(self):
        s = cs.servers.get(1234)
        s.lock()
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.lock(s)
        cs.assert_called('POST', '/servers/1234/action')

    def test_unlock(self):
        s = cs.servers.get(1234)
        s.unlock()
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.unlock(s)
        cs.assert_called('POST', '/servers/1234/action')

    def test_backup(self):
        s = cs.servers.get(1234)
        s.backup('back1', 'daily', 1)
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.backup(s, 'back1', 'daily', 2)
        cs.assert_called('POST', '/servers/1234/action')

    def test_get_console_output_without_length(self):
        success = 'foo'
        s = cs.servers.get(1234)
        s.get_console_output()
        self.assertEqual(s.get_console_output(), success)
        cs.assert_called('POST', '/servers/1234/action')

        cs.servers.get_console_output(s)
        self.assertEqual(cs.servers.get_console_output(s), success)
        cs.assert_called('POST', '/servers/1234/action')

    def test_get_console_output_with_length(self):
        success = 'foo'

        s = cs.servers.get(1234)
        s.get_console_output(length=50)
        self.assertEqual(s.get_console_output(length=50), success)
        cs.assert_called('POST', '/servers/1234/action')

        cs.servers.get_console_output(s, length=50)
        self.assertEqual(cs.servers.get_console_output(s, length=50), success)
        cs.assert_called('POST', '/servers/1234/action')

    def test_get_password(self):
        s = cs.servers.get(1234)
        self.assertEqual(s.get_password('/foo/id_rsa'), '')
        cs.assert_called('GET', '/servers/1234/os-server-password')

    def test_clear_password(self):
        s = cs.servers.get(1234)
        s.clear_password()
        cs.assert_called('DELETE', '/servers/1234/os-server-password')

    def test_get_server_diagnostics(self):
        s = cs.servers.get(1234)
        diagnostics = s.diagnostics()
        self.assertTrue(diagnostics is not None)
        cs.assert_called('GET', '/servers/1234/diagnostics')

        diagnostics_from_manager = cs.servers.diagnostics(1234)
        self.assertTrue(diagnostics_from_manager is not None)
        cs.assert_called('GET', '/servers/1234/diagnostics')

        self.assertEqual(diagnostics, diagnostics_from_manager)

    def test_get_vnc_console(self):
        s = cs.servers.get(1234)
        s.get_vnc_console('fake')
        cs.assert_called('POST', '/servers/1234/action')

        cs.servers.get_vnc_console(s, 'fake')
        cs.assert_called('POST', '/servers/1234/action')

    def test_get_spice_console(self):
        s = cs.servers.get(1234)
        s.get_spice_console('fake')
        cs.assert_called('POST', '/servers/1234/action')

        cs.servers.get_spice_console(s, 'fake')
        cs.assert_called('POST', '/servers/1234/action')

    def test_create_image(self):
        s = cs.servers.get(1234)
        s.create_image('123')
        cs.assert_called('POST', '/servers/1234/action')
        s.create_image('123', {})
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.create_image(s, '123')
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.create_image(s, '123', {})

    def test_live_migrate_server(self):
        s = cs.servers.get(1234)
        s.live_migrate(host='hostname', block_migration=False,
                       disk_over_commit=False)
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.live_migrate(s, host='hostname', block_migration=False,
                                disk_over_commit=False)
        cs.assert_called('POST', '/servers/1234/action')

    def test_reset_state(self):
        s = cs.servers.get(1234)
        s.reset_state('newstate')
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.reset_state(s, 'newstate')
        cs.assert_called('POST', '/servers/1234/action')

    def test_reset_network(self):
        s = cs.servers.get(1234)
        s.reset_network()
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.reset_network(s)
        cs.assert_called('POST', '/servers/1234/action')

    def test_add_security_group(self):
        s = cs.servers.get(1234)
        s.add_security_group('newsg')
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.add_security_group(s, 'newsg')
        cs.assert_called('POST', '/servers/1234/action')

    def test_remove_security_group(self):
        s = cs.servers.get(1234)
        s.remove_security_group('oldsg')
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.remove_security_group(s, 'oldsg')
        cs.assert_called('POST', '/servers/1234/action')

    def test_list_security_group(self):
        s = cs.servers.get(1234)
        s.list_security_group()
        cs.assert_called('GET', '/servers/1234/os-security-groups')

    def test_evacuate(self):
        s = cs.servers.get(1234)
        s.evacuate('fake_target_host', 'True')
        cs.assert_called('POST', '/servers/1234/action')
        cs.servers.evacuate(s, 'fake_target_host', 'False', 'NewAdminPassword')
        cs.assert_called('POST', '/servers/1234/action')

    def test_interface_list(self):
        s = cs.servers.get(1234)
        s.interface_list()
        cs.assert_called('GET', '/servers/1234/os-interface')

    def test_interface_attach(self):
        s = cs.servers.get(1234)
        s.interface_attach(None, None, None)
        cs.assert_called('POST', '/servers/1234/os-interface')

    def test_interface_detach(self):
        s = cs.servers.get(1234)
        s.interface_detach('port-id')
        cs.assert_called('DELETE', '/servers/1234/os-interface/port-id')
