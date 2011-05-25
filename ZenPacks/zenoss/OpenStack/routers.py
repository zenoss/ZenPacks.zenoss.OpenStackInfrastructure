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

from Products.ZenUtils.Ext import DirectRouter, DirectResponse
from Products import Zuul

class OpenStackRouter(DirectRouter):
    def _getFacade(self):
        return Zuul.getFacade('openstack', self.context)

    def addOpenStack(self, title, authUrl, username, apiKey):
        facade = self._getFacade()
        success, message = facade.addOpenStack(
            title, authUrl, username, apiKey)
        
        if success:
            return DirectResponse.succeed(jobId=message)
        else:
            return DirectResponse.fail(message)

