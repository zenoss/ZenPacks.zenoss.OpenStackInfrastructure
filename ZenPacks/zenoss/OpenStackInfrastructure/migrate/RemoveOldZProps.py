##############################################################################
#
# Copyright (C) Zenoss, Inc. 2017, all rights reserved.
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

# in previous versions of the zenpack, these zproperties were created, but
# they are no longer needed.

remove_zproperties = [
    'zOpenStackCeilometerUrl'
]


class RemoveOldZProps(ZenPackMigration):
    version = Version(2, 4, 0)

    def migrate(self, pack):
        dmd = pack.dmd

        count = 0
        for prop in remove_zproperties:
            if dmd.Devices.hasProperty(prop):
                dmd.Devices._delProperty(prop)
                count += 1

        if count == 1:
            log.info("Removed %d obsolete zProperty", count)
        elif count:
            log.info("Removed %d obsolete zProperties", count)

RemoveOldZProps()
