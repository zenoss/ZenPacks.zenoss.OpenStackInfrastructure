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
LOG = logging.getLogger('zen.OpenStackInfrastructureVnic')


class Vnic(schema.Vnic):

    def port(self):
        '''Return the port that corresponds to this Vnic'''
        if not self.instance():
            return

        for port in self.instance().ports():
            if port.mac_address.lower() == self.macaddress.lower():
                return port
