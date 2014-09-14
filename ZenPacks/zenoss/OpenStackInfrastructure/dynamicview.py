###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2014, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

from zope.component import adapts

from Products.ZenModel.Device import Device

from ZenPacks.zenoss.DynamicView import TAG_IMPACTED_BY, TAG_IMPACTS, TAG_ALL
from ZenPacks.zenoss.DynamicView.model.adapters import BaseRelatable
from ZenPacks.zenoss.DynamicView.model.adapters import DeviceComponentRelatable
from ZenPacks.zenoss.DynamicView.model.adapters import BaseRelationsProvider

from ZenPacks.zenoss.OpenStack.Endpoint import Endpoint
from ZenPacks.zenoss.OpenStack.Region import Region
from ZenPacks.zenoss.OpenStack.AvailabilityZone import AvailabilityZone
from ZenPacks.zenoss.OpenStack.Cell import Cell
from ZenPacks.zenoss.OpenStack.SoftwareComponent import SoftwareComponent
from ZenPacks.zenoss.OpenStack.Host import Host

TAG_CLOUD = 'openstack_link'


class EndpointRelatable(BaseRelatable):
    adapts(Region)

    group = 'Region'


class EndpointRelationsProvider(BaseRelationsProvider):
    adapts(Endpoint)

    def relations(self, type=TAG_ALL):
        for region in [x for x in self._adapted.components()
                       if x.meta_type == 'OpenStackRegion']:
            yield self.constructRelationTo(region, TAG_CLOUD)


class RegionRelatable(BaseRelatable):
    adapts(Region)

    group = 'Region'


class RegionRelationsProvider(BaseRelationsProvider):
    adapts(Region)

    def relations(self, type=TAG_ALL):
        if type in (TAG_ALL, TAG_CLOUD):
            # yield self.constructRelationTo(self._adapted.device(), TAG_IMPACTS)

            for zone in self._adapted.childOrgs():
                yield self.constructRelationTo(zone, TAG_CLOUD)

            for software in self._adapted.softwareComponents():
                yield self.constructRelationTo(software, TAG_CLOUD)



class AvailabilityZoneRelatable(BaseRelatable):
    adapts(AvailabilityZone)

    group = 'Availability Zones'


class AvailabilityZoneRelationsProvider(BaseRelationsProvider):
    adapts(AvailabilityZone)

    def relations(self, type=TAG_ALL):
        if type in (TAG_ALL, TAG_CLOUD):
            for childOrg in self._adapted.childOrgs():
                yield self.constructRelationTo(childOrg, TAG_CLOUD)

            for software in self._adapted.softwareComponents():
                yield self.constructRelationTo(software, TAG_CLOUD)

            for host in self._adapted.hosts():
                yield self.constructRelationTo(host, TAG_CLOUD)


class CellRelatable(BaseRelatable):
    adapts(Cell)

    group = 'Nova Cells'


class CellRelationsProvider(BaseRelationsProvider):
    adapts(Cell)

    def relations(self, type=TAG_ALL):
        if type in (TAG_ALL, TAG_CLOUD):
            for childOrg in self._adapted.childOrgs():
                yield self.constructRelationTo(childOrg, TAG_CLOUD)

            for software in self._adapted.softwareComponents():
                yield self.constructRelationTo(software, TAG_CLOUD)

            for host in self._adapted.hosts():
                yield self.constructRelationTo(host, TAG_CLOUD)


class SoftwareComponentRelatable(BaseRelatable):
    adapts(SoftwareComponent)

    group = 'Services'


class SoftwareComponentRelationsProvider(BaseRelationsProvider):
    adapts(SoftwareComponent)

    def relations(self, type=TAG_ALL):
        if type in (TAG_ALL, TAG_CLOUD):
            yield self.constructRelationTo(self._adapted.orgComponent(), TAG_CLOUD)


class HostRelatable(BaseRelatable):
    adapts(Host)

    group = 'Hosts'


class HostRelationsProvider(BaseRelationsProvider):
    adapts(Host)

    def relations(self, type=TAG_ALL):
        if type in (TAG_ALL, TAG_CLOUD):
            for software in self._adapted.hostedSoftware():
                yield self.constructRelationTo(software, TAG_CLOUD)                