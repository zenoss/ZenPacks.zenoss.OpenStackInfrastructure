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


class OpenStackInfrastructureLoader(object):
    """
    Loader for the OpenStackInfrastructure ZenPack.

    Sample usage:

    /Devices/OpenStack/Infrastructure loader='openstackinfrastructure', loader_arg_keys=['deviceName', 'username', 'api_key', 'project_id', 'domain_id', 'auth_url', 'region_name', 'collector']
        ostack_test username='admin', api_key='admin_password', project_id='admin', domain_id = 'default', auth_url='http://10.1.2.3:5000/v2.0/', region_name='RegionOne'

    """
    implements(IDeviceLoader)

    def load_device(self, dmd, deviceName, username, api_key, project_id, domain_id, auth_url,
                    ceilometer_url=None, region_name=None, collector='localhost'):

        # we accept, but do not use, the ceilometer_url parameter for backwards
        # compatability reasons.

        return getFacade('openstackinfrastructure', dmd).addOpenStack(
            deviceName, username, api_key, project_id, domain_id, auth_url,
            region_name=region_name, collector=collector)
