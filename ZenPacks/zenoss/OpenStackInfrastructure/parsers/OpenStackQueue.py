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
        entries = json.loads(cmd.result.output)
        dp_map = dict([(dp.id, dp) for dp in cmd.points])
        for name, dp in dp_map.items():
            # looking for 'event' and 'perf'
            clue = name[:name.find('QueueCount')]
            for entry in entries:
                if entry[0].find(clue) > -1:
                    result.values.append((dp, entry[1]))
                    break
