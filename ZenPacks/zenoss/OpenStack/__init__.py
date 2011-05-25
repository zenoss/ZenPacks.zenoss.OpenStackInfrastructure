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

import logging
log = logging.getLogger('zen.OpenStack')

import os

from Products.ZenModel.ZenPack import ZenPack as ZenPackBase
from Products.ZenUtils.Utils import zenPath

class ZenPack(ZenPackBase):
    packZProperties = [
        ('zOpenStackAuthUrl', '', 'string'),
    ]

    def install(self, app):
        super(ZenPack, self).install(app)
        self.symlinkPlugin()

    def remove(self, app, leaveObjects=False):
        if not leaveObjects:
            self.removePluginSymlink()

        super(ZenPack, self).remove(app, leaveObjects=leaveObjects)

    def symlinkPlugin(self):
        log.info('Linking poll_openstack.py plugin into $ZENHOME/libexec/')
        os.system('ln -sf {0} {1}'.format(
            self.path('poll_openstack.py'),
            zenPath('libexec', 'poll_openstack.py')))

    def removePluginSymlink(self):
        log.info('Removing poll_openstack.py link from $ZENHOME/libexec/')
        os.system('rm -f {0}'.format(zenPath('libexec', 'poll_openstack.py')))

