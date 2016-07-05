##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################
from . import schema

import logging
LOG = logging.getLogger('zen.OpenStackInfrastructurePort')


class Port(schema.Port):

    def vnic(self):
        '''Return the vnic that corresponds to this Port'''
        if not self.instance():
            return

        for vnic in self.instance().vnics():
            if vnic.mac_address.lower() == self.mac_address.lower():
                return vnic
