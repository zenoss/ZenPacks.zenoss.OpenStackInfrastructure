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

    def load_device(self, dmd, title, authUrl, username, apiKey):
        return getFacade('cloudfoundry', dmd).addOpenStack(
            title, authUrl, username, apiKey)

