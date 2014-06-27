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
LOG = logging.getLogger('zen.OpenStackInstance')


class Instance(schema.Instance):

    # The host that this instance is running on (derived from the hypervisor)
    def host(self):
        try:
            return self.hypervisor().host()
        except Exception:
            return None
