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
log = logging.getLogger('zen.OpenStackInfrastructureHypervisor')

from Products.AdvancedQuery import Eq, Or


class Hypervisor(schema.Hypervisor):

    def get_hostByName(self):
        if self.hostfqdn:
            return self.hostfqdn
        return None


    def set_hostByName(self, name):
        if not name:
            log.warning("Could not set host. Given name is None")
            return

        self.hostfqdn = name
        query = Or(Eq('hostname', name), Eq('hostfqdn', name))
        hosts = self.search('Host', query)
        if len(hosts) > 0:
            if len(hosts) > 1:
                log.warning(
                    "Got more than one host for hypervisor: " +
                    "%s with id: %s" % (self.title, self.id))

            host = hosts[0].getObject()
            if host:
                log.info("Set host by fqdn: %s" % name)
                self.set_host(host.id)
        elif name.find('.') > -1:
            name = name[:name.index('.')]
            query = Or(Eq('hostname', name), Eq('hostfqdn', name))
            hosts = self.search('Host', query)
            if len(hosts) > 0:
                if len(hosts) > 1:
                    log.warning(
                        "Got more than one host for hypervisor: " +
                        "%s with id: %s" (self.title, self.id))

                host = hosts[0].getObject()
                if host:
                    log.info("Set host by hostname: %s" % name)
                    self.set_host(host.id)
        else:
            log.error("Could not setup host")
