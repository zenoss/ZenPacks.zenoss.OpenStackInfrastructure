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

from urlparse import urlparse

from zope.interface import implements

from Products.Zuul.facades import ZuulFacade
from Products.Zuul.utils import ZuulMessageFactory as _t

from ZenPacks.zenoss.OpenStack.interfaces import IOpenStackFacade

OPENSTACK_DEVICE_PATH = "/Devices/OpenStack"


class OpenStackFacade(ZuulFacade):
    implements(IOpenStackFacade)

    def addOpenStack(self, username, api_key, project_id, auth_url, api_version, 
                     region_name=None, collector='localhost'):
        """Add a new OpenStack endpoint to the system."""
        parsed_url = urlparse(auth_url)
        hostname = parsed_url.hostname

        # Verify that this device does not already exist.
        deviceRoot = self._dmd.getDmdRoot("Devices")
        device = deviceRoot.findDeviceByIdExact(hostname)
        if device:
            return False, _t("A device named %s already exists." % hostname)

        zProperties = {
            'zCommandUsername': username,
            'zCommandPassword': api_key,
            'zOpenStackProjectId': project_id,
            'zOpenStackAuthUrl': auth_url,
            'zOpenstackComputeApiVersion': api_version,
            'zOpenStackRegionName': region_name or '',
            }

        perfConf = self._dmd.Monitors.getPerformanceMonitor('localhost')
        jobStatus = perfConf.addDeviceCreationJob(
            deviceName=hostname,
            devicePath=OPENSTACK_DEVICE_PATH,
            discoverProto='python',
            performanceMonitor=collector,
            zProperties=zProperties)

        return True, jobStatus.id
