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

class Flavor(DeviceComponent, ManagedEntity):
    meta_type = portal_type = "OpenStackFlavor"

    flavorId = None     # 1
    flavorRAM = None    # Stored as bytes
    flavorDisk = None   # Stored as bytes

    _properties = ManagedEntity._properties + (
        {'id': 'flavorId', 'type': 'int', 'mode': ''},
        {'id': 'flavorRAM', 'type': 'int', 'mode': ''},
        {'id': 'flavorDisk', 'type': 'int', 'mode': ''},
    )

    _relations = ManagedEntity._relations + (
        ('endpoint', ToOne(ToManyCont,
            'ZenPacks.zenoss.OpenStack.Endpoint.Endpoint',
            'flavors',
            ),
        ),
        ('servers', ToMany(ToOne,
            'ZenPacks.zenoss.OpenStack.Server.Server',
            'flavor',
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

