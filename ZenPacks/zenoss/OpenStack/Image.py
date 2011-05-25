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

    imageStatus = None  # ACTIVE
    imageUpdated = None # 010-09-17T07:19:20-05:00

    _properties = ManagedEntity._properties + (
        {'id': 'imageStatus', 'type': 'string', 'mode': ''},
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

    def device(self):
        return self.endpoint()

