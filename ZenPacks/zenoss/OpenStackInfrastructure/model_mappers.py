##############################################################################
#
# Copyright (C) Zenoss, Inc. 2018, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
LOG = logging.getLogger('zen.OpenStackInfrastructure.model_mappers')

from collections import defaultdict
import re
import hashlib

from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.ZenUtils.Utils import prepId
from Products.ZenUtils.Time import isoToTimestamp, LocalDateTime

from ZenPacks.zenoss.OpenStackInfrastructure.hostmap import InvalidHostIdException
from ZenPacks.zenoss.OpenStackInfrastructure.utils import (
    get_subnets_from_fixedips,
    get_port_instance,
    get_port_fixedips,
)

POWER_STATE_MAP = {
    0: 'pending',
    1: 'running',
    3: 'paused',
    4: 'shutdown',
    6: 'crashed',
    7: 'suspended',
    }


def map_tenants(device, results, hostmap):
    tenants = []
    quota_tenants = []

    for tenant in results['tenants']:
        if tenant.get('enabled', False) is not True:
            continue
        if not tenant.get('id', None):
            continue

        quota_tenant = dict(name=tenant.get('name', tenant['id']),
                            id=tenant['id'])
        quota_tenants.append(quota_tenant)

        tenants.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Tenant',
            data=dict(
                id=prepId('tenant-{0}'.format(tenant['id'])),
                title=tenant.get('name', tenant['id']),
                description=tenant.get('description', ''),
                tenantId=tenant['id']
            )))

    results['process_quota_tenants'] = quota_tenants
    return tenants


def map_regions(device, results, hostmap):
    region_id = prepId("region-{0}".format(device.zOpenStackRegionName))
    region = ObjectMap(
        modname='ZenPacks.zenoss.OpenStackInfrastructure.Region',
        data=dict(
            id=region_id,
            title=device.zOpenStackRegionName
        ))
    results['process_region_id'] = region_id
    return [region]


def map_flavors(device, results, hostmap):
    flavors = []
    for flavor in results['flavors']:
        if not flavor.get('id', None):
            continue

        flavors.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Flavor',
            data=dict(
                id=prepId('flavor-{0}'.format(flavor['id'])),
                title=flavor.get('name', flavor['id']),  # 256 server
                flavorId=flavor['id'],  # performance1-1
                flavorRAM=flavor.get('ram', 0) * 1024 * 1024,
                flavorDisk=flavor.get('disk', 0) * 1024 * 1024 * 1024,
                flavorVCPUs=flavor.get('vcpus', 0),
                # default to True, since default flavor is always public
                flavorType=str(flavor.get('os-flavor-access:is_public', True)),
            )))
    return flavors


def map_images(device, results, hostmap):
    images = []
    for image in results['images']:
        if not image.get('id', None):
            continue

        # If we can, change dates like '2014-09-30T19:45:44Z' to '2014/09/30 19:45:44.00'
        try:
            imageCreated = LocalDateTime(isoToTimestamp(image.get('created', '').replace('Z', '')))
        except Exception:
            LOG.debug("Unable to reformat imageCreated '%s'" % image.get('created', ''))
            imageCreated = image.get('created', '')

        try:
            imageUpdated = LocalDateTime(isoToTimestamp(image.get('updated', '').replace('Z', '')))
        except Exception:
            LOG.debug("Unable to reformat imageUpdated '%s'" % image.get('updated', ''))
            imageUpdated = image.get('updated', '')

        images.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Image',
            data=dict(
                id=prepId('image-{0}'.format(image['id'])),
                title=image.get('name', image['id']),  # Red Hat Enterprise Linux 5.5
                imageId=image['id'],  # 346eeba5-a122-42f1-94e7-06cb3c53f690
                imageStatus=image.get('status', ''),  # ACTIVE
                imageCreated=imageCreated,  # 2014/09/30 19:45:44.000
                imageUpdated=imageUpdated,  # 2014/09/30 19:45:44.000
            )))

    return images


