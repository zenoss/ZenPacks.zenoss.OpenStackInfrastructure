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

from Products.DataCollector.plugins.zenoss.cmd.linux.process import process as base_process

__doc__ = """process
Linux command plugin for parsing ps command output and modeling processes for Openstack environments
"""

class process(base_process):
    modname = "ZenPacks.zenoss.OpenStack.OSProcess"

    def process(self, device, results, log):
    	rm = super(process, self).process(device, results, log)

    	if rm is None:
    		return None

    	# TODO:  If the device is a proxy for an openstack component, force the appropriate processes
    	# into this relationshipmap even if they were not found running via process discovery.

        return rm
