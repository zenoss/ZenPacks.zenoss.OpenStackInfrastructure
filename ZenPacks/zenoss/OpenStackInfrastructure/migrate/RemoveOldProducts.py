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

# in previous versions of the zenpack, these products were created, but
# they are no longer needed.

remove_products = [
    '2016.1',
    '2016.2',
    '2017.1',
    '2017.2',
    'Newton (2016.2)',
    'Newton (2017.1)',
    'Ocata (2017.1)'
]


class RemoveOldProducts(ZenPackMigration):
    version = Version(2, 4, 0)

    def migrate(self, pack):
        dmd = pack.dmd

        count = 0
        current_products = dmd.Manufacturers.OpenStack.products.objectIds()
        for product in remove_products:
            if product in current_products:
                dmd.Manufacturers.OpenStack.manage_deleteProducts(ids=[product])
                count += 1

        if count:
            log.info("Removed %d obsolete product objects", count)

RemoveOldProducts()