def map_hypervisors(device, results, hostmap):
    hypervisor_type = {}
    hypervisor_version = {}
    for hypervisor in results['hypervisors_detailed']:
        if not hypervisor.get('id', None):
            continue

        hypervisor_id = prepId("hypervisor-{0}".format(hypervisor['id']))

        hypervisor_type[hypervisor_id] = hypervisor.get('hypervisor_type', None)
        hypervisor_version[hypervisor_id] = hypervisor.get('hypervisor_version', None)

        if hypervisor_type[hypervisor_id] is None:
            # if results['hypervisors_detailed'] did not give us hypervisor type,
            # hypervisor version, try results['hypervisors_details']
            hypervisor_type[hypervisor_id] = \
                results['hypervisor_details'][hypervisor_id].get(
                    'hypervisor_type', None)

        if hypervisor_version[hypervisor_id] is None:
            # if results['hypervisors_detailed'] did not give us version,
            # hypervisor version, try results['hypervisors_details']
            hypervisor_version[hypervisor_id] = \
                results['hypervisor_details'][hypervisor_id].get(
                    'hypervisor_version', None)

        # Reformat the version string.
        if hypervisor_version[hypervisor_id] is not None:
            hypervisor_version[hypervisor_id] = '.'.join(
                str(hypervisor_version[hypervisor_id]).split('00'))

    hypervisors = []
    server_hypervisor_instance_name = {}
    for hypervisor in results['hypervisors']:
        if not hypervisor.get('id', None):
            continue

        hypervisor_id = prepId("hypervisor-{0}".format(hypervisor['id']))

        # this is how a hypervisor discovers the instances belonging to it
        hypervisor_servers = []
        if 'servers' in hypervisor:
            for server in hypervisor['servers']:
                server_id = 'server-{0}'.format(server.get('uuid', ''))
                hypervisor_servers.append(server_id)
                server_hypervisor_instance_name[server_id] = server.get('name', '')

        hypervisor_dict = dict(
            id=hypervisor_id,
            title='{0}.{1}'.format(hypervisor.get('hypervisor_hostname', ''),
                                   hypervisor['id']),
            hypervisorId=hypervisor['id'],  # 1
            hypervisor_type=hypervisor_type.get(hypervisor_id, ''),
            hypervisor_version=hypervisor_version.get(hypervisor_id, None),
            # hypervisor state: power state, UP/DOWN
            hstate=hypervisor.get('state', 'unknown').upper(),
            # hypervisor status: ENABLED/DISABLED
            hstatus=hypervisor.get('status', 'unknown').upper(),
            # hypervisor ip: internal ip address
            host_ip=results['hypervisor_details'].get(
                hypervisor_id, {}).get('host_ip', None),
            vcpus=results['hypervisor_details'].get(
                hypervisor_id, {}).get('vcpus', None),
            vcpus_used=results['hypervisor_details'].get(
                hypervisor_id, {}).get('vcpus_used', None),
            memory=results['hypervisor_details'].get(
                hypervisor_id, {}).get('memory_mb', None),
            memory_used=results['hypervisor_details'].get(
                hypervisor_id, {}).get('memory_mb_used', None),
            memory_free=results['hypervisor_details'].get(
                hypervisor_id, {}).get('free_ram_mb', None),
            disk=results['hypervisor_details'].get(
                hypervisor_id, {}).get('local_gb', None),
            disk_used=results['hypervisor_details'].get(
                hypervisor_id, {}).get('local_gb_used', None),
            disk_free=results['hypervisor_details'].get(
                hypervisor_id, {}).get('free_disk_gb', None),
            set_instances=hypervisor_servers,
            set_hostByName=hypervisor.get('hypervisor_hostname', ''),
        )

        if hypervisor_dict['hypervisor_type'] == 'VMware vCenter Server':
            # This hypervisor type does not run on a specific host, so
            # omit the host relationship.
            del hypervisor_dict['set_hostByName']

        hypervisors.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Hypervisor',
            data=hypervisor_dict))

    results['process_server_hypervisor_instance_name'] = server_hypervisor_instance_name
    return hypervisors


