###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2014-2018, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

""" Get OpenStack host FQDN """

from Products.DataCollector.plugins.DataMaps import ObjectMap

from Products.DataCollector.plugins.CollectorPlugin import CommandPlugin
from ZenPacks.zenoss.OpenStackInfrastructure.utils import add_local_lib_path
add_local_lib_path()

import re

import logging
LOG = logging.getLogger('zen.OpenStack.hostfqdn')


def command_from_commands(*commands):
    """Return a single command given an iterable of commands.

    The results of each command will be separated by __SPLIT__, and the
    results will contain only the commands' stdout.

    """
    return " ; echo __SPLIT__ ; ".join("{} 2>/dev/null".format(c) for c in commands)


def results_from_result(result):
    """Return results split into a list of per-command output."""
    try:
        return [r.strip() for r in result.split("__SPLIT__")]
    except Exception:
        return []


class hostfqdn(CommandPlugin):

    command = command_from_commands(
        "/bin/hostname",
        "/bin/hostname -f",
        "/bin/dnsdomainname"
    )

    def process(self, device, results, log):
        log.info("Modeler %s processing data for device %s",
                 self.name(), device.id)

        results = results_from_result(results)

        if len(results) != 3:
            LOG.error("Unable to process results.  Expected 3 results, but got %d (%s)", len(results), results)
            return []

        hostname, hostname_f, dnsdomainname = results

        # the FQDN could be either "hostname -f", or "hostname" + "dnsdomainname"
        fqdn = hostname_f
        if "." not in hostname and len(dnsdomainname) > 0:
            merged_fqdn = hostname + '.' + dnsdomainname
        else:
            merged_fqdn = ""

        # pick the longer of the two
        if len(merged_fqdn) > len(fqdn):
            fqdn = merged_fqdn

        hostfqdn_om = ObjectMap({
            'hostfqdn': fqdn,
            'hostlocalname': hostname
        })

        LOG.info("Hostname: %s (%s)", hostname, fqdn)

        return [ObjectMap({
            'setApplyDataMapToOpenStackInfrastructureHost': hostfqdn_om
        })]
