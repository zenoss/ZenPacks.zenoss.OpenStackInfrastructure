##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016-2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


import logging
log = logging.getLogger("zen.migrate")

import Globals
from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration
from Products.ZenUtils.Utils import unused
unused(Globals)

# in previous versions of the zenpack, these zproperties had their defaults
# explicitly set at the device class level, rather than as global defaults.
#
# this would cause any changes to these values at the device class level to be
# overwritten when the zenpack was upgraded.


class DefaultZProps(ZenPackMigration):
    version = Version(2, 4, 0)

    def migrate(self, pack):
        dmd = pack.dmd

        set_default_if_none = {
            'zOpenStackNeutronConfigDir': '/etc/neutron'
        }

        remove_local_copy_if_default = {
            'Server/SSH/Linux/NovaHost': [
                'zOpenStackRunNovaManageInContainer',
                'zOpenStackRunVirshQemuInContainer',
                'zOpenStackRunNeutronCommonInContainer'
            ]
        }

        for zprop, newval in set_default_if_none.iteritems():
            if dmd.Devices.hasProperty(zprop):
                if dmd.Devices.getZ(zprop) == '':
                    log.info("Setting default of %s to %s", zprop, newval)
                    dmd.Devices.setZenProperty(zprop, newval)

        for deviceclass, zprops in remove_local_copy_if_default.iteritems():
            try:
                dc = dmd.Devices.getObjByPath(deviceclass)
            except KeyError:
                continue

            for zprop in zprops:
                if dc.hasProperty(zprop) and dc.getZ(zprop) == dmd.Devices.getZ(zprop):
                    log.info("Removing redundant default value for %s", zprop)
                    dc._delProperty(zprop)

DefaultZProps()
