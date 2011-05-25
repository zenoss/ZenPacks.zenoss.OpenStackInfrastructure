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

from Products.Zuul.form import schema
from Products.Zuul.interfaces import IFacade
from Products.Zuul.interfaces import IDeviceInfo
from Products.Zuul.interfaces.component import IComponentInfo
from Products.Zuul.utils import ZuulMessageFactory as _t

class IOpenStackFacade(IFacade):
    def addEndpoint(self, target, email, password, collector):
        """
        Add OpenStack Endpoint.
        """

class IEndpointInfo(IDeviceInfo):
    authUrl = schema.Text(title=_t(u"Authentication URL"))
    username = schema.Text(title=_t(u"Username"))
    serverCount = schema.Int(title=_t(u"Total Servers"))
    flavorCount = schema.Int(title=_t(u"Total Flavors"))
    imageCount = schema.Int(title=_t(u"Total Images"))

class IFlavorInfo(IComponentInfo):
    flavorRAMString = schema.Text(title=_t(u"Flavor RAM"))
    flavorDiskString = schema.Text(title=_t(u"Flavor Disk"))
    serverCount = schema.Int(title=_t(u"Server Count"))

class IImageInfo(IComponentInfo):
    imageStatus = schema.Text(title=_t(u"Image Status"))
    imageCreated = schema.Text(title=_t(u"Image Created"))
    imageUpdated = schema.Text(title=_t(u"Image Updated"))
    serverCount = schema.Int(title=_t(u"Server Count"))

class IServerInfo(IComponentInfo):
    serverStatus = schema.Text(title=_t(u"Server Status"))
    publicIp = schema.Text(title=_t(u"Public IP"))
    privateIp = schema.Text(title=_t(u"Private IP"))
    flavor = schema.Entity(title=_t(u"Server Flavor"))
    image = schema.Entity(title=_t(u"Server Image"))
    serverBackupEnabled = schema.Bool(title=_t(u"Server Backup Enabled"))
    serverBackupDaily = schema.Text(title=_t(u"Server Backup Daily"))
    serverBackupWeekly = schema.Text(title=_t(u"Server Backup Weekly"))
    hostId = schema.Text(title=_t(u"Host ID"))
    guestDevice = schema.Entity(title=_t(u"Guest Device"))

