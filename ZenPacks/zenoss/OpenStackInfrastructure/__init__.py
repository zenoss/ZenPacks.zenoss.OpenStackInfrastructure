##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013-2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""ZenPacks.zenoss.OpenStackInfrastructure.- OpenStack monitoring for Zenoss.

This module contains initialization code for the ZenPack. Everything in
the module scope will be executed at startup by all Zenoss Python
processes.

The initialization order for ZenPacks is defined by
$ZENHOME/ZenPacks/easy-install.pth.

"""

from . import zenpacklib

# Load YAML
CFG = zenpacklib.load_yaml()

import os
import logging
log = logging.getLogger('zen.OpenStack')

from Products.ZenUtils.Utils import unused
from OFS.CopySupport import CopyError

from . import schema
from service_migration import install_migrate_zenpython, remove_migrate_zenpython, fix_service_healthcheck_path

NOVAHOST_PLUGINS = ['zenoss.cmd.linux.openstack.nova',
                    'zenoss.cmd.linux.openstack.libvirt',
                    'zenoss.cmd.linux.openstack.inifiles',
                    'zenoss.cmd.linux.openstack.hostfqdn',
                    ]

try:
    import servicemigration as sm
    from Products.ZenModel.ZenPack import DirectoryConfigContents
    sm.require("1.0.0")
    VERSION5 = True
except ImportError:
    VERSION5 = False


class ZenPack(schema.ZenPack):
    UNINSTALLING = False

    # zenpacklib doesn't yet support all zProperty metadata.
    packZProperties_data = {
        'zOpenStackExtraHosts': {
            'label': 'Extra OpenStack Hosts',
            'description':
                'The list of extra hosts that will be added to the system '
                'once OpenStack Infrastructure device is modeled.',
            'type': 'lines'
        },
        'zOpenStackHostDeviceClass': {
            'label': 'Device Class For OpenStack Linux Hosts',
            'description':
                'Used as a default device class for defined hosts in '
                'zOpenStackExtraHosts and zOpenStackNovaApiHosts properties.',
            'type': 'string'
        },
        'zOpenStackNovaApiHosts': {
            'label': 'Hosts where nova-api is running',
            'description':
                'List of hosts upon which nova-api runs. This is required '
                'when the IP address in the nova API url does not match any '
                'known host.',
            'type': 'lines'
        },
        'zOpenStackCinderApiHosts': {
            'label': 'Hosts where cinder-api is running',
            'description':
                'List of hosts upon which cinder-api runs. This is required '
                'when the IP address in the cinder API url does not match any '
                'known host.',
            'type': 'lines'
        },
        'zOpenStackExtraApiEndpoints': {
            'label': 'Additional OpenStack API endpoints to monitor',
            'description':
                'List of additional API endpoints to monitor. The format '
                'of each line is [service type]:[url]',
            'type': 'lines'
        },
        'zOpenStackHostMapToId': {
            'label': 'Hostname to ID Mapping Override',
            'description':
                'List of <name>=<id>, used to force a host referred to by '
                ' openstack with the given name to be represented in Zenoss '
                ' as a host component with the given ID. (this is not commonly '
                ' used)',
            'type': 'lines'
        },
        'zOpenStackHostMapSame': {
            'label': 'Hostname to Hostname Mapping',
            'description':
                'A list of <name1>=<name2>, used to inform the modeler '
                'that the same host may be referred to with an alternate '
                'name by some part of openstack. (this is not commonly used)',
            'type': 'lines'
        },
        'zOpenStackNeutronConfigDir': {
            'label': 'Neutron Config File Directory',
            'description':
                'Path to directory that contains Neutron configuration files.',
            'type': 'string'
        },
        'zOpenStackRunNovaManageInContainer': {
            'label': 'Nova-Manage Docker Container Pattern',
            'description':
                'Used when openstack processes are running inside of docker '
                'containers. Provide the container names (or a pattern to match '
                'them) here, or leave blank in a non-containerized openstack '
                'environment.',
            'type': 'string'
        },
        'zOpenStackRunVirshQemuInContainer': {
            'label': 'Libvirt Docker Container Pattern',
            'description':
                'Used when openstack processes are running inside of docker '
                'containers. Provide the container names (or a pattern to match '
                'them) here, or leave blank in a non-containerized openstack '
                'environment.',
            'type': 'string'
        },
        'zOpenStackRunNeutronCommonInContainer': {
            'label': 'Neutron Common Docker Container Pattern',
            'description':
                'Used when openstack processes are running inside of docker '
                'containers. Provide the container names (or a pattern to match '
                'them) here, or leave blank in a non-containerized openstack '
                'environment.',
            'type': 'string'
        },
        'zOpenStackAMQPUsername':  {
            'label': '',
            'description': '',
            'type': 'string'
        },
        'zOpenStackAMQPPassword': {
            'label': '',
            'description': '',
            'type': 'password'
        }
    }

    def install(self, app):
        self._migrate_productversions()
        self._update_plugins('/Server/SSH/Linux/NovaHost')
        super(ZenPack, self).install(app)
        install_migrate_zenpython()
        if VERSION5:
            try:
                ctx = sm.ServiceContext()
            except sm.ServiceMigrationError:
                log.info("Couldn't generate service context, skipping.")
                return
            rabbitmq_ceil = filter(lambda s: s.name == "RabbitMQ-Ceilometer", ctx.services)
            if not rabbitmq_ceil:
                # from line 1278 of ZenPack.py
                log.info("Loading RabbitMQ-Ceilometer service definition during upgrade")
                sdFiles = self.getServiceDefinitionFiles()
                toConfigPath = lambda x: os.path.join(os.path.dirname(x), '-CONFIGS-')
                configFileMaps = [DirectoryConfigContents(toConfigPath(i)) for i in sdFiles]
                self.installServicesFromFiles(sdFiles, configFileMaps, self.getServiceTag())

            # Fix zenpack-provided healthcheck file paths (since the zenpack's)
            # directory may change during install/upgrade
            fix_service_healthcheck_path()
        self.chmodScripts()

    def _update_plugins(self, organizer):
        log.debug('Update plugins list for NovaHost organizer')
        self.device_classes[organizer].zProperties['zCollectorPlugins'] = NOVAHOST_PLUGINS
        try:
            plugins = self.dmd.Devices.getOrganizer('/Server/SSH/Linux').zCollectorPlugins
            self.device_classes[organizer].zProperties['zCollectorPlugins'] += plugins
        except KeyError:
            log.debug("'Server/SSH/Linux' organizer does not exist")

    def _migrate_productversions(self):
        # Rename products for openstack versions which did not yet have names
        # in previous versions of the zenpack.   This can not be done in a
        # traditional migrate script because it needs to happen before
        # objects.xml is loaded.
        rename_versions = {
            "2015.2": "Liberty (2015.2)"
        }
        try:
            os_products = self.dmd.getObjByPath("Manufacturers/OpenStack/products")
        except KeyError:
            # First time installing the zenpack.. no prior versions in there.
            pass
        else:
            for old_version, new_version in rename_versions.iteritems():
                if old_version in os_products.objectIds():
                    try:
                        os_products.manage_renameObject(old_version, new_version)
                        log.debug("Migrated version '%s' to '%s'" % (old_version, new_version))
                    except CopyError:
                        raise Exception("Version '%s' is invalid or already in use." % new_version)

    def remove(self, app, leaveObjects=False):
        try:
            ZenPack.UNINSTALLING = True
            super(ZenPack, self).remove(app, leaveObjects=leaveObjects)
        finally:
            ZenPack.UNINSTALLING = False

        remove_migrate_zenpython()

    def chmodScripts(self):
        for script in ('poll_openstack.py',
                       'openstack_amqp_init.py',
                       'openstack_helper.py'):
            os.system('chmod 0755 {0}'.format(self.path(script)))

# Patch last to avoid import recursion problems.
from ZenPacks.zenoss.OpenStackInfrastructure import patches
unused(patches)
