##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
API interfaces and default implementations.
'''

import logging
log = logging.getLogger('zen.OpenStackAPI')

from urlparse import urlparse

from zope.interface import implements

from Products.ZenUtils.Ext import DirectRouter, DirectResponse
from Products import Zuul
from Products.Zuul.facades import ZuulFacade
from Products.Zuul.interfaces import IFacade
from Products.Zuul.utils import ZuulMessageFactory as _t


OPENSTACK_DEVICE_PATH = "/Devices/OpenStack"


class IOpenStackFacade(IFacade):
    def addOpenStack(self, username, api_key, project_id, auth_url,
                     region_name=None, collector='localhost'):
        """Add OpenStack Endpoint."""


class OpenStackFacade(ZuulFacade):
    implements(IOpenStackFacade)

    def addOpenStack(self, username, api_key, project_id, auth_url, 
                     region_name=None, collector='localhost'):
        """Add a new OpenStack endpoint to the system."""
        parsed_url = urlparse(auth_url)

        if parsed_url.scheme == "" or parsed_url.hostname is None:
            return False, _t("'%s' is not a valid URL." % auth_url)

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


class OpenStackRouter(DirectRouter):
    def _getFacade(self):
        return Zuul.getFacade('openstack', self.context)

    def addOpenStack(self, username, api_key, project_id, auth_url,
                     region_name=None, collector='localhost'):

        facade = self._getFacade()
        success, message = facade.addOpenStack(
            username, api_key, project_id, auth_url,
            region_name=region_name, collector=collector)

        if success:
            return DirectResponse.succeed(jobId=message)
        else:
            return DirectResponse.fail(message)
