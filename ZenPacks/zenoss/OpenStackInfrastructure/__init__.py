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

from ZenPacks.zenoss.ZenPackLib import zenpacklib

# Load YAML
CFG = zenpacklib.load_yaml()

import os
import logging
log = logging.getLogger('zen.OpenStack')

from Products.ZenUtils.Utils import unused
from OFS.CopySupport import CopyError

schema = CFG.zenpack_module.schema
from service_migration import remove_migrate_zenpython, force_update_configs

NOVAHOST_PLUGINS = ['zenoss.cmd.linux.openstack.nova',
                    'zenoss.cmd.linux.openstack.libvirt',
                    'zenoss.cmd.linux.openstack.inifiles',
                    'zenoss.cmd.linux.openstack.hostfqdn',
                    ]

try:
    import servicemigration as sm
    sm.require("1.0.0")
    VERSION5 = True
except ImportError:
    VERSION5 = False


class ZenPack(schema.ZenPack):
    UNINSTALLING = False

    def install(self, app):
        self._migrate_productversions()
        self._update_plugins('/Server/SSH/Linux/NovaHost')
        super(ZenPack, self).install(app)
        if VERSION5:
            # by default, services are only installed during initial zenpack
            # installs, not upgrades.   We run it every time instead, but make
            # it only process service definitions that are missing, by
            # overriding getServiceDefinitionFiles to be intelligent.
            self.installServices()
            # We ship a shell script as a "config" file- make sure that
            # the config is updated if the script has changed.
            force_update_configs(self, "proxy-zenopenstack", ["opt/zenoss/bin/proxy-zenopenstack"])

    def getServiceDefinitionFiles(self):
        # The default version of this is only called during initial installation,
        # and returns all services.   This version can be called during upgrades
        # as well, because it returns only services that are not already installed.

        try:
            ctx = sm.ServiceContext()
        except sm.ServiceMigrationError:
            log.info("Couldn't generate service context, skipping.")
            return

        svcs = set([s.name for s in ctx.services])
        files = []
        if "zenopenstack" not in svcs:
            files.append(self.path('service_definition', "zenopenstack.json"))
        if "proxy-zenopenstack" not in svcs:
            files.append(self.path('service_definition', "proxy-zenopenstack.json"))

        return files

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


# Patch last to avoid import recursion problems.
from ZenPacks.zenoss.OpenStackInfrastructure import patches
unused(patches)
