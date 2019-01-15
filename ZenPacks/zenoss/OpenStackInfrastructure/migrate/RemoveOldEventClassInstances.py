##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016-2019, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging

from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration
from zExceptions import NotFound

LOG = logging.getLogger('zen.OpenStackInfrastructure.migrate.%s' % __name__)


class RemoveOldEventClassInstances(ZenPackMigration):

    version = Version(3, 0, 0)

    def migrate(self, dmd):
        mappings_to_remove = [
            '/Status/openStackCeilometerHeartbeat',
            '/OpenStack/instances/OpenStack Events Default',
            '/OpenStack/compute/instance/instances/compute.instance default mapping',
            '/OpenStack/dhcp_agent/instances/dhcp_agent defaultmapping',
            '/OpenStack/firewall/instances/firewall defaultmapping',
            '/OpenStack/firewall_policy/instances/firewall_policy defaultmapping',
            '/OpenStack/firewall_rule/instances/firewall_rule defaultmapping',
            '/OpenStack/floatingip/instances/floatingip defaultmapping',
            '/OpenStack/port/instances/port defaultmapping',
            '/OpenStack/router/instances/router defaultmapping',
            '/OpenStack/security_group/instances/security_group defaultmapping',
            '/OpenStack/security_group_rule/instances/security_group_rule defaultmapping',
            '/OpenStack/subnet/instances/subnet defaultmapping',
            '/OpenStack/Cinder/Volume/instances/cinder.volume default mapping',
            '/OpenStack/Cinder/Snapshot/instances/Cinder Snapshot default mapping']

        count = 0
        for mapping_path in mappings_to_remove:
            try:
                mapping = dmd.Events.unrestrictedTraverse(mapping_path.lstrip("/"))
            except (KeyError, NotFound):
                # mapping not found
                continue
            if mapping:
                eventClass = mapping.eventClass()
                LOG.info("Removing obsolete event class mapping: %s", mapping_path)
                try:
                    eventClass.removeInstances(mapping.id)
                    count += 1
                except Exception:
                    LOG.exception("Error removing event mapping: %s", mapping_path)

        if count:
            LOG.info("Removed %d obsolete event class mappings", count)


RemoveOldEventClassInstances()
