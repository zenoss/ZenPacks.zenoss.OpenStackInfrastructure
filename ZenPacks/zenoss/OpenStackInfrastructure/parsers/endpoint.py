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

import logging
LOG = logging.getLogger('zen.OpenStackInfrastructure.parsers.%s' % __name__)

import json
from Products.ZenRRD.CommandParser import CommandParser


class endpoint(CommandParser):
    def processResults(self, cmd, result):

        try:
            data = json.loads(cmd.result.output)
        except ValueError:
            LOG.error("Invalid JSON: cmd.result.output: %s", cmd.result.output)
            return

        dp_map = dict([(dp.id, dp) for dp in cmd.points])

        for name, dp in dp_map.items():
            if name in data:
                result.values.append((dp, data[name]))

        if 'events' in data:
            for event in data['events']:
                # Keys must be converted from unicode to str.
                event = dict((str(k), v) for k, v in event.iteritems())
                result.events.append(event)
