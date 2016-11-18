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

#------------------------------------------------------------------------------
# Load Yaml here
#------------------------------------------------------------------------------
CFG = zenpacklib.load_yaml()

#------------------------------------------------------------------------------
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
    def install(self, app):
        self._migrate_productversions()
        self._update_plugins('/Server/SSH/Linux/NovaHost')
        self._update_properties()
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

    def _update_properties(self):
        # ZEN-23536: Update zOpenStackNeutronConfigDir property type
        # for existing /Server/SSH/Linux/NovaHost device class.
        try:
            self.dmd.Devices.Server.SSH.Linux.NovaHost._updateProperty(
                'zOpenStackNeutronConfigDir', '/etc/neutron')
        except AttributeError:
            pass

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
        super(ZenPack, self).remove(app, leaveObjects=leaveObjects)
        remove_migrate_zenpython()

    def chmodScripts(self):
        for script in ('poll_openstack.py',
                       'openstack_amqp_init.py',
                       'openstack_helper.py'):
            os.system('chmod 0755 {0}'.format(self.path(script)))

# Patch last to avoid import recursion problems.
from ZenPacks.zenoss.OpenStackInfrastructure import patches
unused(patches)