def map_servers(device, results, hostmap):
    '''Instance maps'''

    servers = []
    for server in results['servers']:
        if not server.get('id', None):
            continue

        # Backup support is optional. Guard against it not existing.
        backup_schedule_enabled = server.get('backup_schedule',
                                             {}).get('enabled', False)
        backup_schedule_daily = server.get('backup_schedule',
                                           {}).get('daily', 'DISABLED')
        backup_schedule_weekly = server.get('backup_schedule',
                                            {}).get('weekly', 'DISABLED')

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
                        private_ips.add(address.get('addr'))
                    elif address.get('OS-EXT-IPS:type') == 'floating':
                        public_ips.add(address.get('addr'))
                    else:
                        LOG.info("Address type not found for %s", address.get('addr'))
                        LOG.info("Adding %s to private_ips", address.get('addr'))
                        private_ips.add(address.get('addr'))

        # Flavor and Image IDs could be specified two different ways.
        flavor_id = server.get('flavorId', None) or \
            server.get('flavor', {}).get('id', None)

        tenant_id = server.get('tenant_id', '')

        power_state = server.get('OS-EXT-STS:power_state', 0)
        task_state = server.get('OS-EXT-STS:task_state')
        if not task_state:
            task_state = 'no task in progress'
        vm_state = server.get('OS-EXT-STS:vm_state')

        # Note: volume relations are added in volumes map below
        server_dict = dict(
            id=prepId('server-{0}'.format(server['id'])),
            title=server.get('name', server['id']),
            resourceId=server['id'],
            serverId=server['id'],  # 847424
            serverStatus=server.get('status', '').lower(),
            serverBackupEnabled=backup_schedule_enabled,
            serverBackupDaily=backup_schedule_daily,
            serverBackupWeekly=backup_schedule_weekly,
            publicIps=list(public_ips),
            privateIps=list(private_ips),
            set_flavor=prepId('flavor-{0}'.format(flavor_id)),
            set_tenant=prepId('tenant-{0}'.format(tenant_id)),
            hostId=server.get('hostId', ''),
            hostName=server.get('name', ''),
            powerState=POWER_STATE_MAP.get(power_state),
            taskState=task_state,
            vmState=vm_state,
            )

        # Some Instances are created from pre-existing volumes
        # This implies no image exists.
        image_id = None
        if 'imageId' in server:
            image_id = server['imageId']
        elif 'image' in server \
                and isinstance(server['image'], dict) \
                and 'id' in server['image']:
            image_id = server['image']['id']

        if image_id:
            server_dict['set_image'] = prepId('image-{0}'.format(image_id))

        servers.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Instance',
            data=server_dict))

    # Add hypervisor instance name to the existing server objectmaps.
    server_hypervisor_instance_name = results.get('process_server_hypervisor_instance_name')
    for om in servers:
        if om.id in server_hypervisor_instance_name:
            om.hypervisorInstanceName = server_hypervisor_instance_name[om.id]

    return servers


def map_services(device, results, hostmap):
    services = []
    zones = {}
    host_orgComponent = defaultdict(lambda: results.get('process_region_id'))

    # Find all hosts which have a nova service on them.
    for service in results['services']:
        if not service.get('id', None):
            continue

        host_id = service['host']
        try:
            hostname = hostmap.get_hostname_for_hostid(host_id)
        except InvalidHostIdException:
            LOG.error("An invalid Host ID: '%s' was provided.\n"
                      "\tPlease examine zOpenStackHostMapToId "
                      "and zOpenStackHostMapSame.", host_id)
            continue
        except Exception:
            LOG.warning("An unknown error for Host ID: '%s' occurred", host_id)
            continue

        host_base_id = re.sub(r'^host-', '', host_id)

        title = '{0}@{1} ({2})'.format(service.get('binary', ''),
                                       hostname,
                                       service.get('zone', ''))
        service_id = prepId('service-{0}-{1}-{2}'.format(
            service.get('binary', ''),
            host_base_id,
            service.get('zone', '')))
        zone_id = prepId("zone-{0}".format(service.get('zone', '')))

        host_orgComponent[host_id] = zone_id

        zones.setdefault(zone_id, ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.AvailabilityZone',
            data=dict(
                id=zone_id,
                title=service.get('zone', ''),
                set_parentOrg=results.get('process_region_id')
            )))

        # Currently, nova-api doesn't show in the nova service list.
        # Even if it does show up there in the future, I don't model
        # it as a NovaService, but rather as its own type of software
        # component.   (See below)
        if service.get('binary', '') == 'nova-api':
            continue

        services.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.NovaService',
            data=dict(
                id=service_id,
                title=title,
                binary=service.get('binary', ''),
                enabled={
                    'enabled': True,
                    'disabled': False
                }.get(service.get('status', None), False),
                operStatus={
                    'up': 'UP',
                    'down': 'DOWN'
                }.get(service.get('state', None), 'UNKNOWN'),
                set_hostedOn=host_id,
                set_orgComponent=zone_id
            )))

    # Find all hosts which have a cinder service on them
    # where cinder services are: cinder-backup, cinder-scheduler, cinder-volume
    for service in results['cinder_services']:
        # well, guest what? volume services do not have 'id' key !

        host_id = service['host']

        if host_id is None:
            zone_id = prepId("zone-{0}".format(service.get('zone', '')))
            title = '{0} ({1})'.format(
                service.get('binary', ''),
                service.get('zone', ''))
            service_id = prepId('service-{0}-{1}'.format(
                service.get('binary', ''), service.get('zone', '')))

        else:
            try:
                hostname = hostmap.get_hostname_for_hostid(host_id)
            except InvalidHostIdException:
                LOG.error("An invalid Host ID: '%s' was provided.\n"
                          "\tPlease examine zOpenStackHostMapToId "
                          "and zOpenStackHostMapSame.", host_id)
                continue
            except Exception:
                LOG.warning("An unknown error for Host ID: '%s' occurred", host_id)

            host_base_id = re.sub(r'^host-', '', host_id)
            zone_id = prepId("zone-{0}".format(service.get('zone', '')))
            title = '{0}@{1} ({2})'.format(service.get('binary', ''),
                                           hostname,
                                           service.get('zone', ''))
            service_id = prepId('service-{0}-{1}-{2}'.format(
                service.get('binary', ''), host_base_id, service.get('zone', '')))

        if host_id is not None and host_id not in host_orgComponent:
            host_orgComponent[host_id] = zone_id

        services.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.CinderService',
            data=dict(
                id=service_id,
                title=title,
                binary=service.get('binary', ''),
                enabled={
                    'enabled': True,
                    'disabled': False
                }.get(service.get('status', None), False),
                operStatus={
                    'up': 'UP',
                    'down': 'DOWN'
                }.get(service.get('state', None), 'UNKNOWN'),
                set_hostedOn=host_id,
                set_orgComponent=zone_id
            )))

    results['process_host_orgComponent'] = host_orgComponent
    results['process_zones'] = zones.values()
    return services


