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

""" Get OpenStack Nova API version """

from Products.DataCollector.plugins.DataMaps import ObjectMap, MultiArgs

from Products.DataCollector.plugins.CollectorPlugin import CommandPlugin
from ZenPacks.zenoss.OpenStack.utils import add_local_lib_path
add_local_lib_path()

import re


class nova(CommandPlugin):

    command = "nova-manage --version 2>&1"

    def process(self, device, results, log):
        log.info("Modeler %s processing data for device %s",
                 self.name(), device.id)

        matcher = re.compile(r'^(?P<version>[\d\.]+)')

        for line in results.split('\n'):
            match = matcher.search(line)
            if match:
                version = match.group('version')
                openstack_om = ObjectMap({
                    'compname': 'os',
                    'setProductKey': MultiArgs(version, 'OpenStack')
                })

                return [ObjectMap({
                    'setApplyDataMapToOpenStackEndpoint': openstack_om
                    })]

        return []
