##############################################################################
#
# Copyright (C) Zenoss, Inc. 2018, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


from . import schema

class Volume(schema.Volume):

    def host(self):
        hosts = self.device().hosts()
        for host in hosts:
            if self.backend is not None and host.hostname == self.backend.split('@')[0]:
                return host
