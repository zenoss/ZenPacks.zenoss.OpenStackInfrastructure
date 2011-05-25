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

    def addOpenStack(self, hostname, authUrl, username, apiKey):
        """
        Handles adding a new OpenStack endpoint to the system.
        """
        # Verify that this device does not already exist.
        deviceRoot = self._dmd.getDmdRoot("Devices")
        device = deviceRoot.findDeviceByIdExact(hostname)
        if device:
            return False, _t("A device named %s already exists." % hostname)

        zProperties = {
            'zOpenStackAuthUrl': authUrl,
            'zCommandUsername': username,
            'zCommandPassword': apiKey,
            }

        perfConf = self._dmd.Monitors.getPerformanceMonitor('localhost')
        jobStatus = perfConf.addDeviceCreationJob(
            deviceName=hostname,
            devicePath=OPENSTACK_DEVICE_PATH,
            discoverProto='python',
            zProperties=zProperties)

        return True, jobStatus.id

