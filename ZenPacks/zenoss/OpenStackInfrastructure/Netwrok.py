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
LOG = logging.getLogger('zen.OpenStackInfrastructureNetwork')

class Network(schema.Network):

    def get_net_tenant_id(self):
        import pdb;pdb.set_trace()
        if self.tenant():
            return self.tenant().tenantId

    def set_net_tenant_id(self, tenant_id):
        import pdb;pdb.set_trace()
        return self.set_tenant('tenant-{0}'.format(tenant_id))
