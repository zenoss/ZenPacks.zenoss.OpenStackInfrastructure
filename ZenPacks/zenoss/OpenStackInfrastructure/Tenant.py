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

        impacted_list = []
        dev = self.device()
        t_types = ('OpenStackInfrastructureInstance',
                   'OpenStackInfrastructureNetwork',
                   'OpenStackInfrastructureSubnet',
                   )

        # Build raw list of all components first
        comps = []
        for t in t_types:
            comps.extend(dev.getDeviceComponents(type=t))

        # Filter the raw list
        impacted_list = [c for c in comps
                         if hasattr(c, 'tenant')
                         if c.tenant()
                         if self.id == c.tenant().id
                         ]

        return impacted_list
