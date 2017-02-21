##############################################################################
#
# Copyright (C) Zenoss, Inc. 2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


from . import schema

import logging
log = logging.getLogger('zen.OpenStackInfrastructureApiEndpoint')

from Products.AdvancedQuery import Eq, Or


class ApiEndpoint(schema.ApiEndpoint):

    def region_if_public_keystone(self):
        # if this is the public-facing api endpoint, it impacts the region.
        if self.id == 'apiendpoint-zOpenStackAuthUrl':
            try:
                return self.device().getDeviceComponents(type='OpenStackInfrastructureRegion')[0]
            except IndexError:
                return None
