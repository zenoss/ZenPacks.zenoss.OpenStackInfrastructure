###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2014, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

from Products.DataCollector.plugins.DataMaps import ObjectMap

from Products.DataCollector.plugins.CollectorPlugin import CommandPlugin
from ZenPacks.zenoss.OpenStack.utils import add_local_lib_path
add_local_lib_path()

import re

import logging
log = logging.getLogger('zen.OpenStack.hostfqdn')


class hostfqdn(CommandPlugin):

    command = "/bin/hostname;/bin/hostname -f;/bin/dnsdomainname"

    def process(self, device, results, log):
        log.info("Modeler %s processing data for device %s",
                 self.name(), device.id)

        fqdn = ''

        matcher=re.compile(r'^(?P<fqdn>(?=^.{1,254}$)(^(?:(?!\d+\.|-)[a-zA-Z0-9_\-]{1,63}(?<!-)\.)+(?:[a-zA-Z]{2,})$))')

        lines = results.split('\n')
        # expect three lines of results plus an empty one
        if len(lines) < 4:
            return []

        hostname = lines[0]
        hostname_f = lines[1]
        dnsdomainname = lines[2]
        m1 = matcher.search(hostname)
        m2 = matcher.search(hostname_f)
        m3 = matcher.search(dnsdomainname)

        # we are looking for FQDN like 'x.y.z'
        if m1:
            fqdn = m1.group('fqdn')
        elif m2 and m2.group('fqdn') == (hostname + '.' + dnsdomainname):
            fqdn = m2.group('fqdn')
        elif hostname.find('.') < 0:     # no '.' in hostname
            fqdn = hostname + '.' + dnsdomainname

        if not fqdn:
            return []

        hostfqdn_om = ObjectMap({
            'hostfqdn': fqdn
        })

        return [ObjectMap({
            'setApplyDataMapToOpenStackHost': hostfqdn_om
            })]
