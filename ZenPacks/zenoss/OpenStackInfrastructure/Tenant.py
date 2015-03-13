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
        ''' Takes self (Tenant) and returns all objects it owns '''
        t_types = ('OpenStackInfrastructureInstance',
                   'OpenStackInfrastructureNetwork',
                   'OpenStackInfrastructureSubnet',
                   )

        return [x for x in self.logicalComponents() if x.meta_type in t_types]
