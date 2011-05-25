###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2011, Zenoss Inc.
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

from ..Endpoint import Endpoint
from ..Server import Server

### IRelatable Adapters

class EndpointRelatable(BaseRelatable):
    adapts(Endpoint)

    group = 'OpenStack'

class ServerRelatable(DeviceComponentRelatable):
    adapts(Server)

    group = 'VMs'

### IRelationsProvider Adapters

class EndpointRelationsProvider(BaseRelationsProvider):
    adapts(Endpoint)

    def relations(self, type=TAG_ALL):
        if type in (TAG_ALL, TAG_IMPACTS):
            for server in self._adapted.servers():
                yield self.constructRelationTo(server, TAG_IMPACTS)

class ServerRelationsProvider(BaseRelationsProvider):
    adapts(Server)

    def relations(self, type=TAG_ALL):
        if type in (TAG_ALL, TAG_IMPACTS):
            guestDevice = self._adapted.getGuestDevice()
            if guestDevice:
                yield self.constructRelationTo(guestDevice, TAG_IMPACTS)

        if type in (TAG_ALL, TAG_IMPACTED_BY):
            yield self.constructRelationTo(
                self._adapted.endpoint(), TAG_IMPACTED_BY)

class DeviceRelationsProvider(BaseRelationsProvider):
    adapts(Device)

    def relations(self, type=TAG_ALL):
        if type in (TAG_ALL, TAG_IMPACTED_BY):
            server = self._adapted.getOpenStackServer()
            if server:
                yield self.constructRelationTo(server, TAG_IMPACTED_BY)