def map_hosts(device, results, hostmap):
    # add any user-specified hosts which we haven't already found.
    # (note: they were already added to the hostmap by preprocess_hosts, so
    # this message is just informational)
    if device.zOpenStackNovaApiHosts or device.zOpenStackExtraHosts:
        LOG.info("Finding additional hosts")

        if device.zOpenStackNovaApiHosts:
            LOG.info("  Adding zOpenStackNovaApiHosts=%s" % device.zOpenStackNovaApiHosts)
        if device.zOpenStackExtraHosts:
            LOG.info("  Adding zOpenStackExtraHosts=%s" % device.zOpenStackExtraHosts)

    LOG.debug("Modeling Hosts:")
    hosts = []
    seen_hostids = set()
    for host_id in hostmap.all_hostids():

        if host_id in seen_hostids:
            LOG.debug("  (disregarding duplicate host ID: %s)", host_id)
            continue
        seen_hostids.add(host_id)

        sources = set(hostmap.get_sources_for_hostid(host_id))

        # skip hosts which were only seen in the API urls
        for api_source in ['Nova API URL', 'Cinder API URL']:
            if api_source in sources:
                sources.remove(api_source)

        if len(sources) == 0:
            continue

        try:
            hostname = hostmap.get_hostname_for_hostid(host_id)
        except Exception:
            LOG.error("Invalid hostname for host_id: '%s'", host_id)
            LOG.error("Ensure that zOpenStackHost* properties are correct!")
            continue

        LOG.debug("  Host %s (%s) (sources=%s)", host_id, hostname, hostmap.get_sources_for_hostid(host_id))

        host_orgComponent = results.get('process_host_orgComponent')
        hosts.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Host',
            data=dict(
                id=host_id,
                title=hostname,
                hostname=hostname,
                host_ip=hostmap.get_ip_for_hostid(host_id),
                set_orgComponent=host_orgComponent[host_id],
            )))

    # nova-api host support.
    # Place it on the user-specified hosts, or also find it if it's
    # in the nova-service list (which we ignored earlier). It should not
    # be, under icehouse, at least, but just in case this changes..)
    nova_api_hosts = set(results['zOpenStackNovaApiHosts'])
    cinder_api_hosts = []
    for service in results['services']:
        if service.get('binary', '') == 'nova-api':
            if service['host'] not in nova_api_hosts:
                nova_api_hosts.add(service['host'])

    # cinder-api host support.
    cinder_api_hosts = set(results['zOpenStackCinderApiHosts'])
    for service in results['cinder_services']:
        if service.get('binary', '') == 'cinder-api':
            if service['host'] not in cinder_api_hosts:
                cinder_api_hosts.append(service['host'])

    # Look to see if the hostname or IP in the auth url corresponds
    # directly to a host we know about.  If so, add it to the nova
    # api hosts.
    known_hosts = [x.id for x in hosts]
    nova_url_host = results['nova_url_host']
    if nova_url_host and (nova_url_host in known_hosts):
        nova_api_hosts.add(nova_url_host)

    if not nova_api_hosts:
        LOG.warning("No nova-api hosts have been identified. "
                    "You must set zOpenStackNovaApiHosts to the "
                    "list of hosts upon which nova-api runs.")

    cinder_url_host = results['cinder_url_host']
    if cinder_url_host and (cinder_url_host in known_hosts):
        cinder_api_hosts.add(cinder_url_host)

    if not cinder_api_hosts:
        LOG.warning("No cinder-api hosts have been identified. "
                    "You must set zOpenStackCinderApiHosts to the "
                    "list of hosts upon which cinder-api runs.")

    results['process_cinder_api_hosts'] = cinder_api_hosts
    results['process_nova_api_hosts'] = nova_api_hosts
    return hosts


