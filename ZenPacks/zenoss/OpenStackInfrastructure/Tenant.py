##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013-2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


from . import schema

import logging
LOG = logging.getLogger('zen.OpenStackInfrastructureTenant')

class Tenant(schema.Tenant):

    def tenant_impacted_by(self):
        comps = []
        comps = self.getDeviceComponents(type="OpenStackInfrastructureInstance")
        comps += self.getDeviceComponents(type="OpenStackInfrastructureNetwork")
        comps += self.getDeviceComponents(type="OpenStackInfrastructureSubnet")
        return comps
