##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging

from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration


LOG = logging.getLogger('zen.OpenStackInfrastructure.migrate.%s' % __name__)


class RemoveOldEventClassInstances(ZenPackMigration):
    
    version = Version(2, 2, 0)

    def migrate(self, dmd):
        baseCls = dmd.Events.Status
        LOG.info(
            "Removing old event class instances under %s",
            baseCls.getPrimaryDmdId())

        baseCls.removeInstances(('openStackCeilometerHeartbeat',))


RemoveOldEventClassInstances()