def map_extra_services(device, results, hostmap):
    services = []

    nova_api_hosts = results['process_nova_api_hosts']
    for host_id in sorted(nova_api_hosts):
        hostname = hostmap.get_hostname_for_hostid(host_id)
        host_base_id = re.sub(r'^host-', '', host_id)
        title = '{0}@{1} ({2})'.format('nova-api', hostname, device.zOpenStackRegionName)
        nova_api_id = prepId('service-nova-api-{0}-{1}'.format(host_base_id, device.zOpenStackRegionName))

        services.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.NovaApi',
            data=dict(
                id=nova_api_id,
                title=title,
                binary='nova-api',
                set_hostedOn=host_id,
                set_orgComponent=results.get('process_region_id')
            )))

    # hosts
    cinder_api_hosts = results['process_cinder_api_hosts']
    for host_id in cinder_api_hosts:
        hostname = hostmap.get_hostname_for_hostid(host_id)
        host_base_id = re.sub(r'^host-', '', host_id)
        title = '{0}@{1} ({2})'.format('cinder-api', hostname, device.zOpenStackRegionName)
        cinder_api_id = prepId('service-cinder-api-{0}-{1}'.format(host_base_id, device.zOpenStackRegionName))

        services.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.CinderApi',
            data=dict(
                id=cinder_api_id,
                title=title,
                binary='cinder-api',
                set_hostedOn=host_id,
                set_orgComponent=results.get('process_region_id')
            )))
    return services


def map_agents(device, results, hostmap):
    agents = []
    for agent in results['agents']:
        if not agent.get('id', None):
            continue

        agent_hostid = agent['host']

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
        try:
            hostname = hostmap.get_hostname_for_hostid(agent['host'])
        except InvalidHostIdException:
            LOG.error("An invalid Host ID: '%s' was provided.\n"
                      "\tPlease examine zOpenStackHostMapToId and "
                      "zOpenStackHostMapSame.", agent_hostid)
            continue
        except Exception:
            LOG.warning("An unknown error for Host ID: "
                        "'%s' occurred", agent_hostid)

        title = '{0}@{1}'.format(agent.get('agent_type', ''), hostname)

        agents.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.NeutronAgent',
            data=dict(
                id=prepId('agent-{0}'.format(agent['id'])),
                title=title,
                binary=agent.get('binary', ''),
                enabled=agent.get('admin_state_up', False),
                operStatus={
                    True: 'UP',
                    False: 'DOWN'
                }.get(agent.get('alive', None), 'UNKNOWN'),

                agentId=agent['id'],
                type=agent.get('agent_type', ''),

                set_routers=l3_agent_routers,
                set_subnets=agent_subnets,
                set_networks=agent_networks,
                set_hostedOn=agent_hostid,
                set_orgComponent=results.get('process_host_orgComponent', {}).get(agent_hostid),
            )))
    return agents


