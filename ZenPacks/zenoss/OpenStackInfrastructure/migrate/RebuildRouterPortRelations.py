##############################################################################
#
# Copyright (C) Zenoss, Inc. 2012-2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
LOG = logging.getLogger('zen.OpenStackInfrastructure.migrate.%s' % __name__)

# Zope Imports
import Globals
from Acquisition import aq_base

# Zenoss Imports
from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration
from Products.ZenRelations.RelationshipBase import RelationshipBase
from Products.ZenUtils.Utils import unused
from Products.Zuul.interfaces import ICatalogTool

# ZenPack Imports
from ZenPacks.zenoss.OpenStackInfrastructure.Router import Router
from ZenPacks.zenoss.OpenStackInfrastructure.Port import Port
from ZenPacks.zenoss.OpenStackInfrastructure.lib.progresslog import ProgressLogger

unused(Globals)

# If the migration takes longer than this interval, a running progress
# showing elapsed and estimated remaining time will be logged this
# often. The value is in seconds.
PROGRESS_LOG_INTERVAL = 10


class RebuildRouterPortRelations(ZenPackMigration):

    """Rebuilds relations on all Router and Port objects.

    This is necessary anytime new relations are added to Tenant.
    The code is generic enough to work simply by updating the version
    at which the migrate script should run. Update the version anytime
    you add a new relationship to Tenant. No other changes to this
    script are necessary.

    """

    version = Version(2, 2, 0)

    def migrate(self, pack):
        results = ICatalogTool(pack.dmd.Devices).search((Router, Port))

        LOG.info("starting: %s total devices", results.total)
        progress = ProgressLogger(
            LOG,
            prefix="progress",
            total=results.total,
            interval=PROGRESS_LOG_INTERVAL)

        objects_migrated = 0

        for brain in results:
            try:
                if self.updateRelations(brain.getObject()):
                    objects_migrated += 1
            except Exception:
                LOG.exception(
                    "error updating relationships for %s",
                    brain.id)

            progress.increment()

        LOG.info(
            "finished: %s of %s devices required migration",
            objects_migrated,
            results.total)

    def updateRelations(self, device):
        relations = None
        if isinstance(device, Port):
            relations = Port._relations
        elif isinstance(device, Router):
            relations = Router._relations
        for relname in (x[0] for x in relations):
            rel = getattr(aq_base(device), relname, None)
            if not rel or not isinstance(rel, RelationshipBase):
                device.buildRelations()
                return True

        return False
