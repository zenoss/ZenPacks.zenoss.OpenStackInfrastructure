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

from Products.ZenModel.Device import Device
from Products.ZenRelations.RelSchema import ToManyCont, ToOne

class Endpoint(Device):
    meta_type = portal_type = 'OpenStackEndpoint'

    _relations = Device._relations + (
        ('flavors', ToManyCont(ToOne,
            'ZenPacks.zenoss.OpenStack.Flavor.Flavor',
            'endpoint',
            ),
        ),
        ('images', ToManyCont(ToOne,
            'ZenPacks.zenoss.OpenStack.Image.Image',
            'endpoint',
            ),
        ),
        ('servers', ToManyCont(ToOne,
            'ZenPacks.zenoss.OpenStack.Server.Server',
            'endpoint',
            ),
        ),
    )

