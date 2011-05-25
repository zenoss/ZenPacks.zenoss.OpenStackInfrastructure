###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2011, Zenoss Inc.
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

class endpoint(CommandParser):
    def processResults(self, cmd, result):
        data = json.loads(cmd.result.output)
        dp_map = dict([(dp.id, dp) for dp in cmd.points])

        for name, dp in dp_map.items():
            if name in data:
                result.values.append((dp, data[name]))

        if 'events' in data:
            for event in data['events']:
                # Keys must be converted from unicode to str.
                event = dict((str(k), v) for k, v in event.iteritems())
                result.events.append(event)

