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

import json

from Products.ZenRRD.CommandParser import CommandParser


class OpenStackQueue(CommandParser):
    def processResults(self, cmd, result):
        qInfo = json.loads(cmd.result.output)
        deviceName = cmd.deviceConfig.name or cmd.deviceConfig.id
        dp_map = dict([(dp.id, dp) for dp in cmd.points])
        for name, dp in dp_map.items():
            clue = name[:name.index('QueueCount')]
            [result.values.append((dp, item[1])) for item in qInfo \
                 if item[0].find('openstack') > -1 and \
                     item[0].find(deviceName) > -1 and \
                     item[0].find(clue) > -1]