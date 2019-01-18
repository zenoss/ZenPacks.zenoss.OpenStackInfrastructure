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
            '/OpenStack/Cinder/Snapshot/instances/Cinder Snapshot default mapping',

            '/OpenStack/instances/compute.metrics.update',
            '/OpenStack/compute/instance/instances/compute.instance.create.end',
            '/OpenStack/compute/instance/instances/compute.instance.create.start',
            '/OpenStack/compute/instance/instances/compute.instance.delete.end',
            '/OpenStack/compute/instance/instances/compute.instance.finish_resize.end',
            '/OpenStack/compute/instance/instances/compute.instance.live_migration._post.end',
            '/OpenStack/compute/instance/instances/compute.instance.power_on.end',
            '/OpenStack/compute/instance/instances/compute.instance.reboot.end',
            '/OpenStack/compute/instance/instances/compute.instance.reboot.start',
            '/OpenStack/compute/instance/instances/compute.instance.rebuild.end',
            '/OpenStack/compute/instance/instances/compute.instance.rebuild.start',
            '/OpenStack/compute/instance/instances/compute.instance.rescue.end',
            '/OpenStack/compute/instance/instances/compute.instance.resize.end',
            '/OpenStack/compute/instance/instances/compute.instance.resize.revert.end',
            '/OpenStack/compute/instance/instances/compute.instance.resume',
            '/OpenStack/compute/instance/instances/compute.instance.shutdown.end',
            '/OpenStack/compute/instance/instances/compute.instance.shutdown.start',
            '/OpenStack/compute/instance/instances/compute.instance.suspend',
            '/OpenStack/compute/instance/instances/compute.instance.unrescue.end',
            '/OpenStack/compute/instance/instances/compute.instance.update',
            '/OpenStack/floatingip/instances/floatingip.create.end',
            '/OpenStack/floatingip/instances/floatingip.delete.end',
            '/OpenStack/floatingip/instances/floatingip.update.end',
            '/OpenStack/floatingip/instances/floatingip.update.start',
            '/OpenStack/network/instances/network defaultmapping',
            '/OpenStack/network/instances/network.create.end',
            '/OpenStack/network/instances/network.delete.end',
            '/OpenStack/network/instances/network.update.end',
            '/OpenStack/port/instances/port.create.end',
            '/OpenStack/port/instances/port.delete.end',
            '/OpenStack/port/instances/port.update.end',
            '/OpenStack/router/instances/router.create.end',
            '/OpenStack/router/instances/router.delete.end',
            '/OpenStack/router/instances/router.update.end',
            '/OpenStack/subnet/instances/subnet.create.end',
            '/OpenStack/subnet/instances/subnet.delete.end',
            '/OpenStack/subnet/instances/subnet.update.end',
            '/OpenStack/Cinder/Volume/instances/volume.attach.end',
            '/OpenStack/Cinder/Volume/instances/volume.create.end',
            '/OpenStack/Cinder/Volume/instances/volume.delete.end',
            '/OpenStack/Cinder/Volume/instances/volume.detach.end',
            '/OpenStack/Cinder/Volume/instances/volume.update.end',
            '/OpenStack/Cinder/Snapshot/instances/snapshot.create.end',
            '/OpenStack/Cinder/Snapshot/instances/snapshot.delete.end'
        ]

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
