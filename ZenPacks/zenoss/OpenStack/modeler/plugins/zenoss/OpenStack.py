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

from ....util import addLocalLibPath
addLocalLibPath()

import novaclient

from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap

class OpenStack(PythonPlugin):
    deviceProperties = PythonPlugin.deviceProperties + (
        'zOpenStackAuthUrl',
        'zCommandUsername',
        'zCommandPassword',
    )

    def collect(self, device, unused):
        client = novaclient.OpenStack(
            device.zCommandUsername,
            device.zCommandPassword,
            device.zOpenStackAuthUrl,
        )

        results = {}

        try:
            log.info('Requesting flavors')
            results['flavors'] = client.flavors.list()
        except Exception, ex:
            raise ex

        log.info('Requesting images')
        results['images'] = client.images.list()

        log.info('Requesting servers')
        results['servers'] = client.servers.list()

        return results

    def process(self, devices, results, unused):
        flavors = []
        for flavor in results['flavors']:
            flavors.append(ObjectMap(data=dict(
                id='flavor{0}'.format(flavor.id),
                title=flavor.name, # 256 server
                flavorId=flavor.id, # 1
                flavorRAM=flavor.ram * 1024 * 1024, # 256
                flavorDisk=flavor.disk * 1024 * 1024 * 1024, # 10
            )))

        flavorsMap = RelationshipMap(
            relname='flavors',
            modname='ZenPacks.zenoss.OpenStack.Flavor',
            objmaps=flavors)

        images = []
        for image in results['images']:
            images.append(ObjectMap(data=dict(
                id='image{0}'.format(image.id),
                title=image.name, # Red Hat Enterprise Linux 5.5
                imageId=str(image.id), # 55
                imageStatus=image.status, # ACTIVE
                imageCreated=image.created, # 2010-09-17T07:19:20-05:00
                imageUpdated=image.updated, # 2010-09-17T07:19:20-05:00
            )))

        imagesMap = RelationshipMap(
            relname='images',
            modname='ZenPacks.zenoss.OpenStack.Image',
            objmaps=images)

        servers = []
        for server in results['servers']:
            servers.append(ObjectMap(data=dict(
                id='server{0}'.format(server.id),
                title=server.name, # cloudserver01
                serverId=str(server.id), # 847424
                serverStatus=server.status, # ACTIVE
                serverBackupEnabled=server.backup_schedule.enabled, # False
                serverBackupDaily=server.backup_schedule.daily, # DISABLED
                serverBackupWeekly=server.backup_schedule.weekly, # DISABLED
                publicIp=server.public_ip, # 50.57.74.222
                privateIp=server.private_ip, # 10.182.13.13
                setFlavorId=server.flavorId, # 1
                setImageId=server.imageId, # 55

                # a84303c0021aa53c7e749cbbbfac265f
                hostId=server.hostId,
            )))

        serversMap = RelationshipMap(
            relname='servers',
            modname='ZenPacks.zenoss.OpenStack.Server',
            objmaps=servers)

        return (flavorsMap, imagesMap, serversMap)

