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
log = logging.getLogger('zen.OpenStackHypervisor')


class Hypervisor(schema.Hypervisor):

    def get_hostByName(self):
        if self.hostname:
            return self.hostname
        return None


    def set_hostByName(self, name):
        host = None

        if name and len(self.search('Host', hostname=name)) > 0:
            host = self.search('Host', hostname=name)[0].getObject()
            if host:
                log.info("Set host by fqdn: %s" % name)
                self.set_host(host.id)
                self.hostname = name
        elif self.host() and self.host().hostname() and \
            len(self.search('Host', hostname=self.host().hostname())) > 0:
            # try host hostname
            host = self.search('Host',
                hostname=self.host().hostname())[0].getObject()
            if host:
                log.info("Set host by hostname: %s" % self.host().hostname())
                self.set_host(host.id)
                self.hostname = self.host().hostname()
        elif self.host() and self.host().id and \
            len(self.search('Host', id=self.host().id)) > 0:
            # try one more time with host id
            host = self.search('Host',
                id=self.host().id)[0].getObject()
            if host:
                log.info("Set host by host id: %s" % self.host().id)
                self.set_host(host.id)
                self.hostname = self.host().id
        else:
            log.error("Could not set host")
