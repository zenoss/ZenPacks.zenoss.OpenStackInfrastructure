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
log = logging.getLogger('zen.OpenStackFacade')

from zope.interface import implements

from Products.Zuul.facades import ZuulFacade
from Products.Zuul.utils import ZuulMessageFactory as _t

from .interfaces import IOpenStackFacade

OPENSTACK_DEVICE_PATH = "/Devices/OpenStack"


class OpenStackFacade(ZuulFacade):
    implements(IOpenStackFacade)

    def addOpenStack(self, title, authUrl, username, apiKey):
        """
        Handles adding a new OpenStack endpoint to the system.
        """
        # Verify that this device does not already exist.
        deviceRoot = self._dmd.getDmdRoot("Devices")
        device = deviceRoot.findDeviceByIdExact(title)
        if device:
            return False, _t("A device named %s already exists." % title)

        zProperties = {
            'zOpenStackAuthUrl': authUrl,
            'zCommandUsername': username,
            'zCommandPassword': apiKey,
            }

        perfConf = self._dmd.Monitors.getPerformanceMonitor('localhost')
        jobStatus = perfConf.addDeviceCreationJob(
            deviceName=authUrl,
            devicePath=OPENSTACK_DEVICE_PATH,
            title=title,
            discoverProto='python',
            zProperties=zProperties)

        return True, jobStatus.id