def map_networks(device, results, hostmap):
    networks = []
    for net in results['networks']:
        if not net.get('id', None):
            continue

        networks.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Network',
            data=dict(
                id=prepId('network-{0}'.format(net['id'])),
                netId=net['id'],
                title=net.get('name', net['id']),
                admin_state_up=net.get('admin_state_up', False),         # true/false
                netExternal=net.get('router:external', False),           # true/false
                set_tenant=prepId('tenant-{0}'.format(net.get('tenant_id', ''))),
                netStatus=net.get('status', 'UNKNOWN'),                      # ACTIVE
                netType=net.get('provider:network_type', 'UNKNOWN').upper()  # local/global
            )))
    return networks


def map_subnets(device, results, hostmap):
    subnets = []
    for subnet in results['subnets']:
        if not subnet.get('id', None):
            continue

        subnets.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Subnet',
            data=dict(
                cidr=subnet.get('cidr', ''),
                dns_nameservers=subnet.get('dns_nameservers', []),
                gateway_ip=subnet.get('gateway_ip', ''),
                id=prepId('subnet-{0}'.format(subnet['id'])),
                set_network=prepId('network-{0}'.format(subnet.get('network_id', ''))),
                set_tenant=prepId('tenant-{0}'.format(subnet.get('tenant_id', ''))),
                subnetId=subnet['id'],
                title=subnet.get('name', subnet['id']),
                )))
    return subnets


def map_ports(device, results, hostmap):
    ports = []
    device_subnet_list = defaultdict(set)
    for port in results['ports']:
        if not port.get('id', None):
            continue
        port_dict = dict()
        # Fetch the subnets for later use
        raw_subnets = get_subnets_from_fixedips(port.get('fixed_ips', []))
        port_subnets = [prepId('subnet-{}'.format(x)) for x in raw_subnets]
        if port_subnets:
            port_dict['set_subnets'] = port_subnets
        # Prepare the device_subnet_list data for later use.
        port_router_id = port.get('device_id')
        if port_router_id:
            device_subnet_list[port_router_id] = \
                device_subnet_list[port_router_id].union(raw_subnets)
        port_tenant = None
        if port.get('tenant_id', None):
            port_tenant = prepId('tenant-{0}'
                                 .format(port.get('tenant_id', '')))
            port_dict['set_tenant'] = port_tenant

        device_owner = port.get('device_owner', '')
        port_instance = get_port_instance(device_owner,
                                          port.get('device_id', ''))
        if port_instance:
            port_instance = prepId(port_instance)
            port_dict['set_instance'] = port_instance
        port_network = port.get('network_id', None)
        if port_network:
            port_network = prepId('network-{0}'.format(port_network))
            port_dict['set_network'] = port_network

        port_router = None
        if 'router_interface' in device_owner and port_router_id:
            port_router = prepId('router-{0}'.format(port_router_id))
            port_dict['set_router'] = port_router

        ports.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Port',
            data=dict(
                admin_state_up=port.get('admin_state_up', False),
                device_owner=device_owner,
                fixed_ip_list=get_port_fixedips(port.get('fixed_ips', [])),
                id=prepId('port-{0}'.format(port['id'])),
                mac_address=port.get('mac_address', '').upper(),
                portId=port['id'],
                status=port.get('status', 'UNKNOWN'),
                title=port.get('name', port['id']),
                vif_type=port.get('binding:vif_type', 'UNKNOWN'),
                **port_dict
                )))
    results['process_device_subnet_list'] = device_subnet_list
    return ports


def map_routers(device, results, hostmap):
    routers = []
    for router in results['routers']:
        if not router.get('id', None):
            continue

        _gateways = set()
        _network_id = None
        device_subnet_list = results['process_device_subnet_list']
        # This should be all of the associated subnets
        _subnets = device_subnet_list[router['id']]

        # Get the External Gateway Data
        external_gateway_info = router.get('external_gateway_info')
        if external_gateway_info:
            _network_id = external_gateway_info.get('network_id', '')
            for _ip in external_gateway_info.get('external_fixed_ips', []):
                _gateways.add(_ip.get('ip_address', None))
                # This should not be required, but it doesn't hurt set()
                _subnets.add(_ip.get('subnet_id', None))

        _network = None
        if _network_id:
            _network = 'network-{0}'.format(_network_id)

        router_dict = dict(
            admin_state_up=router.get('admin_state_up', False),
            gateways=list(_gateways),
            id=prepId('router-{0}'.format(router['id'])),
            routerId=router['id'],
            routes=list(router.get('routes', [])),
            set_tenant=prepId('tenant-{0}'.format(router.get('tenant_id', ''))),
            status=router.get('status', 'UNKNOWN'),
            title=router.get('name', router['id']),
        )
        if _network:
            router_dict['set_network'] = prepId(_network)
        if _subnets:
            router_dict['set_subnets'] = [prepId('subnet-{0}'.format(x))
                                          for x in _subnets]
        routers.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Router',
            data=router_dict))

    return routers


