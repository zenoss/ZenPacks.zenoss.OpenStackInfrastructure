##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
API interfaces and default implementations.
'''

import logging
log = logging.getLogger('zen.OpenStack.api')

import json
import os.path
from urlparse import urlparse
import subprocess

from zope.event import notify
from zope.interface import implements
from ZODB.transact import transact

from Products.ZenUtils.Ext import DirectRouter, DirectResponse
from Products import Zuul
from Products.Zuul.catalog.events import IndexingEvent
from Products.Zuul.facades import ZuulFacade
from Products.Zuul.interfaces import IFacade
from Products.Zuul.utils import ZuulMessageFactory as _t
from Products.ZenUtils.Utils import zenPath

from ZenPacks.zenoss.OpenStackInfrastructure.utils import add_local_lib_path
add_local_lib_path()

OPENSTACK_DEVICE_PATH = "/Devices/OpenStack"

_helper = zenPath('libexec', 'openstack_helper.py')

class KeystoneError(Exception):
    pass


def _runcommand(cmd):
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    (stdout, stderr) = p.communicate()
    if p.returncode == 0:
        return json.loads(stdout)
    else:
        try:
            message = json.loads(stdout)['error']
        except Exception:
            message = stderr

        log.exception(subprocess.CalledProcessError(p.returncode, cmd=cmd, output=message))
        raise KeystoneError(message)


class IOpenStackInfrastructureFacade(IFacade):
    def addOpenStack(self, device_name, username, api_key, project_id, auth_url,
                     ceilometer_url, region_name=None, collector='localhost'):
        """Add OpenStack Endpoint."""

    def getRegions(self, username, api_key, project_id, auth_url):
        """Get a list of available regions, given a keystone endpoint and credentials."""

    def getCeilometerUrl(self, username, api_key, project_id, auth_url, region_name):
        """Return the first defined ceilometer URL, given a keystone endpoint,
        credentials, and a region.  May return an empty string if none is found."""


class OpenStackInfrastructureFacade(ZuulFacade):
    implements(IOpenStackInfrastructureFacade)

    def addOpenStack(self, device_name, username, api_key, project_id, auth_url,
                     ceilometer_url, region_name, collector='localhost'):
        """Add a new OpenStack endpoint to the system."""
        parsed_url = urlparse(auth_url)

        if parsed_url.scheme == "" or parsed_url.hostname is None:
            return False, _t("'%s' is not a valid URL." % auth_url)

        # Verify that this device does not already exist.
        deviceRoot = self._dmd.getDmdRoot("Devices")
        device = deviceRoot.findDeviceByIdExact(device_name)
        if device:
            return False, _t("A device named %s already exists." % device_name)

        zProperties = {
            'zCommandUsername': username,
            'zCommandPassword': api_key,
            'zOpenStackProjectId': project_id,
            'zOpenStackAuthUrl': auth_url,
            'zOpenStackInfrastructureRegionName': region_name,
            'zOpenStackCeilometerUrl': ceilometer_url
            }

        @transact
        def create_device():
            dc = self._dmd.Devices.getOrganizer(OPENSTACK_DEVICE_PATH)

            device = dc.createInstance(device_name)
            device.setPerformanceMonitor(collector)

            device.username = username
            device.password = api_key

            for prop, val in zProperties.items():
                device.setZenProperty(prop, val)

            device.index_object()
            notify(IndexingEvent(device))

        # This must be committed before the following model can be
        # scheduled.
        create_device()

        # Schedule a modeling job for the new device.
        device = deviceRoot.findDeviceByIdExact(device_name)
        device.collectDevice(setlog=False, background=True)

        return True, 'Device addition scheduled'

    def getRegions(self, username, api_key, project_id, auth_url):
        """Get a list of available regions, given a keystone endpoint and credentials."""

        cmd = [_helper, "getRegions"]
        cmd.append("--username=%s" % username)
        cmd.append("--api_key=%s" % api_key)
        cmd.append("--project_id=%s" % project_id)
        cmd.append("--auth_url=%s" % auth_url)

        return _runcommand(cmd)

    def getCeilometerUrl(self, username, api_key, project_id, auth_url, region_name):
        """Return the first defined ceilometer URL, given a keystone endpoint,
        credentials, and a region.  May return an empty string if none is found."""

        cmd = [_helper, "getCeilometerUrl"]
        cmd.append("--username=%s" % username)
        cmd.append("--api_key=%s" % api_key)
        cmd.append("--project_id=%s" % project_id)
        cmd.append("--auth_url=%s" % auth_url)
        cmd.append("--region_name=%s" % region_name)

        return _runcommand(cmd)


class OpenStackInfrastructureRouter(DirectRouter):
    def _getFacade(self):
        return Zuul.getFacade('openstackinfrastructure', self.context)

    def addOpenStack(self, device_name, username, api_key, project_id, auth_url,
                     ceilometer_url, region_name, collector='localhost'):

        facade = self._getFacade()
        success, message = facade.addOpenStack(
            device_name, username, api_key, project_id, auth_url, ceilometer_url,
            region_name=region_name, collector=collector)

        if success:
            return DirectResponse.succeed(jobId=message)
        else:
            return DirectResponse.fail(message)

    def getRegions(self, username, api_key, project_id, auth_url):
        facade = self._getFacade()

        data = facade.getRegions(username, api_key, project_id, auth_url)
        return DirectResponse(success=True, data=data)

    def getCeilometerUrl(self, username, api_key, project_id, auth_url, region_name):
        facade = self._getFacade()

        data = facade.getCeilometerUrl(username, api_key, project_id, auth_url, region_name)
        return DirectResponse(success=True, data=data)
