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

""" Get component information using OpenStack API clients """

import logging
log = logging.getLogger('zen.OpenStack')

import json
import os
import re
import types

from twisted.internet.defer import inlineCallbacks, returnValue

from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
from Products.ZenUtils.Utils import prepId
from Products.ZenUtils.Time import isoToTimestamp, LocalDateTime

from ZenPacks.zenoss.OpenStackInfrastructure.utils import add_local_lib_path, zenpack_path
add_local_lib_path()

from apiclients.novaapiclient import NovaAPIClient, NotFoundError
from apiclients.keystoneapiclient import KeystoneAPIClient

from lib.neutronclient.v2_0.client import Client as NeutronAPIClient

class OpenStackInfrastructure(PythonPlugin):
    deviceProperties = PythonPlugin.deviceProperties + (
        'zCommandUsername',
        'zCommandPassword',
        'zOpenStackProjectId',
        'zOpenStackAuthUrl',
        'zOpenStackRegionName',
        'zOpenStackNovaApiHosts',
        'zOpenStackExtraHosts',
    )

    @inlineCallbacks
    def collect(self, device, unused):

        client = NovaAPIClient(
            device.zCommandUsername,
            device.zCommandPassword,
            device.zOpenStackAuthUrl,
            device.zOpenStackProjectId,
            device.zOpenStackRegionName)

        keystone_client = KeystoneAPIClient(
            device.zCommandUsername,
            device.zCommandPassword,
            device.zOpenStackAuthUrl,
            device.zOpenStackProjectId)

        results = {}

        result = yield keystone_client.tenants()
        results['tenants'] = result['tenants']
        log.debug('tenants: %s\n' % str(results['tenants']))

        nclient = NeutronAPIClient(
            username=device.zCommandUsername,
            password=device.zCommandPassword,
            endpoint_url=device.zOpenStackAuthUrl,
            auth_url='http://192.168.56.122:35357/v2.0/',
            region_name=device.zOpenStackRegionName,
            tenant_name=device.zOpenStackProjectId,
            )
        nclient.format = 'json'
        nclient.httpclient.endpoint_url='http://192.168.56.122:9696/'
        nclient.httpclient.authenticate_and_fetch_endpoint_url()

        result = yield client.flavors(detailed=True, is_public=None)
        results['flavors'] = result['flavors']
        log.debug('flavors: %s\n' % str(results['flavors']))

        result = yield client.images(detailed=True)
        results['images'] = result['images']
        log.debug('images: %s\n' % str(results['images']))

        result = yield client.hypervisors(detailed=False,
                                          hypervisor_match='%',
                                          servers=True)
        results['hypervisors'] = result['hypervisors']
        log.debug('hypervisors: %s\n' % str(results['hypervisors']))

        result = yield client.servers(detailed=True, search_opts={'all_tenants': 1})
        results['servers'] = result['servers']
        log.debug('servers: %s\n' % str(results['servers']))

        result = yield client.services()
        results['services'] = result['services']
        log.debug('services: %s\n' % str(results['services']))

        # non twisted neutron
        # import pdb;pdb.set_trace()
        agents = nclient.list_agents()
        results['agents'] = agents['agents']

        networks = nclient.list_networks()
        results['networks'] = networks['networks']

        subnets = nclient.list_subnets()
        results['subnets'] = subnets['subnets']

        routers = nclient.list_routers()
        results['routers'] = routers['routers']

        ports = nclient.list_ports()
        results['ports'] = ports['ports']

        security_groups = nclient.list_security_groups()
        results['security_groups'] = security_groups['security_groups']

        floatingips = nclient.list_floatingips()
        results['floatingips'] = floatingips['floatingips']

        returnValue(results)

    def process(self, device, results, unused):
        tenants = []
        for tenant in results['tenants']:
            if tenant['enabled'] is not True:
                continue

            tenants.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Tenant',
                data=dict(
                    id='tenant-{0}'.format(tenant['id']),
                    title=tenant['name'],              # nova
                    description=tenant['description'], # tenant description
                    tenantId=tenant['id']
                )))

        region_id = prepId("region-{0}".format(device.zOpenStackRegionName))
        region = ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Region',
            data=dict(
                id=region_id,
                title=device.zOpenStackRegionName
            ))

        flavors = []
        for flavor in results['flavors']:
            flavors.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Flavor',
                data=dict(
                    id='flavor-{0}'.format(flavor['id']),
                    title=flavor['name'],  # 256 server
                    flavorId=flavor['id'],  # performance1-1
                    flavorRAM=flavor['ram'] * 1024 * 1024,  # 256
                    flavorDisk=flavor['disk'] * 1024 * 1024 * 1024,  # 10
                    flavorVCPUs=flavor['vcpus'],
                )))

        images = []
        for image in results['images']:

            # If it's a snapshot, rather than a normal image, ignore it for
            # the time being.
            if 'server' in image:
                log.debug("Ignoring image %s" % image['name'])
                continue

            # If we can, change dates like '2014-09-30T19:45:44Z' to '2014/09/30 19:45:44.00'
            try:
                imageCreated = LocalDateTime(isoToTimestamp(image['created'].replace('Z', '')))
            except Exception:
                log.debug("Unable to reformat imageCreated '%s'" % image['created'])
                imageCreated = image['created']

            try:
                imageUpdated = LocalDateTime(isoToTimestamp(image['updated'].replace('Z', '')))
            except Exception:
                log.debug("Unable to reformat imageUpdated '%s'" % image['updated'])
                imageUpdated = image['updated']

            images.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Image',
                data=dict(
                    id='image-{0}'.format(image['id']),
                    title=image['name'],  # Red Hat Enterprise Linux 5.5
                    imageId=image['id'],  # 346eeba5-a122-42f1-94e7-06cb3c53f690
                    imageStatus=image['status'],  # ACTIVE
                    imageCreated=imageCreated,  # 2014/09/30 19:45:44.000
                    imageUpdated=imageUpdated,  # 2014/09/30 19:45:44.000
                )))

        servers = []
        for server in results['servers']:
            # Backup support is optional. Guard against it not existing.
            backup_schedule_enabled = None
            backup_schedule_daily = None
            backup_schedule_weekly = None

            try:
                backup_schedule_enabled = server['backup_schedule']['enabled']
                backup_schedule_daily = server['backup_schedule']['daily']
                backup_schedule_weekly = server['backup_schedule']['weekly']
            except (NotFoundError, AttributeError, KeyError):
                backup_schedule_enabled = False
                backup_schedule_daily = 'DISABLED'
                backup_schedule_weekly = 'DISABLED'

            # The methods for accessing a server's IP addresses have changed a
            # lot. We'll try as many as we know.
            public_ips = set()
            private_ips = set()

            if server.has_key('public_ip') and server['public_ip']:
                if isinstance(server['public_ip'], types.StringTypes):
                    public_ips.add(server['public_ip'])
                elif isinstance(server['public_ip'], types.ListType):
                    public_ips.update(server['public_ip'])

            if server.has_key('private_ip') and server['private_ip']:
                if isinstance(server['private_ip'], types.StringTypes):
                    private_ips.add(server['private_ip'])
                elif isinstance(server['private_ip'], types.ListType):
                    if isinstance(server['private_ip'][0], types.StringTypes):
                        private_ips.update(server['private_ip'])
                    else:
                        for address in server['private_ip']:
                            private_ips.add(address['addr'])

            if server.has_key('accessIPv4') and server['accessIPv4']:
                public_ips.add(server['accessIPv4'])

            if server.has_key('accessIPv6') and server['accessIPv6']:
                public_ips.add(server['accessIPv6'])

            if server.has_key('addresses') and server['addresses']:
                for network_name, addresses in server['addresses'].items():
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
            if server.has_key('flavorId'):
                flavor_id = server['flavorId']
            elif server.has_key('flavor') and server['flavor'].has_key('id'):
                flavor_id = server['flavor']['id']

            image_id = None
            if server.has_key('imageId'):
                image_id = server['imageId']
            elif server.has_key('image') and \
                 isinstance(server['image'], dict) and \
                 server['image'].has_key('id'):
                image_id = server['image']['id']

            tenant_id = server['tenant_id']

            servers.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Instance',
                data=dict(
                    id='server-{0}'.format(server['id']),
                    title=server['name'],   # cloudserver01
                    resourceId=server['id'],
                    serverId=server['id'],  # 847424
                    serverStatus=server['status'],  # ACTIVE
                    serverBackupEnabled=backup_schedule_enabled,  # False
                    serverBackupDaily=backup_schedule_daily,      # DISABLED
                    serverBackupWeekly=backup_schedule_weekly,    # DISABLED
                    publicIps=list(public_ips),                   # 50.57.74.222
                    privateIps=list(private_ips),                 # 10.182.13.13
                    set_flavor='flavor-{0}'.format(flavor_id),    # flavor-performance1-1
                    set_image='image-{0}'.format(image_id),       # image-346eeba5-a122-42f1-94e7-06cb3c53f690
                    set_tenant='tenant-{0}'.format(tenant_id),    # tenant-a3a2901f2fd14f808401863e3628a858
                    hostId=server['hostId'],                      # a84303c0021aa53c7e749cbbbfac265f
                    hostName=server['name']                       # cloudserver01
                )))

        services = []
        zones = {}
        hostmap = {}

        # Find all hosts which have a nova service on them.
        for service in results['services']:
            title = '{0}@{1} ({2})'.format(service['binary'], service['host'], service['zone'])
            service_id = prepId('service-{0}-{1}-{2}'.format(
                service['binary'], service['host'], service['zone']))
            host_id = prepId("host-{0}".format(service['host']))
            zone_id = prepId("zone-{0}".format(service['zone']))

            hostmap[host_id] = {
                'hostname': service['host'],
                'org_id': zone_id
            }

            zones.setdefault(zone_id, ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.AvailabilityZone',
                data=dict(
                    id=zone_id,
                    title=service['zone'],
                    set_parentOrg=region_id
                )))

            # Currently, nova-api doesn't show in the nova service list.
            # Even if it does show up there in the future, I don't model
            # it as a NovaService, but rather as its own type of software
            # component.   (See below)
            if service['binary'] == 'nova-api':
                continue

            services.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.NovaService',
                data=dict(
                    id=service_id,
                    title=title,
                    binary=service['binary'],
                    enabled={
                        'enabled': True,
                        'disabled': False
                    }.get(service['status'], False),
                    operStatus={
                        'up': 'UP',
                        'down': 'DOWN'
                    }.get(service['state'], 'UNKNOWN'),
                    set_hostedOn=host_id,
                    set_orgComponent=zone_id
                )))

        log.info("Finding hosts")
        # add any user-specified hosts which we haven't already found.
        if device.zOpenStackNovaApiHosts:
            log.info("  Adding zOpenStackNovaApiHosts=%s" % device.zOpenStackNovaApiHosts)
        if device.zOpenStackExtraHosts:
            log.info("  Adding zOpenStackExtraHosts=%s" % device.zOpenStackExtraHosts)

        for hostname in device.zOpenStackNovaApiHosts + device.zOpenStackExtraHosts:
            host_id = prepId("host-{0}".format(hostname))
            hostmap[host_id] = {
                'hostname': hostname,
                'org_id': region_id
            }

        hosts = []
        for host_id in hostmap:
            data = hostmap[host_id]
            hosts.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Host',
                data=dict(
                    id=host_id,
                    title=data['hostname'],
                    hostname=data['hostname'],
                    set_orgComponent=data['org_id']
                )))

        hypervisors = []
        server_hypervisor_instance_name = {}
        for hypervisor in results['hypervisors']:
            hypervisor_id = prepId("hypervisor-{0}".format(hypervisor['id']))

            hypervisor_servers = []
            if hypervisor.has_key('servers'):
                for server in hypervisor['servers']:
                    server_id = 'server-{0}'.format(server['uuid'])
                    hypervisor_servers.append(server_id)
                    server_hypervisor_instance_name[server_id] = server['name']

            hypervisors.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Hypervisor',
                data=dict(
                    id=hypervisor_id,
                    title='{0}.{1}'.format(hypervisor['hypervisor_hostname'], hypervisor['id']),
                    hypervisorId=hypervisor['id'],  # 1
                    set_instances=hypervisor_servers,
                    set_hostByName=hypervisor['hypervisor_hostname'],
                )))

        # add hypervisor instance name to the existing server objectmaps.
        for om in servers:
            if om.id in server_hypervisor_instance_name:
                om.hypervisorInstanceName = server_hypervisor_instance_name[om.id]

        # nova-api support.
        # Place it on the user-specified hosts, or also find it if it's
        # in the nova-service list (which we ignored earlier). It should not
        # be, under icehouse, at least, but just in case this changes..)
        nova_api_hosts = device.zOpenStackNovaApiHosts
        for service in results['services']:
            if service['binary'] == 'nova-api':
                if service['host'] not in nova_api_hosts:
                    nova_api_hosts.append(service['host'])

        for hostname in nova_api_hosts:
            title = '{0}@{1} ({2})'.format('nova-api', hostname, device.zOpenStackRegionName)
            host_id = prepId("host-{0}".format(hostname))
            nova_api_id = prepId('service-nova-api-{0}-{1}'.format(service['host'], device.zOpenStackRegionName))

            services.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.NovaApi',
                data=dict(
                    id=nova_api_id,
                    title=title,
                    binary='nova-api',
                    set_hostedOn=host_id,
                    set_orgComponent=region_id
                )))

        # agent
        agents = []
        # import pdb;pdb.set_trace()
        for agent in results['agents']:
            agents.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Agent',
                data=dict(
                    id='agent-{0}'.format(agent['id']),
                    title=agent['binary'],
                    type=agent['agent_type'],               # true/false
                    host=agent['host'],
                    alive=agent['alive'],                      # ACTIVE
                )))

        # networking
        networks = []
        for net in results['networks']:
            tenant_name = [tenant['name'] for tenant in results['tenants'] \
                           if tenant['enabled'] == True and \
                              tenant['id'] == net['tenant_id']]
            cidrs = ""
            for snetid in net['subnets']:
                for subnet in results['subnets']:
                    if subnet['id'] == snetid:
                        cidrs = cidrs + subnet['cidr']
            networks.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Network',
                data=dict(
                    id='network-{0}'.format(net['id']),
                    title=net['name'],
                    netState=net['admin_state_up'],               # true/false
                    netExternal=net['router:external'],           # TRUE/FALSE
                    tenant_=tenant_name[0],
                    netStatus=net['status'],                      # ACTIVE
                    netType=net['provider:network_type'].upper(), # local/global
                    subnet_=cidrs
                )))

        # subnet
        subnets = []
        for subnet in results['subnets']:
            tenant_name = [tenant['name'] for tenant in results['tenants'] \
                           if tenant['enabled'] == True and \
                              tenant['id'] == subnet['tenant_id']]
            network_name = [network['name'] for network in results['networks'] \
                            if network['status'] == 'ACTIVE' and \
                               network['id'] == subnet['network_id']]
            subnets.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Subnet',
                data=dict(
                    id='subnet-{0}'.format(subnet['id']),
                    title=subnet['name'],
                    cidr=subnet['cidr'],
                    dns=subnet['dns_nameservers'],
                    tenant_=tenant_name[0],
                    network_=network_name[0],
                    gateway=subnet['gateway_ip'],
                    )))


        # router
        routers = []
        for router in results['routers']:
            tenant_name = [tenant['name'] for tenant in results['tenants'] \
                           if tenant['enabled'] == True and \
                              tenant['id'] == router['tenant_id']]
            network_name = [network['name'] for network in results['networks'] \
                            if network['status'] == 'ACTIVE' and \
                               network['id'] == router['external_gateway_info']['network_id']]
            routers.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Router',
                data=dict(
                    id='router-{0}'.format(router['id']),
                    title=router['name'],
                    status=router['status'],
                    tenant_=tenant_name[0],
                    gateway=network_name[0],
                    routes=router['routes'],
                )))

        # port
        ports = []
        # import pdb;pdb.set_trace()
        for port in results['ports']:
            if not port['tenant_id']:
                continue

            tenant_name = [tenant['name'] for tenant in results['tenants'] \
                           if tenant['enabled'] == True and \
                              tenant['id'] == port['tenant_id']]
            network_name = [network['name'] for network in results['networks'] \
                            if network['status'] == 'ACTIVE' and \
                               network['id'] == port['network_id']]
            ports.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Port',
                data=dict(
                    id='port-{0}'.format(port['id']),
                    network_=network_name[0],
                    status=port['status'],
                    tenant_=tenant_name[0],
                    # gateway=network_name[0],
                    host=port['binding:host_id'],
                    mac=port['mac_address'],
                    owner=port['device_owner'],
                    # type_=port['binding:vif_type'],
                    )))

        # security_group
        security_groups = []
        for sg in results['security_groups']:
            tenant_name = [tenant['name'] for tenant in results['tenants'] \
                           if tenant['enabled'] == True and \
                              tenant['id'] == sg['tenant_id']]
            security_groups.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.SecurityGroup',
                data=dict(
                    id='security_group-{0}'.format(sg['id']),
                    title=sg['name'],
                    tenant_=tenant_name[0],
                    )))

        # # floatingip
        floatingips = []
        for floatingip in results['floatingips']:
            tenant_name = [tenant['name'] for tenant in results['tenants'] \
                           if tenant['enabled'] == True and \
                              tenant['id'] == floatingip['tenant_id']]
            network_name = [network['name'] for network in results['networks'] \
                            if network['status'] == 'ACTIVE' and \
                               network['id'] == floatingip['external_gateway_info']['network_id']]
            router_name = [router['name'] for router in results['routers'] \
                            if router['status'] == 'ACTIVE' and \
                               router['id'] == floatingip['router_id']]
            floatingips.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.FloatingIp',
                data=dict(
                    id='floatingip-{0}'.format(floatingip['id']),
                    title=floatingip['name'],
                    status=floatingip['status'],
                    network_=network_name[0],
                    tenant_=tenant_name[0],
                    router_=router_name[0],
                    )))

        objmaps = {
            'flavors': flavors,
            'hosts': hosts,
            'hypervisors': hypervisors,
            'images': images,
            'regions': [region],
            'servers': servers,
            'services': services,
            'tenants': tenants,
            'zones': zones.values(),
            'agents': agents,
            'networks': networks,
            'subnets': subnets,
            'routers': routers,
            'ports': ports,
            'security_groups': security_groups,
            'floatingips': floatingips,
        }

        # If the user has provided a list of static objectmaps to
        # slap on the ends of the ones we discovered dynamically, add them in.
        # (this is mostly for testing purposes!)
        filename = zenpack_path('static_objmaps.json')
        if os.path.exists(filename):
            log.info("Loading %s" % filename)
            data = ''
            with open(filename) as f:
                for line in f:
                    # skip //-style comments
                    if re.match(r'^\s*//', line):
                        data += "\n"
                    else:
                        data += line
                static_objmaps = json.loads(data)
            for key in objmaps:
                if key in static_objmaps and len(static_objmaps[key]):
                    starting_count = len(objmaps[key])
                    for om_dict in static_objmaps[key]:
                        compname = om_dict.pop('compname', None)
                        modname = om_dict.pop('modname', None)
                        classname = om_dict.pop('classname', None)
                        for v in om_dict:
                            om_dict[v] = str(om_dict[v])

                        if 'id' not in om_dict:
                            # Try to match it to an existing objectmap by title (as a regexp)
                            # and merge into it.
                            found = False
                            for om in objmaps[key]:
                                if re.match(om_dict['title'], om.title):
                                    found = True
                                    for attr in om_dict:
                                        if attr != 'title':
                                            log.info("  Adding %s=%s to %s (%s)" % (attr, om_dict[attr], om.id, om.title))
                                            setattr(om, attr, om_dict[attr])
                                    break

                            if not found:
                                log.error("Unable to find a matching objectmap to extend: %s" % om_dict)

                            continue

                        objmaps[key].append(ObjectMap(compname=compname,
                                                      modname=modname,
                                                      classname=classname,
                                                      data=om_dict))
                    added_count = len(objmaps[key]) - starting_count
                    if added_count > 0:
                        log.info("  Added %d new objectmaps to %s" % (added_count, key))


        # Apply the objmaps in the right order.
        componentsMap = RelationshipMap(relname='components')
        for i in ('tenants', 'regions', 'flavors', 'images', 'servers', 'zones',
                  'hosts', 'hypervisors', 'services',
                  'agents', 'networks', 'subnets', 'routers', 'ports', 'security_groups', 'floatingips',
                 ):
            for objmap in objmaps[i]:
                componentsMap.append(objmap)

        endpointObjMap = ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Endpoint',
            data=dict(
                set_maintain_proxydevices=True
            )
        )

        return (componentsMap, endpointObjMap)
