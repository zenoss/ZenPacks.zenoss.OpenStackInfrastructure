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

import re
import json
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

from ZenPacks.zenoss.OpenStackInfrastructure.utils import add_local_lib_path, zenpack_path
add_local_lib_path()

OPENSTACK_DEVICE_PATH = "/Devices/OpenStack/Infrastructure"

_helper = zenpack_path('openstack_helper.py')

cmd_regex = re.compile('(--api_key=)(?P<password>[\wa-zA-Z0-9_.-]+)')

def mask_arg(arg):
    match = cmd_regex.match(arg)
    if match:
        return match.group().replace(match.group('password'),'******')
    return arg

def _runcommand(cmd):
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    (stdout, stderr) = p.communicate()
    if p.returncode == 0:
        return True, json.loads(stdout)
    else:
        try:
            message = json.loads(stdout)['error']
        except Exception:
            message = stderr

        cmd = [ mask_arg(x) for x in cmd]

        log.exception(subprocess.CalledProcessError(p.returncode, cmd=cmd, output=message))
        message = 'Keystone Error Occured: ' +  message.replace('\r', '').replace('\n', '')
        log.error(message)
        return False, message

class IOpenStackInfrastructureFacade(IFacade):
    def addOpenStack(self, device_name, username, api_key, project_id, user_domain_name, project_domain_name, auth_url,
                     region_name=None, collector='localhost'):
        """Add OpenStack Endpoint."""

    def getRegions(self, username, api_key, project_id, user_domain_name, project_domain_name, auth_url):
        """Get a list of available regions, given a keystone endpoint and credentials."""


class OpenStackInfrastructureFacade(ZuulFacade):
    implements(IOpenStackInfrastructureFacade)

    def addOpenStack(self, device_name, username, api_key, project_id, user_domain_name, project_domain_name, auth_url,
                     region_name, collector='localhost'):
        """Add a new OpenStack endpoint to the system."""
        parsed_url = urlparse(auth_url.strip())

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
            'zOpenStackUserDomainName' : user_domain_name,
            'zOpenStackProjectDomainName' : project_domain_name,
            'zOpenStackAuthUrl': auth_url.strip(),
            'zOpenStackRegionName': region_name,
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

    def getRegions(self, username, api_key, project_id, user_domain_name, project_domain_name, auth_url):
        """Get a list of available regions, given a keystone endpoint and credentials."""

        cmd = [_helper, "getRegions"]
        cmd.append("--username=%s" % username)
        cmd.append("--api_key=%s" % api_key)
        cmd.append("--project_id=%s" % project_id)
        cmd.append("--user_domain_name=%s" % user_domain_name)
        cmd.append("--project_domain_name=%s" % project_domain_name)
        cmd.append("--auth_url=%s" % auth_url)

        return _runcommand(cmd)


class OpenStackInfrastructureRouter(DirectRouter):
    def _getFacade(self):
        return Zuul.getFacade('openstackinfrastructure', self.context)

    def addOpenStack(self, device_name, username, api_key, project_id, user_domain_name, project_domain_name, auth_url,
                     region_name, collector='localhost'):

        facade = self._getFacade()
        success, message = facade.addOpenStack(
            device_name, username, api_key, project_id, user_domain_name, project_domain_name, auth_url,
            region_name=region_name, collector=collector)

        if success:
            return DirectResponse.succeed(jobId=message)
        else:
            return DirectResponse.fail(message)

    def getRegions(self, username, api_key, project_id, user_domain_name, project_domain_name, auth_url):
        facade = self._getFacade()

        success, data = facade.getRegions(username, api_key, project_id, user_domain_name, project_domain_name, auth_url)
        if success:
            return DirectResponse.succeed(data=data)
        else:
            return DirectResponse.fail(data)
