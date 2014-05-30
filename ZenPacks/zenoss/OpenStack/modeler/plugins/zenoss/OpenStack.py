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

import types
from collections import defaultdict

from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
from Products.ZenUtils.Utils import prepId

from ZenPacks.zenoss.OpenStack.utils import add_local_lib_path
add_local_lib_path()

from novaclient import client as novaclient
from ceilometerapiclient import CeilometerAPIClient

class OpenStack(PythonPlugin):
    deviceProperties = PythonPlugin.deviceProperties + (
        'zCommandUsername',
        'zCommandPassword',
        'zOpenStackProjectId',
        'zOpenStackAuthUrl',
        'zOpenStackRegionName'
    )

    def collect(self, device, unused):
        region_name = None
        if device.zOpenStackRegionName:
            region_name = device.zOpenStackRegionName

        if (log.isEnabledFor(logging.DEBUG)):
            http_log_debug = True
            logging.getLogger('novaclient.client').setLevel(logging.DEBUG)
        else:
            http_log_debug = False

        client = novaclient.Client(
            2,  # API version 2
            device.zCommandUsername,
            device.zCommandPassword,
            device.zOpenStackProjectId,
            device.zOpenStackAuthUrl,
            region_name=region_name,
            http_log_debug=http_log_debug
        )

        results = {}

        log.info('Requesting flavors')
        results['flavors'] = client.flavors.list()

        log.info('Requesting images')
        results['images'] = client.images.list()

        log.info('Requesting servers')
        results['servers'] = client.servers.list()

        log.info('Requesting services')
        results['services'] = client.services.list()

        log.info('Requesting hypervisors')
        results['hypervisors'] = client.hypervisors.search('%', servers=True)

        return results

    def process(self, device, results, unused):
        region_id = prepId("region-{0}".format(device.zOpenStackRegionName))
        region = ObjectMap(
            modname='ZenPacks.zenoss.OpenStack.Region',
                data=dict(
                    id=region_id,
                    title=device.zOpenStackRegionName
            ))

        flavors = []
        for flavor in results['flavors']:
            flavors.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStack.Flavor',
                data=dict(
                    id='flavor-{0}'.format(flavor.id),
                    title=flavor.name,  # 256 server
                    flavorId=flavor.id,  # performance1-1
                    flavorRAM=flavor.ram * 1024 * 1024,  # 256
                    flavorDisk=flavor.disk * 1024 * 1024 * 1024,  # 10
            )))

        images = []
        for image in results['images']:
            # Sometimes there's no created timestamp for an image.
            created = getattr(image, 'created', '')

            images.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStack.Image',
                data=dict(
                    id='image-{0}'.format(image.id),
                    title=image.name,  # Red Hat Enterprise Linux 5.5
                    imageId=image.id,  # 346eeba5-a122-42f1-94e7-06cb3c53f690
                    imageStatus=image.status,  # ACTIVE
                    imageCreated=created,  # 2010-09-17T07:19:20-05:00
                    imageUpdated=image.updated,  # 2010-09-17T07:19:20-05:00
            )))    

        servers = []
        for server in results['servers']:
            # Backup support is optional. Guard against it not existing.
            backup_schedule_enabled = None
            backup_schedule_daily = None
            backup_schedule_weekly = None

            try:
                backup_schedule_enabled = server.backup_schedule.enabled
                backup_schedule_daily = server.backup_schedule.daily
                backup_schedule_weekly = server.backup_schedule.weekly
            except (novaclient.exceptions.NotFound, AttributeError):
                backup_schedule_enabled = False
                backup_schedule_daily = 'DISABLED'
                backup_schedule_weekly = 'DISABLED'

            # The methods for accessing a server's IP addresses have changed a
            # lot. We'll try as many as we know.
            public_ips = set()
            private_ips = set()

            if hasattr(server, 'public_ip') and server.public_ip:
                if isinstance(server.public_ip, types.StringTypes):
                    public_ips.add(server.public_ip)
                elif isinstance(server.public_ip, types.ListType):
                    public_ips.update(server.public_ip)

            if hasattr(server, 'private_ip') and server.private_ip:
                if isinstance(server.private_ip, types.StringTypes):
                    private_ips.add(server.private_ip)
                elif isinstance(server.private_ip, types.ListType):
                    if isinstance(server.private_ip[0], types.StringTypes):
                        private_ips.update(server.private_ip)
                    else:
                        for address in server.private_ip:
                            private_ips.add(address['addr'])

            if hasattr(server, 'accessIPv4') and server.accessIPv4:
                public_ips.add(server.accessIPv4)

            if hasattr(server, 'accessIPv6') and server.accessIPv6:
                public_ips.add(server.accessIPv6)

            if hasattr(server, 'addresses') and server.addresses:
                for network_name, addresses in server.addresses.items():
                    for address in addresses:
                        if 'public' in network_name.lower():
                            if isinstance(address, types.DictionaryType):
                                public_ips.add(address['addr'])
                            elif isinstance(address, types.StringTypes):
                                public_ips.add(address)
                        else:
                            if isinstance(address, types.DictionaryType):
                                private_ips.add(address['addr'])
                            elif isinstance(address, types.StringTypes):
                                private_ips.add(address)

            # Flavor and Image IDs could be specified two different ways.
            flavor_id = None
            if hasattr(server, 'flavorId'):
                flavor_id = server.flavorId
            else:
                flavor_id = server.flavor['id']

            image_id = None
            if hasattr(server, 'imageId'):
                image_id = server.imageId
            else:
                image_id = server.image['id']

            servers.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStack.Server',
                data=dict(
                    id='server-{0}'.format(server.id),
                    title=server.name,  # cloudserver01                
                    serverId=server.id, # 847424
                    serverStatus=server.status,  # ACTIVE
                    serverBackupEnabled=backup_schedule_enabled,  # False
                    serverBackupDaily=backup_schedule_daily,   # DISABLED
                    serverBackupWeekly=backup_schedule_weekly, # DISABLED
                    publicIps=list(public_ips),   # 50.57.74.222
                    privateIps=list(private_ips), # 10.182.13.13
                    set_flavor='flavor-{0}'.format(flavor_id),  # flavor-performance1-1
                    set_image='image-{0}'.format(image_id),     # image-346eeba5-a122-42f1-94e7-06cb3c53f690
                    hostId=server.hostId,  # a84303c0021aa53c7e749cbbbfac265f
                    hostName=server.name   # cloudserver01
            )))

        hosts = []
        hostnames = set()
        for service in results['services']:
            hostnames.add(service.host)

        for hostname in hostnames:
            host_id = prepId("host-{0}".format(hostname))

            hosts.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStack.Host',
                data=dict(
                    id=host_id,
                    title=hostname
            )))

        hypervisors = []
        for hypervisor in results['hypervisors']: 
            hypervisor_id = prepId("hypervisor-{0}".format(hypervisor.id))
            host_id       = prepId("host-{0}".format(hypervisor.hypervisor_hostname))

            hypervisor_servers = []
            if hasattr(hypervisor, 'servers'):
                hypervisor_servers = ['server-{0}'.format(x['uuid']) for x in hypervisor.servers]

            hypervisors.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStack.Hypervisor',
                data=dict(
                    id=hypervisor_id,
                    title='{0}.{1}'.format(hypervisor.hypervisor_hostname, hypervisor.id),
                    hypervisorId=hypervisor.id,  # 1
                    set_servers=hypervisor_servers,
                    set_host=host_id
            )))


        services = []
        zones = {}            
        for service in results['services']:
            title = '{0}@{1} ({2})'.format(service.binary, service.host, service.zone)
            service_id = prepId('service-{0}-{1}-{2}'.format(service.binary, service.host, service.zone))
            host_id = prepId("host-{0}".format(service.host))
            zone_id = prepId("zone-{0}".format(service.zone))

            zones.setdefault(zone_id, ObjectMap(
                modname='ZenPacks.zenoss.OpenStack.AvailabilityZone',
                data=dict(
                    id=zone_id,
                    title=service.zone,
                    set_parentOrg=region_id
                )))

            services.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStack.NovaService',
                data=dict(
                    id=service_id,
                    title=title,
                    binary=service.binary,
                    set_hostedOn=host_id,
                    set_orgComponent=zone_id
                )))


        componentsMap = RelationshipMap(relname='components')
        for objmap in [region] + flavors + images + servers + hosts + hypervisors + zones.values() + services:
            componentsMap.append(objmap)

        endpointObjMap = ObjectMap(
            modname='ZenPacks.zenoss.OpenStack.Endpoint',
            data=dict(
                set_maintain_proxydevices=True
            )
        )

        return (componentsMap, endpointObjMap)
