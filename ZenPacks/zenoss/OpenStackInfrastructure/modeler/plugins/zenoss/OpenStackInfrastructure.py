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
import itertools
from urlparse import urlparse
import socket

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.error import ConnectError, TimeoutError

from Products.ZenUtils.IpUtil import isip, asyncIpLookup
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
from Products.ZenUtils.Utils import prepId
from Products.ZenUtils.Time import isoToTimestamp, LocalDateTime

from ZenPacks.zenoss.OpenStackInfrastructure.utils import (
    add_local_lib_path,
    zenpack_path,
    get_subnets_from_fixedips,
    get_port_instance,
    getNetSubnetsGws_from_GwInfo,
    get_port_fixedips,
    sleep,
    sanitize_host_or_ip,

)

add_local_lib_path()

from apiclients.novaapiclient import NovaAPIClient, NotFoundError
from apiclients.keystoneapiclient import KeystoneAPIClient, KeystoneError
from apiclients.neutronapiclient import NeutronAPIClient, NotFoundError as NeutronNotFoundError


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

    _keystonev2errmsg = """
        Unable to connect to keystone Identity Admin API v2.0 to retrieve tenant
        list.  Tenant names will be unknown (tenants will show with their IDs only)
        until this is corrected, either by opening access to the admin API endpoint
        as listed in the keystone service catalog, or by configuring zOpenStackAuthUrl
        to point to a different, accessible endpoint which supports both the public and
        admin APIs.  (This may be as simple as changing the port in the URL from
        5000 to 35357)  Details: %s
    """

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
            device.zOpenStackProjectId,
            admin=True)

        results = {}

        results['tenants'] = []
        try:
            result = yield keystone_client.tenants()
            results['tenants'] = result['tenants']
            log.debug('tenants: %s\n' % str(results['tenants']))

        except (ConnectError, TimeoutError), e:
            log.error(self._keystonev2errmsg, e)
        except KeystoneError, e:
            if len(e.args):
                if isinstance(e.args[0], ConnectError) or \
                   isinstance(e.args[0], TimeoutError):
                    log.error(self._keystonev2errmsg, e.args[0])
                else:
                    log.error(self._keystonev2errmsg, e)
            else:
                log.error(self._keystonev2errmsg, e)
        except Exception, e:
            log.error(self._keystonev2errmsg, e)

        results['nova_url'] = yield client.nova_url()

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

        result = yield client.hypervisors(detailed=True)
        results['hypervisors_detailed'] = result['hypervisors']
        log.debug('hypervisors_detailed: %s\n' % str(results['hypervisors']))

        result = yield client.servers(detailed=True, search_opts={'all_tenants': 1})
        results['servers'] = result['servers']
        log.debug('servers: %s\n' % str(results['servers']))

        result = yield client.services()
        results['services'] = result['services']
        log.debug('services: %s\n' % str(results['services']))

        # Neutron
        neutron_client = NeutronAPIClient(
            username=device.zCommandUsername,
            password=device.zCommandPassword,
            auth_url=device.zOpenStackAuthUrl,
            project_id=device.zOpenStackProjectId,
            region_name=device.zOpenStackRegionName,
            )

        results['agents'] = []
        try:
            result = yield neutron_client.agents()
            results['agents'] = result['agents']
        except NeutronNotFoundError:
            log.error("Unable to model neutron agents because the enabled neutron plugin does not support the 'agent' API extension.")
        except Exception, e:
            log.error('Error modeling neutron agents: %s' % e)

        # ---------------------------------------------------------------------
        # Insert the l3_agents -> (routers, networks, subnets, gateways) data
        # ---------------------------------------------------------------------
        for _agent in results['agents']:
            _agent['l3_agent_routers'] = []
            _routers = set()
            _subnets = set()
            _gateways = set()
            _networks = set()

            if _agent['agent_type'].lower() == 'l3 agent':
                router_data = yield \
                    neutron_client.api_call('/v2.0/agents/%s/l3-routers'
                                            % str(_agent['id']))

                for r in router_data['routers']:
                    _routers.add(r.get('id'))
                    (net, snets, gws) = \
                        getNetSubnetsGws_from_GwInfo(r['external_gateway_info'])
                    if net: _networks.add(net)
                    _subnets = _subnets.union(snets)
                    _gateways = _gateways.union(gws)

                _agent['l3_agent_networks'] = list(_networks)
                _agent['l3_agent_subnets'] = list(_subnets)
                _agent['l3_agent_gateways'] = list(_gateways)  # Not used yet
                _agent['l3_agent_routers'] = list(_routers)

        # ---------------------------------------------------------------------
        # Insert the DHCP agents-subnets info
        # ---------------------------------------------------------------------
        for _agent in results['agents']:
            _agent['dhcp_agent_subnets'] = []
            _subnets = []
            _networks = []

            if _agent['agent_type'].lower() == 'dhcp agent':
                dhcp_data = yield \
                    neutron_client.api_call('/v2.0/agents/%s/dhcp-networks'
                                            % str(_agent['id']))

                for network in dhcp_data['networks']:
                    _networks.append(network.get('id'))
                    for subnet in network['subnets']:
                        _subnets.append(subnet)

                _agent['dhcp_agent_subnets'] = _subnets
                _agent['dhcp_agent_networks'] = _networks

        result = yield neutron_client.networks()
        results['networks'] = result['networks']

        result = yield neutron_client.subnets()
        results['subnets'] = result['subnets']

        result = yield neutron_client.routers()
        results['routers'] = result['routers']

        result = yield neutron_client.ports()
        results['ports'] = result['ports']

        result = yield neutron_client.floatingips()
        results['floatingips'] = result['floatingips']

        # Do some DNS lookups as well.
        hostnames = set([x['host'] for x in results['services']])
        hostnames.update([x['host'] for x in results['agents']])
        hostnames.update(device.zOpenStackExtraHosts)
        hostnames.update(device.zOpenStackNovaApiHosts)
        try:
            hostnames.add(urlparse(results['nova_url']).hostname)
        except Exception, e:
            log.warning("Unable to determine nova URL for nova-api component discovery: %s" % e)

        results['resolved_hostnames'] = {}
        for hostname in sorted(hostnames):
            if isip(hostname):
                results['resolved_hostnames'][hostname] = hostname
                continue

            for i in range(1, 4):
                try:
                    host_ip = yield asyncIpLookup(hostname)
                    results['resolved_hostnames'][hostname] = host_ip
                    break
                except socket.gaierror, e:
                    if e.errno == -3:
                        # temporary dns issue- try again.
                        log.error("resolve %s: (attempt %d/3): %s" % (hostname, i, e))
                        yield sleep(2)
                        continue
                    else:
                        log.error("resolve %s: %s" % (hostname, e))
                        break
                except Exception, e:
                    log.error("resolve %s: %s" % (hostname, e))
                    break

        returnValue(results)

    def process(self, device, results, unused):
        tenants = []
        for tenant in results['tenants']:
            if tenant['enabled'] is not True:
                continue

            tenants.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Tenant',
                data=dict(
                    id=prepId('tenant-{0}'.format(tenant['id'])),
                    title=tenant['name'],               # nova
                    description=tenant['description'],  # tenant description
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
                    id=prepId('flavor-{0}'.format(flavor['id'])),
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
                    id=prepId('image-{0}'.format(image['id'])),
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

            # Get and classify IP addresses into public and private: (fixed/floating)
            public_ips = set()
            private_ips = set()

            access_ipv4 = server.get('accessIPv4')
            if access_ipv4:
                public_ips.add(access_ipv4)

            access_ipv6 = server.get('accessIPv6')
            if access_ipv6:
                public_ips.add(access_ipv6)

            address_group = server.get('addresses')
            if address_group:
                for network_name, net_addresses in address_group.items():
                    for address in net_addresses:
                        if address.get('OS-EXT-IPS:type') == 'fixed':
                            private_ips.add(address['addr'])
                        elif address.get('OS-EXT-IPS:type') == 'floating':
                            public_ips.add(address['addr'])
                        else:
                            log.info("Address type not found for %s", address['addr'])
                            log.info("Adding %s to private_ips", address['addr'])
                            private_ips.add(address['addr'])

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
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Instance',
                data=dict(
                    id=prepId('server-{0}'.format(server['id'])),
                    title=server['name'],   # cloudserver01
                    resourceId=server['id'],
                    serverId=server['id'],  # 847424
                    serverStatus=server['status'],  # ACTIVE
                    serverBackupEnabled=backup_schedule_enabled,  # False
                    serverBackupDaily=backup_schedule_daily,      # DISABLED
                    serverBackupWeekly=backup_schedule_weekly,    # DISABLED
                    publicIps=list(public_ips),                   # 50.57.74.222
                    privateIps=list(private_ips),                 # 10.182.13.13
                    set_flavor=prepId('flavor-{0}'.format(flavor_id)),    # flavor-performance1-1
                    set_image=prepId('image-{0}'.format(image_id)),       # image-346eeba5-a122-42f1-94e7-06cb3c53f690
                    set_tenant=prepId('tenant-{0}'.format(tenant_id)),    # tenant-a3a2901f2fd14f808401863e3628a858
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

        # Find all hosts which have a neutron agent on them.
        for agent in results['agents']:
            sanitized_hostname = sanitize_host_or_ip(agent['host'])
            if not sanitized_hostname:
                log.debug("Skipping empty hostname %s !", agent['host'])
                continue
            if sanitized_hostname != agent['host']:
                log.debug("Sanitized hostname %s", agent['host'])

            host_id = prepId("host-{0}".format(sanitized_hostname))
            hostmap[host_id] = {
                'hostname': sanitized_hostname,
                'org_id': region_id
            }

        # add any user-specified hosts which we haven't already found.
        if device.zOpenStackNovaApiHosts or device.zOpenStackExtraHosts:
            log.info("Finding additional hosts")

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

        hypervisor_type = {}
        hypervisor_version = {}
        for hypervisor in results['hypervisors_detailed']:
            hypervisor_id = prepId("hypervisor-{0}".format(hypervisor['id']))

            hypervisor_type[hypervisor_id] = hypervisor.get('hypervisor_type', None)
            hypervisor_version[hypervisor_id] = hypervisor.get('hypervisor_version', None)

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

            hypervisor_dict = dict(
                id=hypervisor_id,
                title='{0}.{1}'.format(hypervisor['hypervisor_hostname'], hypervisor['id']),
                hypervisorId=hypervisor['id'],  # 1
                hypervisor_type=hypervisor_type.get(hypervisor_id, None),
                hypervisor_version=hypervisor_version.get(hypervisor_id, None),
                set_instances=hypervisor_servers,
                set_hostByName=hypervisor['hypervisor_hostname'],
            )

            if hypervisor_dict['hypervisor_type'] == 'VMware vCenter Server':
                # This hypervisor type does not run on a specific host, so
                # omit the host relationship.
                del hypervisor_dict['set_hostByName']

            hypervisors.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Hypervisor',
                data=hypervisor_dict))

        # add hypervisor instance name to the existing server objectmaps.
        for om in servers:
            if om.id in server_hypervisor_instance_name:
                om.hypervisorInstanceName = server_hypervisor_instance_name[om.id]

        # nova-api support.
        # Place it on the user-specified hosts, or also find it if it's
        # in the nova-service list (which we ignored earlier). It should not
        # be, under icehouse, at least, but just in case this changes..)
        nova_api_hosts = set(device.zOpenStackNovaApiHosts)
        for service in results['services']:
            if service['binary'] == 'nova-api':
                if service['host'] not in nova_api_hosts:
                    nova_api_hosts.add(service['host'])

        # Look to see if the hostname or IP in the auth url corresponds
        # directly to a host we know about.  If so, add it to the nova
        # api hosts.
        try:
            apiHostname = urlparse(results['nova_url']).hostname
            apiIp = results['resolved_hostnames'].get(apiHostname, apiHostname)
            for host in hosts:
                if host.hostname == apiHostname:
                    nova_api_hosts.add(host.hostname)
                else:
                    hostIp = results['resolved_hostnames'].get(host.hostname, host.hostname)
                    if hostIp == apiIp:
                        nova_api_hosts.add(host.hostname)
        except Exception, e:
            log.warning("Unable to perform nova-api component discovery: %s" % e)

        if not nova_api_hosts:
            log.warning("No nova-api hosts have been identified.   You must set zOpenStackNovaApiHosts to the list of hosts upon which nova-api runs.")

        for hostname in sorted(nova_api_hosts):
            title = '{0}@{1} ({2})'.format('nova-api', hostname, device.zOpenStackRegionName)
            host_id = prepId("host-{0}".format(hostname))
            nova_api_id = prepId('service-nova-api-{0}-{1}'.format(hostname, device.zOpenStackRegionName))

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
        for agent in results['agents']:

            sanitized_hostname = sanitize_host_or_ip(agent['host'])
            if not sanitized_hostname:
                log.debug("Skipping empty hostname %s !", agent['host'])
                continue
            if sanitized_hostname != agent['host']:
                log.debug("Sanitized hostname %s", agent['host'])

            # Get agent's host
            agent_host = prepId('host-{0}'.format(sanitized_hostname))

            # ------------------------------------------------------------------
            # AgentSubnets Section
            # ------------------------------------------------------------------

            agent_subnets = []
            agent_networks = []
            if agent.get('dhcp_agent_networks'):
                agent_networks = ['network-{0}'.format(x)
                                  for x in agent['dhcp_agent_networks']]

            if agent.get('dhcp_agent_subnets'):
                agent_subnets = ['subnet-{0}'.format(x)
                                 for x in agent['dhcp_agent_subnets']]

            if agent.get('l3_agent_subnets'):
                agent_subnets = ['subnet-{0}'.format(x)
                                 for x in agent['l3_agent_subnets']]

            if agent.get('l3_agent_networks'):
                agent_networks = ['network-{0}'.format(x)
                                  for x in agent['l3_agent_networks']]

            # ------------------------------------------------------------------
            # format l3_agent_routers
            l3_agent_routers = ['router-{0}'.format(x)
                                for x in agent['l3_agent_routers']]

            title = '{0}@{1}'.format(agent['agent_type'], agent['host'])
            agents.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.NeutronAgent',
                data=dict(
                    id=prepId('agent-{0}'.format(agent['id'])),
                    title=title,
                    binary=agent['binary'],
                    enabled=agent['admin_state_up'],
                    operStatus={
                        True: 'UP',
                        False: 'DOWN'
                    }.get(agent['alive'], 'UNKNOWN'),

                    agentId=agent['id'],
                    type=agent['agent_type'],

                    set_routers=l3_agent_routers,
                    set_subnets=agent_subnets,
                    set_networks=agent_networks,
                    set_hostedOn=agent_host,
                    set_orgComponent=hostmap[agent_host]['org_id'],
                )))

        # networking
        networks = []
        for net in results['networks']:
            networks.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Network',
                data=dict(
                    id=prepId('network-{0}'.format(net['id'])),
                    netId=net['id'],
                    title=net['name'],
                    admin_state_up=net['admin_state_up'],         # true/false
                    netExternal=net['router:external'],           # true/false
                    set_tenant=prepId('tenant-{0}'.format(net['tenant_id'])),
                    netStatus=net['status'],                      # ACTIVE
                    netType=net.get('provider:network_type', 'UNKNOWN').upper()  # local/global
                )))

        # subnet
        subnets = []
        for subnet in results['subnets']:
            subnets.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Subnet',
                data=dict(
                    cidr=subnet['cidr'],
                    dns_nameservers=subnet['dns_nameservers'],
                    gateway_ip=subnet['gateway_ip'],
                    id=prepId('subnet-{0}'.format(subnet['id'])),
                    set_network=prepId('network-{0}'.format(subnet['network_id'])),
                    set_tenant=prepId('tenant-{0}'.format(subnet['tenant_id'])),
                    subnetId=subnet['id'],
                    title=subnet['name'],
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
                for _ip in external_gateway_info.get('external_fixed_ips', []):
                    _gateways.add(_ip.get('ip_address', None))
                    _subnets.add(_ip.get('subnet_id', None))

            _network = None
            if _network_id:
                _network = 'network-{0}'.format(_network_id)

            routers.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Router',
                data=dict(
                    admin_state_up=router['admin_state_up'],
                    gateways=list(_gateways),
                    id=prepId('router-{0}'.format(router['id'])),
                    routerId=router['id'],
                    routes=list(router['routes']),
                    set_network=prepId(_network),
                    set_subnets=[prepId('subnet-{0}'.format(x)) for x in _subnets],
                    set_tenant=prepId('tenant-{0}'.format(router['tenant_id'])),
                    status=router['status'],
                    title=router['name'],
                )))

        # port
        ports = []
        for port in results['ports']:
            port_tenant = None
            if port['tenant_id']:
                port_tenant = prepId('tenant-{0}'.format(port['tenant_id']))

            port_instance = get_port_instance(port['device_owner'],
                                              port['device_id'])
            if port_instance:
                port_instance = prepId(port_instance)

            ports.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Port',
                data=dict(
                    admin_state_up=port['admin_state_up'],
                    device_owner=port['device_owner'],
                    fixed_ip_list=get_port_fixedips(port['fixed_ips']),
                    id=prepId('port-{0}'.format(port['id'])),
                    mac_address=port['mac_address'].upper(),
                    portId=port['id'],
                    set_instance=port_instance,
                    set_network=prepId('network-{0}'.format(port['network_id'])),
                    set_subnets=[prepId(x) for x in get_subnets_from_fixedips(port['fixed_ips'])],
                    set_tenant=port_tenant,
                    status=port['status'],
                    title=port['name'],
                    vif_type=port['binding:vif_type'],
                    )))

        # floatingip
        floatingips = []
        for floatingip in results['floatingips']:
            floatingips.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.FloatingIp',
                data=dict(
                    floatingipId=floatingip['id'],
                    fixed_ip_address=floatingip['fixed_ip_address'],
                    floating_ip_address=floatingip['floating_ip_address'],
                    id=prepId('floatingip-{0}'.format(floatingip['id'])),
                    set_router=prepId('router-{0}'.format(floatingip['router_id'])),
                    set_network=prepId('network-{0}'.format(floatingip['floating_network_id'])),
                    set_port=prepId('port-{0}'.format(floatingip['port_id'])),
                    set_tenant=prepId('tenant-{0}'.format(floatingip['tenant_id'])),
                    status=floatingip['status'],
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
            'floatingips': floatingips,
        }

        # If we have references to tenants which we did not discover during
        # (keystone) modeling, create dummy records for them.
        all_tenant_ids = set()
        for objmap in itertools.chain.from_iterable(objmaps.values()):
            try:
                all_tenant_ids.add(objmap.set_tenant)
            except AttributeError:
                pass

        if None in all_tenant_ids:
            all_tenant_ids.remove(None)

        known_tenant_ids = set([x.id for x in tenants])
        for tenant_id in all_tenant_ids - known_tenant_ids:
            tenants.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Tenant',
                data=dict(
                    id=prepId(tenant_id),
                    title=str(tenant_id),
                    description=str(tenant_id),
                    tenantId=tenant_id[7:]  # strip tenant- prefix
                )))

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
                  'hosts', 'hypervisors', 'services', 'networks',
                  'subnets', 'routers', 'ports', 'agents', 'floatingips',
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
