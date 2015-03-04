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
log = logging.getLogger('zen.OpenStackInfrastructure')

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
from apiclients.neutronapiclient import NeutronAPIClient

# from ZenPacks.zenoss.OpenStackInfrastructure.modeler.plugins.zenoss.OpenStackInfrastructureNeutron import OpenStackInfrastructureNeutron

# from lib.neutronclient.v2_0.client import Client as NeutronAPIClient

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

        result = yield client.flavors(detailed = True, is_public = None)
        results['flavors'] = result['flavors']
        log.debug('flavors: %s\n' % str(results['flavors']))

        result = yield client.images(detailed = True)
        results['images'] = result['images']
        log.debug('images: %s\n' % str(results['images']))

        result = yield client.hypervisors(detailed = False,
                                          hypervisor_match = '%',
                                          servers = True)
        results['hypervisors'] = result['hypervisors']
        log.debug('hypervisors: %s\n' % str(results['hypervisors']))

        result = yield client.servers(detailed = True, search_opts={'all_tenants': 1})
        results['servers'] = result['servers']
        log.debug('servers: %s\n' % str(results['servers']))

        result = yield client.services()
        results['services'] = result['services']
        log.debug('services: %s\n' % str(results['services']))

        # Neutron
        neutron_client = NeutronAPIClient(
            username = device.zCommandUsername,
            password = device.zCommandPassword,
            auth_url = device.zOpenStackAuthUrl,
            project_id = device.zOpenStackProjectId,
            region_name = device.zOpenStackRegionName,
            )

        result = yield neutron_client.agents()
        results['agents'] = result['agents']

        # ---------------------------------------------------------------------
        # Insert the l3_agents - routers list
        # ---------------------------------------------------------------------
        for _agent in results['agents']:
            _agent['l3_agent_routers'] = []
            _routers = []

            if _agent['agent_type'].lower() == 'l3 agent':
                router_data = yield \
                    neutron_client.api_call('/v2.0/agents/%s/l3-routers'
                                            % str(_agent['id']))

                for r in router_data['routers']: _routers.append(r.get('id'))

            _agent['l3_agent_routers'] = _routers

        # ---------------------------------------------------------------------
        # Insert the DHCP agents-subnets info
        # ---------------------------------------------------------------------
        for _agent in results['agents']:
            _agent['dhcp_agent_subnets'] = []
            _subnets = []

            if _agent['agent_type'].lower() == 'dhcp agent':
                dhcp_data = yield \
                    neutron_client.api_call('/v2.0/agents/%s/dhcp-networks'
                                            % str(_agent['id']))

                for network in dhcp_data['networks']:
                    for subnet in network['subnets']:
                        _subnets.append(subnet)

            _agent['dhcp_agent_subnets'] = _subnets

        result = yield neutron_client.networks()
        results['networks'] = result['networks']

        result = yield neutron_client.subnets()
        results['subnets'] = result['subnets']

        result = yield neutron_client.routers()
        results['routers'] = result['routers']

        # ---------------------------------------------------------------------
        # Please leave this code here for reference.
        # ---------------------------------------------------------------------
        # # Get router => L3-Agents relation data
        # for _router in results['routers']:

        #     l3_agents = yield neutron_client.api_call(
        #                         '/v2.0/routers/%s/l3-agents'
        #                         % str(_router['id'])
        #                              )
        #     _router['l3_agent_list'] = [str(x['id']) for x in l3_agents['agents']]

        result = yield neutron_client.ports()
        results['ports'] = result['ports']

        # result = yield neutron_client.security_groups()
        # results['security_groups'] = result['security_groups']
        results['security_groups'] = {}

        result = yield neutron_client.floatingips()
        results['floatingips'] = result['floatingips']

        returnValue(results)

    def process(self, device, results, unused):
        tenants = []
        for tenant in results['tenants']:
            if tenant['enabled'] is not True:
                continue

            tenants.append(ObjectMap(
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.Tenant',
                data = dict(
                    id = 'tenant-{0}'.format(tenant['id']),
                    title = tenant['name'],              # nova
                    description = tenant['description'], # tenant description
                    tenantId = tenant['id']
                )))

        region_id = prepId("region-{0}".format(device.zOpenStackRegionName))
        region = ObjectMap(
            modname = 'ZenPacks.zenoss.OpenStackInfrastructure.Region',
            data = dict(
                id = region_id,
                title = device.zOpenStackRegionName
            ))

        flavors = []
        for flavor in results['flavors']:
            flavors.append(ObjectMap(
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.Flavor',
                data = dict(
                    id = 'flavor-{0}'.format(flavor['id']),
                    title = flavor['name'],  # 256 server
                    flavorId = flavor['id'],  # performance1-1
                    flavorRAM = flavor['ram'] * 1024 * 1024,  # 256
                    flavorDisk = flavor['disk'] * 1024 * 1024 * 1024,  # 10
                    flavorVCPUs = flavor['vcpus'],
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
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.Image',
                data = dict(
                    id = 'image-{0}'.format(image['id']),
                    title = image['name'],  # Red Hat Enterprise Linux 5.5
                    imageId = image['id'],  # 346eeba5-a122-42f1-94e7-06cb3c53f690
                    imageStatus = image['status'],  # ACTIVE
                    imageCreated = imageCreated,  # 2014/09/30 19:45:44.000
                    imageUpdated = imageUpdated,  # 2014/09/30 19:45:44.000
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

            if 'public_ip' in server and server['public_ip']:
                if isinstance(server['public_ip'], types.StringTypes):
                    public_ips.add(server['public_ip'])
                elif isinstance(server['public_ip'], types.ListType):
                    public_ips.update(server['public_ip'])

            if 'private_ip' in server and server['private_ip']:
                if isinstance(server['private_ip'], types.StringTypes):
                    private_ips.add(server['private_ip'])
                elif isinstance(server['private_ip'], types.ListType):
                    if isinstance(server['private_ip'][0], types.StringTypes):
                        private_ips.update(server['private_ip'])
                    else:
                        for address in server['private_ip']:
                            private_ips.add(address['addr'])

            if 'accessIPv4' in server and server['accessIPv4']:
                public_ips.add(server['accessIPv4'])

            if 'accessIPv6' in server and server['accessIPv6']:
                public_ips.add(server['accessIPv6'])

            if 'addresses' in server and server['addresses']:
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
            if 'flavorId' in server:
                flavor_id = server['flavorId']
            elif 'flavor' in server and 'id' in server['flavor']:
                flavor_id = server['flavor']['id']

            image_id = None
            if 'imageId' in server:
                image_id = server['imageId']
            elif 'image' in server and \
                 isinstance(server['image'], dict) and \
                 'id' in server['image']:
                image_id = server['image']['id']

            tenant_id = server['tenant_id']

            servers.append(ObjectMap(
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.Instance',
                data = dict(
                    id = 'server-{0}'.format(server['id']),
                    title = server['name'],   # cloudserver01
                    resourceId = server['id'],
                    serverId = server['id'],  # 847424
                    serverStatus = server['status'],  # ACTIVE
                    serverBackupEnabled = backup_schedule_enabled,  # False
                    serverBackupDaily = backup_schedule_daily,      # DISABLED
                    serverBackupWeekly = backup_schedule_weekly,    # DISABLED
                    publicIps = list(public_ips),                   # 50.57.74.222
                    privateIps = list(private_ips),                 # 10.182.13.13
                    set_flavor = 'flavor-{0}'.format(flavor_id),    # flavor-performance1-1
                    set_image = 'image-{0}'.format(image_id),       # image-346eeba5-a122-42f1-94e7-06cb3c53f690
                    set_tenant = 'tenant-{0}'.format(tenant_id),    # tenant-a3a2901f2fd14f808401863e3628a858
                    hostId = server['hostId'],                      # a84303c0021aa53c7e749cbbbfac265f
                    hostName = server['name']                       # cloudserver01
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
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.AvailabilityZone',
                data = dict(
                    id = zone_id,
                    title = service['zone'],
                    set_parentOrg = region_id
                )))

            # Currently, nova-api doesn't show in the nova service list.
            # Even if it does show up there in the future, I don't model
            # it as a NovaService, but rather as its own type of software
            # component.   (See below)
            if service['binary'] == 'nova-api':
                continue

            services.append(ObjectMap(
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.NovaService',
                data = dict(
                    id = service_id,
                    title = title,
                    binary = service['binary'],
                    enabled={
                        'enabled': True,
                        'disabled': False
                    }.get(service['status'], False),
                    operStatus={
                        'up': 'UP',
                        'down': 'DOWN'
                    }.get(service['state'], 'UNKNOWN'),
                    set_hostedOn = host_id,
                    set_orgComponent = zone_id
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
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.Host',
                data = dict(
                    id = host_id,
                    title = data['hostname'],
                    hostname = data['hostname'],
                    set_orgComponent = data['org_id']
                )))

        hypervisors = []
        server_hypervisor_instance_name = {}
        for hypervisor in results['hypervisors']:
            hypervisor_id = prepId("hypervisor-{0}".format(hypervisor['id']))

            hypervisor_servers = []
            if 'servers' in hypervisor:
                for server in hypervisor['servers']:
                    server_id = 'server-{0}'.format(server['uuid'])
                    hypervisor_servers.append(server_id)
                    server_hypervisor_instance_name[server_id] = server['name']

            hypervisors.append(ObjectMap(
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.Hypervisor',
                data = dict(
                    id = hypervisor_id,
                    title = '{0}.{1}'.format(hypervisor['hypervisor_hostname'], hypervisor['id']),
                    hypervisorId = hypervisor['id'],  # 1
                    set_instances = hypervisor_servers,
                    set_hostByName = hypervisor['hypervisor_hostname'],
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
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.NovaApi',
                data = dict(
                    id = nova_api_id,
                    title = title,
                    binary = 'nova-api',
                    set_hostedOn = host_id,
                    set_orgComponent = region_id
                )))

        # agent
        agents = []
        for agent in results['agents']:

            # format dhcp_agent_subnets
            dhcp_agent_subnets = ['subnet-{0}'.format(x)
                                  for x in agent['dhcp_agent_subnets']]
            # format l3_agent_routers
            l3_agent_routers = ['router-{0}'.format(x)
                                for x in agent['l3_agent_routers']]

            agents.append(ObjectMap(
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.NeutronAgent',
                data = dict(
                    id = 'agent-{0}'.format(agent['id']),
                    agentId = agent['id'],
                    title = agent['binary'],
                    type = agent['agent_type'],               # true/false
                    state = agent['admin_state_up'],          # true/false
                    alive = agent['alive'],                   # ACTIVE
                    set_agentRouters = l3_agent_routers,
                    set_dhcpSubnets = dhcp_agent_subnets,
                    set_hostedOn = 'host-{0}'.format(agent['host']),
                )))

        # networking
        networks = []
        for net in results['networks']:
            networks.append(ObjectMap(
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.Network',
                data = dict(
                    id = 'network-{0}'.format(net['id']),
                    netId = net['id'],
                    title = net['name'],
                    admin_state_up = net['admin_state_up'],         # true/false
                    netExternal = net['router:external'],           # true/false
                    set_tenant = 'tenant-{0}'.format(net['tenant_id']),
                    netStatus = net['status'],                      # ACTIVE
                    netType = net['provider:network_type'].upper(), # local/global
                )))

        # subnet
        subnets = []
        for subnet in results['subnets']:
            subnets.append(ObjectMap(
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.Subnet',
                data = dict(
                    cidr = subnet['cidr'],
                    dns_nameservers = subnet['dns_nameservers'],
                    gateway_ip = subnet['gateway_ip'],
                    id = 'subnet-{0}'.format(subnet['id']),
                    set_network = 'network-{0}'.format(subnet['network_id']),
                    set_tenant = 'tenant-{0}'.format(subnet['tenant_id']),
                    subnetId = subnet['id'],
                    title = subnet['name'],
                    )))

        # router
        routers = []
        for router in results['routers']:
            _gateways = set()
            _subnets = set()
            _network_id = None

            # Get the External Gateway Data
            external_gateway_info = router.get('external_gateway_info')
            if external_gateway_info:
                _network_id = external_gateway_info.get('network_id')
                for _ip in external_gateway_info['external_fixed_ips']:
                    _gateways.add(_ip.get('ip_address', None))
                    _subnets.add(_ip.get('subnet_id', None))

            routers.append(ObjectMap(
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.Router',
                data = dict(
                    admin_state_up = router['admin_state_up'],
                    gateways = list(_gateways),
                    id = 'router-{0}'.format(router['id']),
                    network_id = _network_id,
                    routerId = router['id'],
                    routes = list(router['routes']),
                    set_tenant = 'tenant-{0}'.format(router['tenant_id']),
                    set_network = 'network-{0}'.format(_network_id),
                    status = router['status'],
                    subnets = list(_subnets),
                    title = router['name'],
                )))

        # port
        ports = []
        for port in results['ports']:
            if not port['tenant_id']:
                continue

            ports.append(ObjectMap(
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.Port',
                data = dict(
                    admin_state_up = port['admin_state_up'],
                    device_owner = port['device_owner'],
                    id = 'port-{0}'.format(port['id']),
                    mac_address = port['mac_address'].upper(),
                    network_id = port['network_id'],
                    portId = port['id'],
                    set_network = 'network-{0}'.format(port['network_id']),
                    set_tenant = 'tenant-{0}'.format(port['tenant_id']),
                    status = port['status'],
                    title = port['name'],
                    vif_type = port['binding:vif_type'],
                    )))

        # security_group
        # WARNING: We must use "securitygroup-{id}" for proper modeler naming
        security_groups = []
        for sg in results['security_groups']:
            security_groups.append(ObjectMap(
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.SecurityGroup',
                data = dict(
                    id = 'securitygroup-{0}'.format(sg['id']),
                    sgId = sg['id'],
                    title = sg['name'],
                    set_tenant = 'tenant-{0}'.format(sg['tenant_id']),
                    )))

        # # floatingip
        floatingips = []
        for floatingip in results['floatingips']:
            floatingips.append(ObjectMap(
                modname = 'ZenPacks.zenoss.OpenStackInfrastructure.FloatingIp',
                data = dict(
                    floatingipId = floatingip['id'],
                    fixed_ip_address = floatingip['fixed_ip_address'],
                    floating_ip_address = floatingip['floating_ip_address'],
                    floating_network_id = floatingip['floating_network_id'],
                    id = 'floatingip-{0}'.format(floatingip['id']),
                    router_id = floatingip['router_id'],
                    set_network = 'network-{0}'.format(floatingip['floating_network_id']),
                    set_tenant = 'tenant-{0}'.format(floatingip['tenant_id']),
                    status = floatingip['status'],
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

                        objmaps[key].append(ObjectMap(compname = compname,
                                                      modname = modname,
                                                      classname = classname,
                                                      data = om_dict))
                    added_count = len(objmaps[key]) - starting_count
                    if added_count > 0:
                        log.info("  Added %d new objectmaps to %s" % (added_count, key))

        # Apply the objmaps in the right order.
        componentsMap = RelationshipMap(relname = 'components')
        for i in ('tenants', 'regions', 'flavors', 'images', 'servers', 'zones',
                  'hosts', 'hypervisors', 'services', 'networks',
                  'subnets', 'routers', 'ports', 'agents', 'security_groups', 'floatingips',
                  ):
            for objmap in objmaps[i]:
                componentsMap.append(objmap)

        endpointObjMap = ObjectMap(
            modname = 'ZenPacks.zenoss.OpenStackInfrastructure.Endpoint',
            data = dict(
                set_maintain_proxydevices = True
            )
        )

        log.info("returning componentsMap, endpointObjMap")
        return (componentsMap, endpointObjMap)
