# Copyright 2010 Jacob Kaplan-Moss

# Copyright 2011 OpenStack Foundation
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

"""
Server interface.
"""

import six

from novaclient import base
from novaclient import crypto
from novaclient.openstack.common.py3kcompat import urlutils
from novaclient.v1_1.security_groups import SecurityGroup

REBOOT_SOFT, REBOOT_HARD = 'SOFT', 'HARD'


class Server(base.Resource):
    HUMAN_ID = True

    def __repr__(self):
        return "<Server: %s>" % self.name

    def delete(self):
        """
        Delete (i.e. shut down and delete the image) this server.
        """
        self.manager.delete(self)

    def update(self, name=None):
        """
        Update the name or the password for this server.

        :param name: Update the server's name.
        :param password: Update the root password.
        """
        self.manager.update(self, name=name)

    def get_console_output(self, length=None):
        """
        Get text console log output from Server.

        :param length: The number of lines you would like to retrieve (as int)
        """
        return self.manager.get_console_output(self, length)

    def get_vnc_console(self, console_type):
        """
        Get vnc console for a Server.

        :param console_type: Type of console ('novnc' or 'xvpvnc')
        """
        return self.manager.get_vnc_console(self, console_type)

    def get_spice_console(self, console_type):
        """
        Get spice console for a Server.

        :param console_type: Type of console ('spice-html5')
        """
        return self.manager.get_spice_console(self, console_type)

    def get_password(self, private_key):
        """
        Get password for a Server.

        :param private_key: Path to private key file for decryption
        """
        return self.manager.get_password(self, private_key)

    def clear_password(self):
        """
        Get password for a Server.

        """
        return self.manager.clear_password(self)

    def add_fixed_ip(self, network_id):
        """
        Add an IP address on a network.

        :param network_id: The ID of the network the IP should be on.
        """
        self.manager.add_fixed_ip(self, network_id)

    def add_floating_ip(self, address, fixed_address=None):
        """
        Add floating IP to an instance

        :param address: The ip address or FloatingIP to add to the instance
        :param fixed_address: The fixedIP address the FloatingIP is to be
               associated with (optional)
        """
        self.manager.add_floating_ip(self, address, fixed_address)

    def remove_floating_ip(self, address):
        """
        Remove floating IP from an instance

        :param address: The ip address or FloatingIP to remove
        """
        self.manager.remove_floating_ip(self, address)

    def stop(self):
        """
        Stop -- Stop the running server.
        """
        self.manager.stop(self)

    def force_delete(self):
        """
        Force delete -- Force delete a server.
        """
        self.manager.force_delete(self)

    def restore(self):
        """
        Restore -- Restore a server in 'soft-deleted' state.
        """
        self.manager.restore(self)

    def start(self):
        """
        Start -- Start the paused server.
        """
        self.manager.start(self)

    def pause(self):
        """
        Pause -- Pause the running server.
        """
        self.manager.pause(self)

    def unpause(self):
        """
        Unpause -- Unpause the paused server.
        """
        self.manager.unpause(self)

    def lock(self):
        """
        Lock -- Lock the instance from certain operations.
        """
        self.manager.lock(self)

    def unlock(self):
        """
        Unlock -- Remove instance lock.
        """
        self.manager.unlock(self)

    def suspend(self):
        """
        Suspend -- Suspend the running server.
        """
        self.manager.suspend(self)

    def resume(self):
        """
        Resume -- Resume the suspended server.
        """
        self.manager.resume(self)

    def rescue(self):
        """
        Rescue -- Rescue the problematic server.
        """
        return self.manager.rescue(self)

    def unrescue(self):
        """
        Unrescue -- Unrescue the rescued server.
        """
        self.manager.unrescue(self)

    def diagnostics(self):
        """Diagnostics -- Retrieve server diagnostics."""
        return self.manager.diagnostics(self)

    def migrate(self):
        """
        Migrate a server to a new host.
        """
        self.manager.migrate(self)

    def remove_fixed_ip(self, address):
        """
        Remove an IP address.

        :param address: The IP address to remove.
        """
        self.manager.remove_fixed_ip(self, address)

    def change_password(self, password):
        """
        Update the password for a server.
        """
        self.manager.change_password(self, password)

    def reboot(self, reboot_type=REBOOT_SOFT):
        """
        Reboot the server.

        :param reboot_type: either :data:`REBOOT_SOFT` for a software-level
                reboot, or `REBOOT_HARD` for a virtual power cycle hard reboot.
        """
        self.manager.reboot(self, reboot_type)

    def rebuild(self, image, password=None, **kwargs):
        """
        Rebuild -- shut down and then re-image -- this server.

        :param image: the :class:`Image` (or its ID) to re-image with.
        :param password: string to set as password on the rebuilt server.
        """
        return self.manager.rebuild(self, image, password=password, **kwargs)

    def resize(self, flavor, **kwargs):
        """
        Resize the server's resources.

        :param flavor: the :class:`Flavor` (or its ID) to resize to.

        Until a resize event is confirmed with :meth:`confirm_resize`, the old
        server will be kept around and you'll be able to roll back to the old
        flavor quickly with :meth:`revert_resize`. All resizes are
        automatically confirmed after 24 hours.
        """
        self.manager.resize(self, flavor, **kwargs)

    def create_image(self, image_name, metadata=None):
        """
        Create an image based on this server.

        :param image_name: The name to assign the newly create image.
        :param metadata: Metadata to assign to the image.
        """
        return self.manager.create_image(self, image_name, metadata)

    def backup(self, backup_name, backup_type, rotation):
        """
        Backup a server instance.

        :param backup_name: Name of the backup image
        :param backup_type: The backup type, like 'daily' or 'weekly'
        :param rotation: Int parameter representing how many backups to
                        keep around.
        """
        self.manager.backup(self, backup_name, backup_type, rotation)

    def confirm_resize(self):
        """
        Confirm that the resize worked, thus removing the original server.
        """
        self.manager.confirm_resize(self)

    def revert_resize(self):
        """
        Revert a previous resize, switching back to the old server.
        """
        self.manager.revert_resize(self)

    @property
    def networks(self):
        """
        Generate a simplified list of addresses
        """
        networks = {}
        try:
            for network_label, address_list in self.addresses.items():
                networks[network_label] = [a['addr'] for a in address_list]
            return networks
        except Exception:
            return {}

    def live_migrate(self, host=None,
                     block_migration=False,
                     disk_over_commit=False):
        """
        Migrates a running instance to a new machine.
        """
        self.manager.live_migrate(self, host,
                                  block_migration,
                                  disk_over_commit)

    def reset_state(self, state='error'):
        """
        Reset the state of an instance to active or error.
        """
        self.manager.reset_state(self, state)

    def reset_network(self):
        """
        Reset network of an instance.
        """
        self.manager.reset_network(self)

    def add_security_group(self, security_group):
        """
        Add a security group to an instance.
        """
        self.manager.add_security_group(self, security_group)

    def remove_security_group(self, security_group):
        """
        Remove a security group from an instance.
        """
        self.manager.remove_security_group(self, security_group)

    def list_security_group(self):
        """
        List security group(s) of an instance.
        """
        return self.manager.list_security_group(self)

    def evacuate(self, host, on_shared_storage, password=None):
        """
        Evacuate an instance from failed host to specified host.

        :param host: Name of the target host
        :param on_shared_storage: Specifies whether instance files located
                        on shared storage
        :param password: string to set as password on the evacuated server.
        """
        return self.manager.evacuate(self, host, on_shared_storage, password)

    def interface_list(self):
        """
        List interfaces attached to an instance.
        """
        return self.manager.interface_list(self)

    def interface_attach(self, port_id, net_id, fixed_ip):
        """
        Attach a network interface to an instance.
        """
        return self.manager.interface_attach(self, port_id, net_id, fixed_ip)

    def interface_detach(self, port_id):
        """
        Detach a network interface from an instance.
        """
        return self.manager.interface_detach(self, port_id)


