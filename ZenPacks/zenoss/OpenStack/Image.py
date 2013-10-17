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

class Image(DeviceComponent, ManagedEntity):
    meta_type = portal_type = "OpenStackImage"

    imageId = None      # 346eeba5-a122-42f1-94e7-06cb3c53f690
    imageStatus = None  # ACTIVE
    imageCreated = None # 010-09-17T07:19:20-05:00
    imageUpdated = None # 010-09-17T07:19:20-05:00

    _properties = ManagedEntity._properties + (
        {'id': 'imageId', 'type': 'string', 'mode': ''},
        {'id': 'imageStatus', 'type': 'string', 'mode': ''},
        {'id': 'imageCreated', 'type': 'string', 'mode': ''},
        {'id': 'imageUpdated', 'type': 'string', 'mode': ''},
    )

    _relations = ManagedEntity._relations + (
        ('endpoint', ToOne(ToManyCont,
            'ZenPacks.zenoss.OpenStack.Endpoint.Endpoint',
            'images',
            ),
        ),
        ('servers', ToMany(ToOne,
            'ZenPacks.zenoss.OpenStack.Server.Server',
            'image',
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

