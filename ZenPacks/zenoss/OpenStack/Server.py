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

from Products.ZenModel.DeviceComponent import DeviceComponent
from Products.ZenModel.ManagedEntity import ManagedEntity
from Products.ZenModel.ZenossSecurity import ZEN_CHANGE_DEVICE
from Products.ZenRelations.RelSchema import ToMany, ToManyCont, ToOne

class Server(DeviceComponent, ManagedEntity):
    meta_type = portal_type = "OpenStackServer"

    serverId = None             # 847424
    serverStatus = None         # ACTIVE
    serverBackupEnabled = None  # False
    serverBackupDaily = None    # DISABLED
    serverBackupWeekly = None   # DISABLED
    publicIp = None             # 50.57.74.222
    privateIp = None            # 10.182.13.13
    hostId = None               # a84303c0021aa53c7e749cbbbfac265f

    _properties = ManagedEntity._properties + (
        {'id': 'serverId', 'type': 'int', 'mode': ''},
        {'id': 'serverStatus', 'type': 'string', 'mode': ''},
        {'id': 'serverBackupEnabled', 'type': 'boolean', 'mode': ''},
        {'id': 'serverBackupDaily', 'type': 'string', 'mode': ''},
        {'id': 'serverBackupWeekly', 'type': 'string', 'mode': ''},
        {'id': 'publicIp', 'type': 'string', 'mode': ''},
        {'id': 'privateIp', 'type': 'string', 'mode': ''},
        {'id': 'hostId', 'type': 'string', 'mode': ''},
    )

    _relations = ManagedEntity._relations + (
        ('endpoint', ToOne(ToManyCont,
            'ZenPacks.zenoss.OpenStack.Endpoint.Endpoint',
            'images',
            ),
        ),
        ('flavor', ToOne(ToMany,
            'ZenPacks.zenoss.OpenStack.Flavor.Flavor',
            'servers',
            ),
        ),
        ('image', ToOne(ToMany,
            'ZenPacks.zenoss.OpenStack.Image.Image',
            'servers',
            ),
        ),
    )

    factory_type_information = ({
        'actions': ({ 
            'id': 'perfConf', 
            'name': 'Template', 
            'action': 'objTemplates', 
            'permissions': (ZEN_CHANGE_DEVICE,), 
        },), 
    },)

    # Query for events by id instead of name.
    event_key = "ComponentId"

    def device(self):
        return self.endpoint()

    def setFlavorId(self, flavorId):
        for flavor in self.endpoint.flavors():
            if flavorId == flavor.flavorId:
                self.flavor.addRelation(flavor)

    def getFlavorId(self):
        if self.flavor():
            return self.flavor().flavorId

        return None

    def setImageId(self, imageId):
        for image in self.endpoint.images():
            if imageId == image.imageId:
                self.image.addRelation(image)

    def getImageId(self):
        if self.image():
            return self.image().imageId

        return None

    def getGuestDevice(self):
        if self.publicIp:
            device = self.dmd.Devices.findDeviceByIdOrIp(self.publicIp)
            if device:
                return device

            ip = self.dmd.Networks.findIp(self.publicIp)
            return ip.device()

        return None

    def getDefaultGraphDefs(self, drange=None):
        """
        Currently no metrics are collected directly from servers. Pull in the
        graphs from the associated guest device if it is known.
        """
        graphs = []

        guestDevice = self.getGuestDevice()
        if guestDevice:
            for guest_graph in guestDevice.getDefaultGraphDefs(drange):
                graphs.append(dict(
                    title='{0} (Guest Device)'.format(guest_graph['title']),
                    url=guest_graph['url']))

        return graphs

