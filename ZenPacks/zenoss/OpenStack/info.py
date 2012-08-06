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

from zope.component import adapts
from zope.interface import implements

from Products.ZenUtils.Utils import convToUnits
from Products.Zuul.decorators import info
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.infos.device import DeviceInfo
from Products.Zuul.infos.component import ComponentInfo

from .Endpoint import Endpoint
from .Flavor import Flavor
from .Image import Image
from .Server import Server

from .interfaces import IEndpointInfo, IFlavorInfo, IImageInfo, IServerInfo


class OpenStackComponentInfo(ComponentInfo):
    @property
    def icon(self):
        return self._object.getIconPath()


class EndpointInfo(DeviceInfo):
    implements(IEndpointInfo)
    adapts(Endpoint)

    @property
    def username(self):
        return self._object.primaryAq().zCommandUsername

    @property
    def project_id(self):
        return self._object.primaryAq().zOpenStackProjectId

    @property
    def auth_url(self):
        return self._object.primaryAq().zOpenStackAuthUrl

    @property
    def region_name(self):
        return self._object.primaryAq().zOpenStackRegionName

    @property
    def flavorCount(self):
        return self._object.flavors.countObjects()

    @property
    def imageCount(self):
        return self._object.images.countObjects()

    @property
    def serverCount(self):
        return self._object.servers.countObjects()


class FlavorInfo(OpenStackComponentInfo):
    implements(IFlavorInfo)
    adapts(Flavor)

    flavorRAM = ProxyProperty('flavorRAM')
    flavorDisk = ProxyProperty('flavorDisk')

    @property
    def flavorRAMString(self):
        return convToUnits(self._object.flavorRAM, 1024, 'B')

    @property
    def flavorDiskString(self):
        return convToUnits(self._object.flavorDisk, 1024, 'B')

    @property
    def serverCount(self):
        return self._object.servers.countObjects()


class ImageInfo(OpenStackComponentInfo):
    implements(IImageInfo)
    adapts(Image)

    imageStatus = ProxyProperty('imageStatus')
    imageCreated = ProxyProperty('imageCreated')
    imageUpdated = ProxyProperty('imageUpdated')

    @property
    def serverCount(self):
        return self._object.servers.countObjects()


class ServerInfo(OpenStackComponentInfo):
    implements(IServerInfo)
    adapts(Server)

    serverStatus = ProxyProperty('serverStatus')
    publicIps = ProxyProperty('publicIps')
    privateIps = ProxyProperty('privateIps')
    serverBackupEnabled = ProxyProperty('serverBackupEnabled')
    serverBackupDaily = ProxyProperty('serverBackupDaily')
    serverBackupWeekly = ProxyProperty('serverBackupWeekly')
    hostId = ProxyProperty('hostId')

    @property
    @info
    def flavor(self):
        return self._object.flavor()

    @property
    @info
    def image(self):
        return self._object.image()

    @property
    @info
    def guestDevice(self):
        return self._object.getGuestDevice()