class ServerManager(base.BootingManagerWithFind):
    resource_class = Server

    def get(self, server):
        """
        Get a server.

        :param server: ID of the :class:`Server` to get.
        :rtype: :class:`Server`
        """
        return self._get("/servers/%s" % base.getid(server), "server")

    def list(self, detailed=True, search_opts=None, marker=None, limit=None):
        """
        Get a list of servers.

        :param detailed: Whether to return detailed server info (optional).
        :param search_opts: Search options to filter out servers (optional).
        :param marker: Begin returning servers that appear later in the server
                       list than that represented by this server id (optional).
        :param limit: Maximum number of servers to return (optional).

        :rtype: list of :class:`Server`
        """
        if search_opts is None:
            search_opts = {}

        qparams = {}

        for opt, val in six.iteritems(search_opts):
            if val:
                qparams[opt] = val

        if marker:
            qparams['marker'] = marker

        if limit:
            qparams['limit'] = limit

        query_string = "?%s" % urlutils.urlencode(qparams) if qparams else ""

        detail = ""
        if detailed:
            detail = "/detail"
        return self._list("/servers%s%s" % (detail, query_string), "servers")

    def add_fixed_ip(self, server, network_id):
        """
        Add an IP address on a network.

        :param server: The :class:`Server` (or its ID) to add an IP to.
        :param network_id: The ID of the network the IP should be on.
        """
        self._action('addFixedIp', server, {'networkId': network_id})

    def remove_fixed_ip(self, server, address):
        """
        Remove an IP address.

        :param server: The :class:`Server` (or its ID) to add an IP to.
        :param address: The IP address to remove.
        """
        self._action('removeFixedIp', server, {'address': address})

    def add_floating_ip(self, server, address, fixed_address=None):
        """
        Add a floating ip to an instance

        :param server: The :class:`Server` (or its ID) to add an IP to.
        :param address: The FloatingIP or string floating address to add.
        :param fixed_address: The FixedIP the floatingIP should be
                              associated with (optional)
        """

        address = address.ip if hasattr(address, 'ip') else address
        if fixed_address:
            if hasattr(fixed_address, 'ip'):
                fixed_address = fixed_address.ip
            self._action('addFloatingIp', server,
                         {'address': address, 'fixed_address': fixed_address})
        else:
            self._action('addFloatingIp', server, {'address': address})

    def remove_floating_ip(self, server, address):
        """
        Remove a floating IP address.

        :param server: The :class:`Server` (or its ID) to remove an IP from.
        :param address: The FloatingIP or string floating address to remove.
        """

        address = address.ip if hasattr(address, 'ip') else address
        self._action('removeFloatingIp', server, {'address': address})

    def get_vnc_console(self, server, console_type):
        """
        Get a vnc console for an instance

        :param server: The :class:`Server` (or its ID) to add an IP to.
        :param console_type: Type of vnc console to get ('novnc' or 'xvpvnc')
        """

        return self._action('os-getVNCConsole', server,
                            {'type': console_type})[1]

    def get_spice_console(self, server, console_type):
        """
        Get a spice console for an instance

        :param server: The :class:`Server` (or its ID) to add an IP to.
        :param console_type: Type of spice console to get ('spice-html5')
        """

        return self._action('os-getSPICEConsole', server,
                            {'type': console_type})[1]

    def get_password(self, server, private_key):
        """
        Get password for an instance

        Requires that openssl is installed and in the path

        :param server: The :class:`Server` (or its ID) to add an IP to.
        :param private_key: The private key to decrypt password
        """

        _resp, body = self.api.client.get("/servers/%s/os-server-password"
                                          % base.getid(server))
        if body and body.get('password'):
            try:
                return crypto.decrypt_password(private_key, body['password'])
            except Exception as exc:
                return '%sFailed to decrypt:\n%s' % (exc, body['password'])
        return ''

    def clear_password(self, server):
        """
        Clear password for an instance

        :param server: The :class:`Server` (or its ID) to add an IP to.
        """

        return self._delete("/servers/%s/os-server-password"
                            % base.getid(server))

    def stop(self, server):
        """
        Stop the server.
        """
        return self._action('os-stop', server, None)

    def force_delete(self, server):
        """
        Force delete the server.
        """
        return self._action('forceDelete', server, None)

    def restore(self, server):
        """
        Restore soft-deleted server.
        """
        return self._action('restore', server, None)

    def start(self, server):
        """
        Start the server.
        """
        self._action('os-start', server, None)

    def pause(self, server):
        """
        Pause the server.
        """
        self._action('pause', server, None)

    def unpause(self, server):
        """
        Unpause the server.
        """
        self._action('unpause', server, None)

    def lock(self, server):
        """
        Lock the server.
        """
        self._action('lock', server, None)

    def unlock(self, server):
        """
        Unlock the server.
        """
        self._action('unlock', server, None)

    def suspend(self, server):
        """
        Suspend the server.
        """
        self._action('suspend', server, None)

    def resume(self, server):
        """
        Resume the server.
        """
        self._action('resume', server, None)

    def rescue(self, server):
        """
        Rescue the server.
        """
        return self._action('rescue', server, None)

    def unrescue(self, server):
        """
        Unrescue the server.
        """
        self._action('unrescue', server, None)

    def diagnostics(self, server):
        """Retrieve server diagnostics."""
        return self.api.client.get("/servers/%s/diagnostics" %
                                   base.getid(server))

    def create(self, name, image, flavor, meta=None, files=None,
               reservation_id=None, min_count=None,
               max_count=None, security_groups=None, userdata=None,
               key_name=None, availability_zone=None,
               block_device_mapping=None, block_device_mapping_v2=None,
               nics=None, scheduler_hints=None,
               config_drive=None, disk_config=None, **kwargs):
        # TODO(anthony): indicate in doc string if param is an extension
        # and/or optional
        """
        Create (boot) a new server.

        :param name: Something to name the server.
        :param image: The :class:`Image` to boot with.
        :param flavor: The :class:`Flavor` to boot onto.
        :param meta: A dict of arbitrary key/value metadata to store for this
                     server. A maximum of five entries is allowed, and both
                     keys and values must be 255 characters or less.
        :param files: A dict of files to overrwrite on the server upon boot.
                      Keys are file names (i.e. ``/etc/passwd``) and values
                      are the file contents (either as a string or as a
                      file-like object). A maximum of five entries is allowed,
                      and each file must be 10k or less.
        :param userdata: user data to pass to be exposed by the metadata
                      server this can be a file type object as well or a
                      string.
        :param reservation_id: a UUID for the set of servers being requested.
        :param key_name: (optional extension) name of previously created
                      keypair to inject into the instance.
        :param availability_zone: Name of the availability zone for instance
                                  placement.
        :param block_device_mapping: (optional extension) A dict of block
                      device mappings for this server.
        :param block_device_mapping_v2: (optional extension) A dict of block
                      device mappings for this server.
        :param nics:  (optional extension) an ordered list of nics to be
                      added to this server, with information about
                      connected networks, fixed ips, port etc.
        :param scheduler_hints: (optional extension) arbitrary key-value pairs
                            specified by the client to help boot an instance
        :param config_drive: (optional extension) value for config drive
                            either boolean, or volume-id
        :param disk_config: (optional extension) control how the disk is
                            partitioned when the server is created.  possible
                            values are 'AUTO' or 'MANUAL'.
        """
        if not min_count:
            min_count = 1
        if not max_count:
            max_count = min_count
        if min_count > max_count:
            min_count = max_count

        boot_args = [name, image, flavor]

        boot_kwargs = dict(
            meta=meta, files=files, userdata=userdata,
            reservation_id=reservation_id, min_count=min_count,
            max_count=max_count, security_groups=security_groups,
            key_name=key_name, availability_zone=availability_zone,
            scheduler_hints=scheduler_hints, config_drive=config_drive,
            disk_config=disk_config, **kwargs)

        if block_device_mapping:
            resource_url = "/os-volumes_boot"
            boot_kwargs['block_device_mapping'] = block_device_mapping
        elif block_device_mapping_v2:
            resource_url = "/os-volumes_boot"
            boot_kwargs['block_device_mapping_v2'] = block_device_mapping_v2
        else:
            resource_url = "/servers"
        if nics:
            boot_kwargs['nics'] = nics

        response_key = "server"
        return self._boot(resource_url, response_key, *boot_args,
                **boot_kwargs)

    def update(self, server, name=None):
        """
        Update the name or the password for a server.

        :param server: The :class:`Server` (or its ID) to update.
        :param name: Update the server's name.
        """
        if name is None:
            return

        body = {
            "server": {
                "name": name,
            },
        }

        return self._update("/servers/%s" % base.getid(server), body, "server")

    def change_password(self, server, password):
        """
        Update the password for a server.
        """
        self._action("changePassword", server, {"adminPass": password})

    def delete(self, server):
        """
        Delete (i.e. shut down and delete the image) this server.
        """
        self._delete("/servers/%s" % base.getid(server))

    def reboot(self, server, reboot_type=REBOOT_SOFT):
        """
        Reboot a server.

        :param server: The :class:`Server` (or its ID) to share onto.
        :param reboot_type: either :data:`REBOOT_SOFT` for a software-level
                reboot, or `REBOOT_HARD` for a virtual power cycle hard reboot.
        """
        self._action('reboot', server, {'type': reboot_type})

    def rebuild(self, server, image, password=None, disk_config=None,
                **kwargs):
        """
        Rebuild -- shut down and then re-image -- a server.

        :param server: The :class:`Server` (or its ID) to share onto.
        :param image: the :class:`Image` (or its ID) to re-image with.
        :param password: string to set as password on the rebuilt server.
        :param disk_config: partitioning mode to use on the rebuilt server.
                            Valid values are 'AUTO' or 'MANUAL'
        """
        body = {'imageRef': base.getid(image)}
        if password is not None:
            body['adminPass'] = password
        if disk_config is not None:
            body['OS-DCF:diskConfig'] = disk_config

        _resp, body = self._action('rebuild', server, body, **kwargs)
        return Server(self, body['server'])

    def migrate(self, server):
        """
        Migrate a server to a new host.

        :param server: The :class:`Server` (or its ID).
        """
        self._action('migrate', server)

    def resize(self, server, flavor, disk_config=None, **kwargs):
        """
        Resize a server's resources.

        :param server: The :class:`Server` (or its ID) to share onto.
        :param flavor: the :class:`Flavor` (or its ID) to resize to.
        :param disk_config: partitioning mode to use on the rebuilt server.
                            Valid values are 'AUTO' or 'MANUAL'

        Until a resize event is confirmed with :meth:`confirm_resize`, the old
        server will be kept around and you'll be able to roll back to the old
        flavor quickly with :meth:`revert_resize`. All resizes are
        automatically confirmed after 24 hours.
        """
        info = {'flavorRef': base.getid(flavor)}
        if disk_config is not None:
            info['OS-DCF:diskConfig'] = disk_config

        self._action('resize', server, info=info, **kwargs)

    def confirm_resize(self, server):
        """
        Confirm that the resize worked, thus removing the original server.

        :param server: The :class:`Server` (or its ID) to share onto.
        """
        self._action('confirmResize', server)

    def revert_resize(self, server):
        """
        Revert a previous resize, switching back to the old server.

        :param server: The :class:`Server` (or its ID) to share onto.
        """
        self._action('revertResize', server)

    def create_image(self, server, image_name, metadata=None):
        """
        Snapshot a server.

        :param server: The :class:`Server` (or its ID) to share onto.
        :param image_name: Name to give the snapshot image
        :param meta: Metadata to give newly-created image entity
        """
        body = {'name': image_name, 'metadata': metadata or {}}
        resp = self._action('createImage', server, body)[0]
        location = resp.headers['location']
        image_uuid = location.split('/')[-1]
        return image_uuid

    def backup(self, server, backup_name, backup_type, rotation):
        """
        Backup a server instance.

        :param server: The :class:`Server` (or its ID) to share onto.
        :param backup_name: Name of the backup image
        :param backup_type: The backup type, like 'daily' or 'weekly'
        :param rotation: Int parameter representing how many backups to
                        keep around.
        """
        body = {'name': backup_name,
                'backup_type': backup_type,
                'rotation': rotation}
        self._action('createBackup', server, body)

    def set_meta(self, server, metadata):
        """
        Set a servers metadata
        :param server: The :class:`Server` to add metadata to
        :param metadata: A dict of metadata to add to the server
        """
        body = {'metadata': metadata}
        return self._create("/servers/%s/metadata" % base.getid(server),
                             body, "metadata")

    def get_console_output(self, server, length=None):
        """
        Get text console log output from Server.

        :param server: The :class:`Server` (or its ID) whose console output
                        you would like to retrieve.
        :param length: The number of tail loglines you would like to retrieve.
        """
        return self._action('os-getConsoleOutput',
                            server,
                            {'length': length})[1]['output']

    def delete_meta(self, server, keys):
        """
        Delete metadata from an server
        :param server: The :class:`Server` to add metadata to
        :param keys: A list of metadata keys to delete from the server
        """
        for k in keys:
            self._delete("/servers/%s/metadata/%s" % (base.getid(server), k))

    def live_migrate(self, server, host, block_migration, disk_over_commit):
        """
        Migrates a running instance to a new machine.

        :param server: instance id which comes from nova list.
        :param host: destination host name.
        :param block_migration: if True, do block_migration.
        :param disk_over_commit: if True, Allow overcommit.

        """
        self._action('os-migrateLive', server,
                     {'host': host,
                      'block_migration': block_migration,
                      'disk_over_commit': disk_over_commit})

    def reset_state(self, server, state='error'):
        """
        Reset the state of an instance to active or error.

        :param server: ID of the instance to reset the state of.
        :param state: Desired state; either 'active' or 'error'.
                      Defaults to 'error'.
        """
        self._action('os-resetState', server, dict(state=state))

    def reset_network(self, server):
        """
        Reset network of an instance.
        """
        self._action('resetNetwork', server)

    def add_security_group(self, server, security_group):
        """
        Add a Security Group to an instance

        :param server: ID of the instance.
        :param security_group: The name of security group to add.

        """
        self._action('addSecurityGroup', server, {'name': security_group})

    def remove_security_group(self, server, security_group):
        """
        Add a Security Group to an instance

        :param server: ID of the instance.
        :param security_group: The name of security group to remove.

        """
        self._action('removeSecurityGroup', server, {'name': security_group})

    def list_security_group(self, server):
        """
        List Security Group(s) of an instance

        :param server: ID of the instance.

        """
        return self._list('/servers/%s/os-security-groups' %
                          base.getid(server), 'security_groups', SecurityGroup)

    def evacuate(self, server, host, on_shared_storage, password=None):
        """
        Evacuate a server instance.

        :param server: The :class:`Server` (or its ID) to share onto.
        :param host: Name of the target host.
        :param on_shared_storage: Specifies whether instance files located
                        on shared storage
        :param password: string to set as password on the evacuated server.
        """
        body = {
                'host': host,
                'onSharedStorage': on_shared_storage,
                }

        if password is not None:
            body['adminPass'] = password

        return self._action('evacuate', server, body)

    def interface_list(self, server):
        """
        List attached network interfaces

        :param server: The :class:`Server` (or its ID) to query.
        """
        return self._list('/servers/%s/os-interface' % base.getid(server),
                          'interfaceAttachments')

    def interface_attach(self, server, port_id, net_id, fixed_ip):
        """
        Attach a network_interface to an instance.

        :param server: The :class:`Server` (or its ID) to attach to.
        :param port_id: The port to attach.
        """

        body = {'interfaceAttachment': {}}
        if port_id:
            body['interfaceAttachment']['port_id'] = port_id
        if net_id:
            body['interfaceAttachment']['net_id'] = net_id
        if fixed_ip:
            body['interfaceAttachment']['fixed_ips'] = [
                {'ip_address': fixed_ip}]

        return self._create('/servers/%s/os-interface' % base.getid(server),
                            body, 'interfaceAttachment')

    def interface_detach(self, server, port_id):
        """
        Detach a network_interface from an instance.

        :param server: The :class:`Server` (or its ID) to detach from.
        :param port_id: The port to detach.
        """
        self._delete('/servers/%s/os-interface/%s' % (base.getid(server),
                                                      port_id))

    def _action(self, action, server, info=None, **kwargs):
        """
        Perform a server "action" -- reboot/rebuild/resize/etc.
        """
        body = {action: info}
        self.run_hooks('modify_body_for_action', body, **kwargs)
        url = '/servers/%s/action' % base.getid(server)
        return self.api.client.post(url, body=body)
