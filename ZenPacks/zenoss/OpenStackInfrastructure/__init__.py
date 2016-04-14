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
NOVA_HOST_PLUGINS = ['zenoss.cmd.linux.openstack.nova',
                     'zenoss.cmd.linux.openstack.libvirt',
                     'zenoss.cmd.linux.openstack.inifiles']

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


class ZenPack(schema.ZenPack):
    def install(self, app):
        self._migrate_productversions()
        self._update_plugins()

        super(ZenPack, self).install(app)
        self.chmodScripts()

    def _update_plugins(self):
        log.info('Setting zProperty zCollectorPlugins on /Server/SSH/Linux/NovaHost')
        plugins=self.dmd.Devices.getOrganizer('/Server/SSH/Linux').zCollectorPlugins
        novahost = self.dmd.Devices.getOrganizer('/Server/SSH/Linux/NovaHost')
        novahost.zCollectorPlugins = plugins + NOVA_HOST_PLUGINS

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

    def chmodScripts(self):
        for script in ('poll_openstack.py',
                       'openstack_amqp_init.py',
                       'openstack_helper.py'):
            os.system('chmod 0755 {0}'.format(self.path(script)))

# Patch last to avoid import recursion problems.
from ZenPacks.zenoss.OpenStackInfrastructure import patches
unused(patches)