def map_floatingips(device, results, hostmap):
    floatingips = []
    for floatingip in results['floatingips']:
        if not floatingip.get('id', None):
            continue

        floatingip_dict = dict(
            floatingipId=floatingip['id'],
            fixed_ip_address=floatingip.get('fixed_ip_address', ''),
            floating_ip_address=floatingip.get('floating_ip_address', ''),
            id=prepId('floatingip-{0}'.format(floatingip['id'])),
            set_network=prepId('network-{0}'.format(floatingip.get('floating_network_id', ''))),
            set_tenant=prepId('tenant-{0}'.format(floatingip.get('tenant_id', ''))),
            status=floatingip.get('status', 'UNKNOWN'),
            )

        if floatingip.get('router_id'):
            floatingip_dict['set_router'] = prepId('router-{0}'.format(floatingip.get('router_id', '')))

        if floatingip.get('port_id'):
            floatingip_dict['set_port'] = prepId('port-{0}'.format(floatingip.get('port_id', '')))

        floatingips.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.FloatingIp',
            data=floatingip_dict))

    return floatingips


def map_voltypes(device, results, hostmap):
    # volume Types
    voltypes = []
    for voltype in results['volumetypes']:
        if not voltype.get('id'):
            continue

        voltypes.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.VolType',
            data=dict(
                id=prepId('volType-{0}'.format(voltype['id'])),
                title=voltype.get('name', 'UNKNOWN'),
            )))

    results['process_voltypes'] = voltypes
    return voltypes


def map_volumes(device, results, hostmap):
    # volumes
    volumes = []
    voltypes = results.get('process_voltypes')
    for volume in results['volumes']:
        if not volume.get('id'):
            continue

        attachment = volume.get('attachments', [])
        instanceId = ''
        # each openstack volume can only attach to one instance
        if len(attachment) > 0:
            instanceId = attachment[0].get('server_id', '')

        # if not defined, volume.get('volume_type', '') returns ''
        voltypeid = [vtype.id for vtype in voltypes
                     if volume.get('volume_type', '') == vtype.title]

        volume_dict = dict(
            id=prepId('volume-{0}'.format(volume['id'])),
            title=volume.get('name', ''),
            volumeId=volume['id'],  # 847424
            avzone=volume.get('availability_zone', ''),
            created_at=volume.get('created_at', '').replace('T', ' '),
            sourceVolumeId=volume.get('source_volid', ''),
            host=volume.get('os-vol-host-attr:host', ''),
            size=volume.get('size', 0),
            bootable=volume.get('bootable', 'FALSE').upper(),
            status=volume.get('status', 'UNKNOWN').upper(),
        )
        # set tenant only when volume['attachments'] is not empty
        if len(instanceId) > 0:
            volume_dict['set_instance'] = prepId('server-{0}'.format(
                instanceId))
        # set instance only when volume['tenant_id'] is not empty
        if volume.get('os-vol-tenant-attr:tenant_id'):
            volume_dict['set_tenant'] = prepId('tenant-{0}'.format(
                volume.get('os-vol-tenant-attr:tenant_id', '')))
        if len(voltypeid) > 0:
            volume_dict['set_volType'] = voltypeid[0]
        if volume.get('os-vol-tenant-attr:tenant_id'):
            volume_dict['set_tenant'] = prepId('tenant-{0}'.format(
                volume.get('os-vol-tenant-attr:tenant_id')))

        volumes.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Volume',
            data=volume_dict))
    return volumes


def map_volsnapshots(device, results, hostmap):
    volsnapshots = []
    for snapshot in results['volsnapshots']:
        if not snapshot.get('id', None):
            continue

        volsnap_dict = dict(
            id=prepId('snapshot-{0}'.format(snapshot['id'])),
            title=snapshot.get('name', ''),
            created_at=snapshot.get('created_at', '').replace('T', ' '),
            size=snapshot.get('size', 0),
            description=snapshot.get('description', ''),
            status=snapshot.get('status', 'UNKNOWN').upper(),
        )
        if snapshot.get('volume_id', None):
            volsnap_dict['set_volume'] = \
                prepId('volume-{0}'.format(snapshot.get('volume_id', '')))
        if snapshot.get('os-extended-snapshot-attributes:project_id', None):
            volsnap_dict['set_tenant'] = \
                prepId('tenant-{0}'.format(snapshot.get(
                    'os-extended-snapshot-attributes:project_id', '')))
        volsnapshots.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.VolSnapshot',
            data=volsnap_dict))
    return volsnapshots


