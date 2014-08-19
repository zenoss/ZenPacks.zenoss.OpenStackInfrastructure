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

import logging
log = logging.getLogger('zen.OpenStackLoader')

from zope.interface import implements

from Products.Zuul import getFacade
from Products.ZenModel.interfaces import IDeviceLoader


class OpenStackLoader(object):
    """
    Loader for the OpenStack ZenPack.
    """
    implements(IDeviceLoader)

    def load_device(self, dmd, username, api_key, project_id, auth_url,
                    region_name=None, collector='localhost'):

        return getFacade('openstack', dmd).addOpenStack(
            username, api_key, project_id, auth_url,
            region_name=region_name, collector=collector)
