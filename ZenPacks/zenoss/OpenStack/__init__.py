###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2011, 2012, Zenoss Inc.
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

import copy
import os

from Products.ZenEvents.EventManagerBase import EventManagerBase
from Products.ZenModel.Device import Device
from Products.ZenModel.ZenPack import ZenPack as ZenPackBase
from Products.ZenUtils.Utils import monkeypatch, zenPath
from Products.Zuul.interfaces import ICatalogTool


class ZenPack(ZenPackBase):
    packZProperties = [
        ('zOpenStackAuthUrl', '', 'string'),
        ('zOpenstackComputeApiVersion', '', 'string'),
        ('zOpenStackProjectId', '', 'string'),
        ('zOpenStackInsecure', False, 'boolean'),
        ('zOpenStackRegionName', '', 'string'),
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
        plugin_path = zenPath('libexec', 'poll_openstack.py')
        os.system('ln -sf {0} {1}'.format(
            self.path('poll_openstack.py'), plugin_path))
        os.system('chmod 0755 {0}'.format(plugin_path))

    def removePluginSymlink(self):
        log.info('Removing poll_openstack.py link from $ZENHOME/libexec/')
        os.system('rm -f {0}'.format(zenPath('libexec', 'poll_openstack.py')))

# We need to filter OpenStack components by id instead of name.
EventManagerBase.ComponentIdWhere = (
    "\"(device = '%s' and component = '%s')\""
    " % (me.device().getDmdKey(), me.id)")


@monkeypatch('Products.ZenModel.Device.Device')
def getOpenStackServer(self):
    device_ips = set()
    if self.manageIp:
        device_ips.add(self.manageIp)

    for iface in self.os.interfaces():
        for ip in iface.getIpAddresses():
            device_ips.add(ip.split('/')[0])

    catalog = ICatalogTool(self.dmd)
    for record in catalog.search('ZenPacks.zenoss.OpenStack.Server.Server'):
        server = record.getObject()
        server_ips = set()

        if server.publicIps:
            server_ips.update(server.publicIps)

        if server.privateIps:
            server_ips.update(server.privateIps)

        if server_ips.intersection(device_ips):
            return server

# This would be much cleaner with the new "original" method support in
# Avalon's monkeypatch decorator. For now we have to do it manually.
orig_getExpandedLinks = copy.copy(Device.getExpandedLinks.im_func)


def openstack_getExpandedLinks(self):
    links = orig_getExpandedLinks(self)
    server = self.getOpenStackServer()
    if server:
        links = '<a href="{0}">OpenStack Server {1} on {2}</a><br/>{3}' \
            .format(server.getPrimaryUrlPath(), server.titleOrId(),
                server.endpoint().titleOrId(), links)

    return links

Device.getExpandedLinks = openstack_getExpandedLinks