def map_pools(device, results, hostmap):
    pools = []
    for pool in results['volume_pools']:
        # does pool have id?

        # pool name from Ceph looks like: 'block1@ceph#ceph
        # the right most (or the middle part?) part is volume type.
        # the middle part is Ceph cluster name?

        allocated_capacity = pool.get('capabilities', {}).get('allocated_capacity_gb', False)
        if not allocated_capacity:
            allocated_capacity = ''
        else:
            allocated_capacity = str(allocated_capacity) + ' GB',
        free_capacity = pool.get('capabilities', {}).get('free_capacity_gb', False)
        if not free_capacity:
            free_capacity = ''
        else:
            free_capacity = str(free_capacity) + ' GB',
        total_capacity = pool.get('capabilities', {}).get('total_capacity_gb', False)
        if not total_capacity:
            total_capacity = ''
        else:
            total_capacity = str(total_capacity) + ' GB',

        pools.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Pool',
            data=dict(
                id=prepId('pool-{0}'.format(pool.get('name'))),
                title=pool.get('name', ''),
                qos_support=pool.get('capabilities', {}).get('QoS_support', False),
                allocated_capacity=allocated_capacity,
                free_capacity=free_capacity,
                total_capacity=total_capacity,
                driver_version=pool.get('capabilities', {}).get('driver_version', ''),
                location=pool.get('capabilities', {}).get('location_info', ''),
                reserved_percentage=str(pool.get('capabilities', {}).get('reserved_percentage', 0)) + '%',
                storage_protocol=pool.get('capabilities', {}).get('storage_protocol', 0),
                vendor_name=pool.get('capabilities', {}).get('vendor_name', 0),
                volume_backend=pool.get('capabilities', {}).get('volume_backend', 0),
                )))
        return pools


def map_quotas(device, results, hostmap):
    quotas = []
    for quota_key in results['quotas'].keys():
        quota = results['quotas'][quota_key]

        # Find and use the tenant that corresponds to this quota:
        q_tenant = None
        for _ten in results.get('process_quota_tenants'):
            if _ten.get('id') == quota_key:
                q_tenant = _ten
                break

        if not q_tenant:
            continue

        quotas.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Quota',
            data=dict(
                id=prepId('quota-{0}'.format(quota_key)),
                tenant_name=q_tenant['name'],
                volumes=quota.get('volumes', 0),
                snapshots=quota.get('snapshots', 0),
                bytes=quota.get('gigabytes', 0),
                backups=quota.get('backups', 0),
                backup_bytes=quota.get('backup_gigabytes', 0),
                set_tenant=prepId('tenant-{0}'.format(quota_key)),
                )))
    return quotas


def map_api_endpoints(device, results, hostmap):
    # API Endpoints
    api_endpoints = []
    api_endpoints.append(ObjectMap(
        modname='ZenPacks.zenoss.OpenStackInfrastructure.ApiEndpoint',
        data=dict(
            id=prepId('apiendpoint-zOpenStackAuthUrl'),
            title=device.zOpenStackAuthUrl,
            service_type='identity',
            url=device.zOpenStackAuthUrl,
            source='zOpenStackAuthUrl'
        )
    ))

    for api_endpoint in device.zOpenStackExtraApiEndpoints:
        try:
            service_type, url = api_endpoint.split(':')
            url = url.lstrip()
        except ValueError:
            LOG.error("Ignoring invalid value in zOpenStackExtraApiEndpoints: %s", api_endpoint)

        # create a component id for the api endpoint, based on the url
        # and service type.
        h = hashlib.new()
        h.update(service_type)
        h.update(url)
        id_ = h.hexdigest()
        api_endpoints.append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.ApiEndpoint',
            data=dict(
                id=prepId('apiendpoint-%s' % id_),
                title=url,
                service_type=service_type,
                url=url,
                source='zOpenStackExtraApiEndpoints'
            )
        ))
    # Ideally we should also include the endpoints reported by
    # keystone and model them here, but there are some issues
    # in txapiclient that make this difficult at this time.
    return api_endpoints
