##########################################################################
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
LOG = logging.getLogger('zen.OpenStackInfrastructure')

from collections import defaultdict
import hashlib
import itertools
import json
import os
import re
from urlparse import urlparse

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.error import ConnectionRefusedError, TimeoutError

from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
from Products.ZenUtils.Time import isoToTimestamp, LocalDateTime
from Products.ZenUtils.Utils import prepId

from ZenPacks.zenoss.OpenStackInfrastructure.hostmap import HostMap, InvalidHostIdException
from ZenPacks.zenoss.OpenStackInfrastructure.utils import (
    add_local_lib_path,
    filter_FQDNs,
    getNetSubnetsGws_from_GwInfo,
    get_port_fixedips,
    get_port_instance,
    get_subnets_from_fixedips,
    zenpack_path,
)

add_local_lib_path()

from apiclients.session import SessionManager
from apiclients.txapiclient import (
    KeystoneClient,
    NovaClient,
    NeutronClient,
    CinderClient,
)
from apiclients.exceptions import APIClientError, NotFoundError

# https://github.com/openstack/nova/blob/master/nova/compute/power_state.py
POWER_STATE_MAP = {
    0: 'pending',
    1: 'running',
    3: 'paused',
    4: 'shutdown',
    6: 'crashed',
    7: 'suspended',
}


def getHostOrgComponent(host_id, results):
    """
    Get zone-id related to host.

    Iterate through Nova and Cinder services to get zone related to host_id
    Note: There are some services that can be related to multiple zones so
          the result somewhat deterministic, based on the order that they
          were processed in older versions of the modeler.  Last nova
          service wins out, and if no nova service matches, then the first
          cinder service that matches, and failing that, the region.

    """
    for service in reversed(results['services']):
        zone_name = service.get('zone')
        if zone_name and service['host'] == host_id:
            return prepId("zone-{0}".format(service.get('zone')))

    for service in results['cinder_services']:
        zone_name = service.get('zone')
        if zone_name and service['host'] == host_id:
            return prepId("zone-{0}".format(service.get('zone')))

    return results.get('process_region_id')


def getServiceZoneNameId(region_name, service):
    """Get zone from service.

       @Returns a tuple: (zone_name, zone_id)
       Services should have a zone name but in case missing, set to region
    """
    zone_name = service.get('zone')
    if not zone_name:
        zone_name = region_name
        zone_id = prepId("region-{0}".format(zone_name))
    else:
        zone_id = prepId("zone-{0}".format(zone_name))

    return zone_name, zone_id


class OpenStackInfrastructure(PythonPlugin):
    deviceProperties = PythonPlugin.deviceProperties + (
        'zCommandUsername',
        'zCommandPassword',
        'zOpenStackProjectId',
        'zOpenStackUserDomainName',
        'zOpenStackProjectDomainName',
        'zOpenStackAuthUrl',
        'zOpenStackRegionName',
        'zOpenStackNovaApiHosts',
        'zOpenStackCinderApiHosts',
        'zOpenStackExtraHosts',
        'zOpenStackHostMapToId',
        'zOpenStackHostMapSame',
        'get_host_mappings',
        'zOpenStackExtraApiEndpoints',
    )

    # -------------------------------------------------------------------------
    # ----------------- Mapping functions for process() -----------------------
    # -------------------------------------------------------------------------
    def map_tenants(self, device, results):
        """
        Map tenants list.

        Sample tenant::

           {'enabled': True,
            'description': 'admin tenant',
            'name': 'admin',
            'id': '313da8e3ab19478e82be9c50e6b1a04b'
           }

        """
        tenants = []
        quota_tenants = []

        for tenant in results['tenants']:
            if tenant.get('enabled') is not True:
                continue
            if not tenant.get('id'):
                continue

            quota_tenant = dict(name=tenant.get('name', tenant['id']),
                                id=tenant['id'])
            quota_tenants.append(quota_tenant)

            tenants.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Tenant',
                data=dict(
                    id=prepId('tenant-{0}'.format(tenant['id'])),
                    title=tenant.get('name', tenant['id']),
                    description=tenant.get('description'),
                    tenantId=tenant['id']
                )))

        results['process_quota_tenants'] = quota_tenants
        return tenants

    def map_regions(self, device, results):
        """Map the OpenStack Region via device.zOpenStackRegionName"""
        region_id = prepId("region-{0}".format(device.zOpenStackRegionName))
        region = ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Region',
            data=dict(
                id=region_id,
                title=device.zOpenStackRegionName
            ))
        results['process_region_id'] = region_id
        return [region]

    def map_zones(self, device, results):
        zones = []
        zone_ids = []

        for service in results['services'] + results['cinder_services']:
            zone_name = service.get('zone')
            if not zone_name or not service.get('id'):
                continue
            _zid = prepId("zone-{0}".format(zone_name))
            if _zid in zone_ids:
                continue

            zone_ids.append(_zid)
            zones.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.AvailabilityZone',
                data=dict(
                    id=_zid,
                    title=zone_name,
                    set_parentOrg=results.get('process_region_id')
                )))

        return zones

    def map_flavors(self, device, results):
        """
        Map flavors list from NovaClient:/flavors API call.

        Sample flavor::

            {'OS-FLV-DISABLED:disabled': False,
             'OS-FLV-EXT-DATA:ephemeral': 0,
             'disk': 1,
             'id': '1',
             'links': [{'href': 'http://10.87.209.165:8774/v2.1/313da8e3ab19478e82be9c50e6b1a04b/flavors/1',
                        'rel': 'self'},
                        {'href': 'http://10.87.209.165:8774/313da8e3ab19478e82be9c50e6b1a04b/flavors/1',
                        'rel': 'bookmark'}],
             'name': 'm1.tiny',
             'os-flavor-access:is_public': True,
             'ram': 512,
             'rxtx_factor': 1.0,
             'swap': '',
             'vcpus': 1}

        """
        flavors = []
        for flavor in results['flavors']:
            if not flavor.get('id'):
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

    def map_images(self, device, results):
        """
        Map image list from NovaClient:/images(detailed=True) API call.

        Sample image::

            {'OS-EXT-IMG-SIZE:size': 13267968,
             'created': '2018-10-31T19:52:53Z',
             'id': 'fc6607b7-ccbf-4834-be6c-0a09faef19ec',
             'links': [{'href': 'http://10.87.209.165:8774/v2.1/313da8e3ab19478e82be9c50e6b1a04b/images/fc6607b7-ccbf-4834-be6c-0a09faef19ec',
                        'rel': 'self'},
                       {'href': 'http://10.87.209.165:8774/313da8e3ab19478e82be9c50e6b1a04b/images/fc6607b7-ccbf-4834-be6c-0a09faef19ec',
                         'rel': 'bookmark'},
                       {'href': 'http://10.87.209.165:9292/images/fc6607b7-ccbf-4834-be6c-0a09faef19ec',
                         'rel': 'alternate',
                         'type': 'application/vnd.openstack.image'}],
             'metadata': {},
             'minDisk': 0,
             'minRam': 0,
             'name': 'cirros',
             'progress': 100,
             'status': 'ACTIVE',
             'updated': '2018-10-31T19:52:53Z'}

        """
        images = []
        for image in results['images']:
            if not image.get('id'):
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

    def map_hypervisors(self, device, results):
        """
        Map hypervisor list from the
        nova:/os-hypervisors/{param[hypervisor_match]}/servers  API call

        Sample hypervisor::

            {
             'cpu_info': <a long unicode string>,
             'current_workload': 0,
             'disk_available_least': 46,
             'free_disk_gb': 49,
             'free_ram_mb': 7679,
             'host_ip': u'10.87.209.165',
             'hypervisor_hostname': u'osi-p',
             'hypervisor_type': u'QEMU',
             'hypervisor_version': 2010000,
             'id': 1,
             'local_gb': 49,
             'local_gb_used': 0,
             'memory_mb': 8191,
             'memory_mb_used': 512,
             'running_vms': 0,
             'service': {u'disabled_reason': None, u'host': u'osi-p', u'id': 6},
             'state': u'up',
             'status': u'enabled',
             'vcpus': 7,
             'vcpus_used': 0}

        """
        hypervisor_type = {}
        hypervisor_version = {}
        for hypervisor in results['hypervisors_detailed']:
            if not hypervisor.get('id'):
                continue

            hypervisor_id = prepId("hypervisor-{0}".format(hypervisor['id']))

            hypervisor_type[hypervisor_id] = hypervisor.get('hypervisor_type')
            hypervisor_version[hypervisor_id] = hypervisor.get('hypervisor_version')

            if hypervisor_type[hypervisor_id] is None:
                # if results['hypervisors_detailed'] did not give us hypervisor type,
                # hypervisor version, try results['hypervisors_details']
                hypervisor_type[hypervisor_id] = \
                    results['hypervisor_details'][hypervisor_id].get(
                        'hypervisor_type')

            if hypervisor_version[hypervisor_id] is None:
                # if results['hypervisors_detailed'] did not give us version,
                # hypervisor version, try results['hypervisors_details']
                hypervisor_version[hypervisor_id] = \
                    results['hypervisor_details'][hypervisor_id].get(
                        'hypervisor_version')

            # Reformat the version string.
            if hypervisor_version[hypervisor_id] is not None:
                hypervisor_version[hypervisor_id] = '.'.join(
                    str(hypervisor_version[hypervisor_id]).split('00'))

        hypervisors = []
        server_hypervisor_instance_name = {}
        for hypervisor in results['hypervisors']:
            if not hypervisor.get('id'):
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
                hypervisor_version=hypervisor_version.get(hypervisor_id),
                # hypervisor state: power state, UP/DOWN
                hstate=hypervisor.get('state', 'unknown').upper(),
                # hypervisor status: ENABLED/DISABLED
                hstatus=hypervisor.get('status', 'unknown').upper(),
                # hypervisor ip: internal ip address
                host_ip=results['hypervisor_details'].get(
                    hypervisor_id, {}).get('host_ip'),
                vcpus=results['hypervisor_details'].get(
                    hypervisor_id, {}).get('vcpus'),
                vcpus_used=results['hypervisor_details'].get(
                    hypervisor_id, {}).get('vcpus_used'),
                memory=results['hypervisor_details'].get(
                    hypervisor_id, {}).get('memory_mb'),
                memory_used=results['hypervisor_details'].get(
                    hypervisor_id, {}).get('memory_mb_used'),
                memory_free=results['hypervisor_details'].get(
                    hypervisor_id, {}).get('free_ram_mb'),
                disk=results['hypervisor_details'].get(
                    hypervisor_id, {}).get('local_gb'),
                disk_used=results['hypervisor_details'].get(
                    hypervisor_id, {}).get('local_gb_used'),
                disk_free=results['hypervisor_details'].get(
                    hypervisor_id, {}).get('free_disk_gb'),
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

    def map_servers(self, device, results):
        """
        Map 'Instance' servers from nova:/servers/detailed API call.

        Sample server::

        {
            "OS-EXT-STS:power_state": 1,
            "OS-EXT-STS:task_state": null,
            "OS-EXT-STS:vm_state": "active",
            "accessIPv4": "1.2.3.4",
            "accessIPv6": "80fe::",
            "addresses": {
                "private": [
                    {"OS-EXT-IPS-MAC:mac_addr": "aa:bb:cc:dd:ee:ff",
                     "OS-EXT-IPS:type": "fixed",
                     "addr": "192.168.0.3",
                     "version": 4
                    }
                ]
            },
            "created": "2017-10-10T15:49:08Z",
            "flavor": {"disk": 1,
                       "original_name": "m1.tiny.specs",
                       "vcpus": 1
                       },
            "hostId": "2091634baaccdc4c5a1d57069c833e402921df696b7f970791b12ec6",
            "host_status": "UP",
            "id": "569f39f9-7c76-42a1-9c2d-8394e2638a6d",
            "image": {
                "id": "70a599e0-31e7-49b7-b260-868f441e862b",
                 ...
            },
            "key_name": null,
            "locked": false,
            "metadata": { "My Server Name": "Apache1" },
            "name": "new-server-test",
            "os-extended-volumes:volumes_attached": [],
            "progress": 0,
            "security_groups": [ { "name": "default" } ],
            "status": "ACTIVE",
            "tags": [],
            "tenant_id": "6f70656e737461636b20342065766572",
            "trusted_image_certificates": [
                "0b5d2c72-12cc-4ba6-a8d7-3ff5cc1d8cb8",
                "674736e3-f25c-405c-8362-bbf991e0ce0a"
            ],
            "updated": "2017-10-10T15:49:09Z",
            "user_id": "fake"
        }

        """
        servers = []
        for server in results['servers']:
            if not server.get('id'):
                continue
            server_uid = server['id']

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
                        ip_addr = address.get('addr')
                        if address.get('OS-EXT-IPS:type') == 'fixed':
                            private_ips.add(ip_addr)
                        elif address.get('OS-EXT-IPS:type') == 'floating':
                            public_ips.add(ip_addr)
                        else:
                            message = ("Address type not found for {0}.\n"
                                       "Adding {0} to private_ips "
                                       "for server: {1}"
                                       ).format(ip_addr, server_uid)

                            LOG.info(message)
                            private_ips.add(ip_addr)

            flavor = server.get('flavor', {}).get('id')
            if flavor:
                flavor_id = prepId('flavor-{0}'.format(flavor))

            tenant = server.get('tenant_id')
            if tenant:
                tenant_id = prepId('tenant-{0}'.format(tenant))

            power_state = server.get('OS-EXT-STS:power_state', 0)
            task_state = server.get('OS-EXT-STS:task_state')
            if not task_state:
                task_state = 'no task in progress'
            vm_state = server.get('OS-EXT-STS:vm_state')

            # Note: volume relations are added in volumes map below
            server_dict = dict(
                id=prepId('server-{0}'.format(server_uid)),
                title=server.get('name', server_uid),
                resourceId=server_uid,
                serverId=server_uid,
                serverStatus=server.get('status', '').lower(),
                serverBackupEnabled=backup_schedule_enabled,
                serverBackupDaily=backup_schedule_daily,
                serverBackupWeekly=backup_schedule_weekly,
                publicIps=list(public_ips),
                privateIps=list(private_ips),
                set_flavor=flavor_id,
                set_tenant=tenant_id,
                hostId=server.get('hostId', ''),
                hostName=server.get('name', ''),
                powerState=POWER_STATE_MAP.get(power_state),
                taskState=task_state,
                vmState=vm_state,
                )

            # Some Instances are created from pre-existing volumes
            # This implies no image may exists.
            image = server.get('image')
            if image:
                image_id = image.get('id')
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

    def map_hosts(self, device, results):
        """
        Map hosts:

            * Add any user-specified hosts which we haven't already found.
            * Note: Hosts were already added to the hostmap by preprocess_hosts.
                    This method further augments that hostmap data.

        """

        if device.zOpenStackNovaApiHosts or device.zOpenStackExtraHosts:
            LOG.info("Finding additional hosts")

            if device.zOpenStackNovaApiHosts:
                LOG.info("  Adding zOpenStackNovaApiHosts=%s" % device.zOpenStackNovaApiHosts)
            if device.zOpenStackExtraHosts:
                LOG.info("  Adding zOpenStackExtraHosts=%s" % device.zOpenStackExtraHosts)

        LOG.debug("Modeling Hosts:")
        hostmap = results.get('hostmap')
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

            hosts.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Host',
                data=dict(
                    id=host_id,
                    title=hostname,
                    hostname=hostname,
                    host_ip=hostmap.get_ip_for_hostid(host_id),
                    set_orgComponent=getHostOrgComponent(host_id, results),
                )))

        # nova-api host support.
        # Place it on the user-specified hosts, or also find it if it's
        # in the nova-service list (which we ignored earlier). It should not
        # be, under icehouse, at least, but just in case this changes..)
        nova_api_hosts = set(results['zOpenStackNovaApiHosts'])
        for service in results['services']:
            if service.get('binary') == 'nova-api':
                if service['host'] not in nova_api_hosts:
                    nova_api_hosts.add(service['host'])

        # cinder-api host support.
        cinder_api_hosts = set(results['zOpenStackCinderApiHosts'])
        for service in results['cinder_services']:
            if service.get('binary') == 'cinder-api':
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

        results['process_nova_api_hosts'] = nova_api_hosts

        cinder_url_host = results['cinder_url_host']
        if cinder_url_host and (cinder_url_host in known_hosts):
            cinder_api_hosts.add(cinder_url_host)

        if not cinder_api_hosts:
            LOG.warning("No cinder-api hosts have been identified. "
                        "You must set zOpenStackCinderApiHosts to the "
                        "list of hosts upon which cinder-api runs.")

        results['process_cinder_api_hosts'] = cinder_api_hosts

        return hosts

    def map_nova_services(self, device, results):
        """
        Map services list that come from nova:/os-services API call.

        Sample service::

            {
                "id": 1,
                "binary": "nova-scheduler",
                "disabled_reason": "test1",
                "host": "host-osi8",
                "state": "up",
                "status": "disabled",
                "updated_at": "2012-10-29T13:42:02.000000",
                "forced_down": false,
                "zone": "internal"
            },

        """
        services = []

        # Find all hosts which have a nova service on them.
        for service in results['services']:
            if not service.get('id'):
                continue

            host_id = service['host']
            hostmap = results.get('hostmap')
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

            zone_name, zone_id = getServiceZoneNameId(device.zOpenStackRegionName, service)
            binary_name = service.get('binary')
            title = '{0}@{1} ({2})'.format(binary_name,
                                           hostname,
                                           zone_name)
            service_id = prepId('service-{0}-{1}-{2}'.format(
                binary_name,
                host_base_id,
                zone_name))

            # Currently, nova-api doesn't show in the nova service list.
            # Even if it does show up there in the future, I don't model
            # it as a NovaService, but rather as its own type of software
            # component.   (See below)
            if binary_name == 'nova-api':
                continue

            services.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.NovaService',
                data=dict(
                    id=service_id,
                    title=title,
                    binary=binary_name,
                    enabled={
                        'enabled': True,
                        'disabled': False
                    }.get(service.get('status'), False),
                    operStatus={
                        'up': 'UP',
                        'down': 'DOWN'
                    }.get(service.get('state'), 'UNKNOWN'),
                    set_hostedOn=host_id,
                    set_orgComponent=zone_id
                )))

        # Append nova_api_hosts to services here.
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

        return services

    def map_cinder_services(self, device, results):
        services = []
        hostmap = results.get('hostmap')

        # Find all hosts which have a cinder service on them
        # where cinder services are: cinder-backup, cinder-scheduler, cinder-volume
        for service in results['cinder_services']:
            # well, guest what? volume services do not have 'id' key !

            host_id = service['host']
            zone_name, zone_id = getServiceZoneNameId(device.zOpenStackRegionName, service)
            binary_name = service.get('binary')

            if host_id is None:
                title = '{0} ({1})'.format(
                    binary_name,
                    zone_name)
                service_id = prepId('service-{0}-{1}'.format(
                    binary_name, zone_name))

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
                    continue

                host_base_id = re.sub(r'^host-', '', host_id)
                title = '{0}@{1} ({2})'.format(binary_name,
                                               hostname,
                                               zone_name)
                service_id = prepId('service-{0}-{1}-{2}'.format(binary_name,
                                                                 host_base_id,
                                                                 zone_name))

            services.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.CinderService',
                data=dict(
                    id=service_id,
                    title=title,
                    binary=binary_name,
                    enabled={
                        'enabled': True,
                        'disabled': False
                    }.get(service.get('status'), False),
                    operStatus={
                        'up': 'UP',
                        'down': 'DOWN'
                    }.get(service.get('state'), 'UNKNOWN'),
                    set_hostedOn=host_id,
                    set_orgComponent=zone_id
                )))

        # Append cinder_api_hosts to services here.
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

    def map_agents(self, device, results):
        """
        Map agents list that comes from neutron:/v2.0/agents.json API call.

        Sample data::

        """
        hostmap = results.get('hostmap')

        agents = []
        for agent in results['agents']:
            if not agent.get('id'):
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
            # ------------------------------------------------------------------
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

            # ------------------------------------------------------------------
            # Divine the availability_zone
            # ------------------------------------------------------------------
            availability_zone = agent.get('availability_zone')
            if availability_zone:
                zone_id = prepId("zone-{0}".format(availability_zone))
            else:
                zone_id = getHostOrgComponent(agent_hostid, results)

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
                    }.get(agent.get('alive'), 'UNKNOWN'),

                    agentId=agent['id'],
                    type=agent.get('agent_type', ''),

                    set_routers=l3_agent_routers,
                    set_subnets=agent_subnets,
                    set_networks=agent_networks,
                    set_hostedOn=agent_hostid,
                    set_orgComponent=zone_id,
                )))
        return agents

    def map_networks(self, device, results):
        networks = []
        for net in results['networks']:
            if not net.get('id'):
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

    def map_subnets(self, device, results):
        subnets = []
        for subnet in results['subnets']:
            if not subnet.get('id'):
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

    def map_ports(self, device, results):
        ports = []
        device_subnet_list = defaultdict(set)
        for port in results['ports']:
            if not port.get('id'):
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
            if port.get('tenant_id'):
                port_tenant = prepId('tenant-{0}'
                                     .format(port.get('tenant_id', '')))
                port_dict['set_tenant'] = port_tenant

            device_owner = port.get('device_owner', '')
            port_instance = get_port_instance(device_owner,
                                              port.get('device_id', ''))
            if port_instance:
                port_instance = prepId(port_instance)
                port_dict['set_instance'] = port_instance
            port_network = port.get('network_id')
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

    def map_routers(self, device, results):
        routers = []
        for router in results['routers']:
            if not router.get('id'):
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
                    _gateways.add(_ip.get('ip_address'))
                    # This should not be required, but it doesn't hurt set()
                    _subnets.add(_ip.get('subnet_id'))

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

    def map_floatingips(self, device, results):
        floatingips = []
        for floatingip in results['floatingips']:
            if not floatingip.get('id'):
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

    def map_voltypes(self, device, results):
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

    def map_volumes(self, device, results):
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
                backend=volume.get('os-vol-host-attr:host', ''),
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

    def map_volumesnapshots(self, device, results):
        volumesnapshots = []
        for snapshot in results['volsnapshots']:
            if not snapshot.get('id'):
                continue

            volsnap_dict = dict(
                id=prepId('snapshot-{0}'.format(snapshot['id'])),
                title=snapshot.get('name', ''),
                created_at=snapshot.get('created_at', '').replace('T', ' '),
                size=snapshot.get('size', 0),
                description=snapshot.get('description', ''),
                status=snapshot.get('status', 'UNKNOWN').upper(),
            )
            if snapshot.get('volume_id'):
                volsnap_dict['set_volume'] = \
                    prepId('volume-{0}'.format(snapshot.get('volume_id', '')))
            if snapshot.get('os-extended-snapshot-attributes:project_id'):
                volsnap_dict['set_tenant'] = \
                    prepId('tenant-{0}'.format(snapshot.get(
                        'os-extended-snapshot-attributes:project_id', '')))
            volumesnapshots.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.VolSnapshot',
                data=volsnap_dict))
        return volumesnapshots

    def map_pools(self, device, results):
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
                allocated_capacity = str(allocated_capacity) + ' GB'
            free_capacity = pool.get('capabilities', {}).get('free_capacity_gb', False)
            if not free_capacity:
                free_capacity = ''
            else:
                free_capacity = str(free_capacity) + ' GB'
            total_capacity = pool.get('capabilities', {}).get('total_capacity_gb', False)
            if not total_capacity:
                total_capacity = ''
            else:
                total_capacity = str(total_capacity) + ' GB'

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

    def map_quotas(self, device, results):
        quotas = []
        for quota in results['quotas']:
            quota_key = quota.get('id')

            # Find and use the tenant that corresponds to this quota:
            q_tenant = None
            for _ten in results.get('process_quota_tenants'):
                if _ten.get('id') == quota_key:
                    q_tenant = _ten
                    break

            if not q_tenant:
                continue

            title = 'quota-' + q_tenant.get('name')
            quotas.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Quota',
                data=dict(
                    id=prepId('quota-{0}'.format(quota_key)),
                    title=title,
                    tenant_name=q_tenant['name'],
                    volumes=quota.get('volumes', 0),
                    snapshots=quota.get('snapshots', 0),
                    bytes=quota.get('gigabytes', 0),
                    backups=quota.get('backups', 0),
                    backup_bytes=quota.get('backup_gigabytes', 0),
                    set_tenant=prepId('tenant-{0}'.format(quota_key)),
                    )))
        return quotas

    def map_api_endpoints(self, device, results):
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

    # -------------------------------------------------------------------------
    # --------------- End Mapping functions for process() ---------------------
    # -------------------------------------------------------------------------

    @inlineCallbacks
    def api_call(self, method, key, **kwargs):
        """
        A smart API calling method, which handles possible errors.

        API gets called like this:

            results['cinder_url'] = yield api_call(cinder.get_url, None)
            results['tenants'] = yield api_call(keystone.tenants, 'tenants')
            results['flavors'] = yield api_call(nova.flavors, 'flavors', is_public=True)

        """
        if self.api_client_logs is None:
            self.api_client_logs = set()

        method_class = '{}'.format(method.__self__.__class__.__name__)
        debug_string = "{}".format(method_class)
        if key:
            debug_string += ".{}".format(key)
        if kwargs:
            debug_string += ".{}".format(str(kwargs))

        LOG.debug("api_call: %s", debug_string)

        try:
            result = yield method(**kwargs)

        except NotFoundError as ex:
            LOG.error("Method not found for '%s': %s. "
                      "Check the API configuration.", debug_string, ex)
            returnValue([])

        except ConnectionRefusedError as ex:
            LOG.error("Connection refused for '%s': %s. "
                      "Check the OpenStack service and network configuration.",
                      debug_string, ex)
            raise ConnectionRefusedError

        except TimeoutError as ex:
            LOG.error("Connection timed out for '%s': %s. "
                      "Check the OpenStack service configuration.",
                      debug_string, ex)
            raise TimeoutError

        except APIClientError as ex:
            messages = set()
            error = re.sub('403 Forbidden:.*"message":\s+"','', ex.message)
            error = error = re.sub('",.+$','', error)
            messages.add("API client error for '{}': {}".format(debug_string, error))

            # Add a single authorization error message to top of list.
            if "401 Unauthorized" in ex.message:
                messages.add("Authorization Errors: Check zCommandUsername and zCommandPassword!")

            elif "403 Forbidden" in ex.message:
                messages.add("OpenStack user lacks access to call: {}. "
                             "Partial Modeling will proceed regardless."
                             .format(debug_string))

            elif "500 Internal Server Error" in ex.message:
                LOG.error("Internal Server Error for '%s': %s. "
                          "Check the OpenStack connectivity.", debug_string, ex)
                raise APIClientError

            elif "503 Service Unavailable" in ex.message:
                LOG.error("Service Unavailable for '%s': %s. "
                          "Check the OpenStack connectivity.", debug_string, ex)
                raise APIClientError

            else:
                raise

            self.api_client_logs.update(messages)
            returnValue([])

        except Exception as ex:
            LOG.warning("API call failure for '%s': %s", debug_string, ex)
            returnValue([])

        else:
            if key:
                returnValue(result.get(key, []))
                LOG.debug('%s: %s\n', debug_string, str(result[key]))
            else:
                returnValue(result)

    @inlineCallbacks
    def collect(self, device, unused):

        self.api_client_logs = None

        if not device.zCommandUsername or not device.zCommandPassword:
            LOG.error("Password/Username should be set to proper values. Check your Openstack credentials.")
            returnValue({})

        if not device.zOpenStackAuthUrl or not device.zOpenStackProjectId or not device.zOpenStackRegionName or not device.zOpenStackUserDomainName or not device.zOpenStackProjectDomainName:
            LOG.error("Openstack credentials should be set to proper values. Check your OpenStackAuthUrl, OpenStackProjectId, zOpenStackUserDomainName, zOpenStackProjectDomainName and OpenStackRegionName")
            returnValue({})

        sm = SessionManager(
            device.zCommandUsername,
            device.zCommandPassword,
            device.zOpenStackAuthUrl,
            device.zOpenStackProjectId,
            device.zOpenStackUserDomainName,
            device.zOpenStackProjectDomainName,
            device.zOpenStackRegionName
        )
        keystone = KeystoneClient(session_manager=sm)
        nova = NovaClient(session_manager=sm)
        neutron = NeutronClient(session_manager=sm)
        cinder = CinderClient(session_manager=sm)

        results = {}
        results['nova_url'] = yield self.api_call(nova.get_url, None)
        results['tenants'] = yield self.api_call(keystone.tenants, 'tenants')
        results['flavors'] = yield self.api_call(nova.flavors, 'flavors', is_public=True)

        private_flavors = yield self.api_call(nova.flavors, 'flavors', is_public=False)
        for flavor in private_flavors:
            if flavor not in results['flavors']:
                results['flavors'].append(flavor)

        results['images'] = yield self.api_call(nova.images, 'images')
        results['hypervisors'] = yield self.api_call(nova.hypervisorservers, 'hypervisors', hypervisor_match='%')
        results['hypervisors_detailed'] = yield self.api_call(nova.hypervisorsdetailed, 'hypervisors')

        # Get hypervisor details for each individual hypervisor
        results['hypervisor_details'] = {}
        for hypervisor in results['hypervisors']:
            hypervisor_detail_id = yield self.api_call(nova.hypervisor_detail_id,
                                                       'hypervisor',
                                                       hypervisor_id=hypervisor['id'])
            hypervisor_id = prepId("hypervisor-{0}".format(hypervisor['id']))
            results['hypervisor_details'][hypervisor_id] = hypervisor_detail_id

        results['servers'] = yield self.api_call(nova.servers, 'servers')
        # Retry as single in case where we don't use administrator account.
        if not results['servers']:
            LOG.debug("API returned no data for 'servers': Re-trying as single tenant.")
            results['servers'] = yield self.api_call(nova.servers_single, 'servers')
        results['services'] = yield self.api_call(nova.services, 'services')
        results['agents'] = yield self.api_call(neutron.agents, 'agents')

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
                try:
                    router_data = yield self.api_call(neutron.agent_l3_routers, None, agent_id=str(_agent['id']))
                except Exception, e:
                    LOG.warning("Unable to determine neutron URL for " +
                                "l3 router agent discovery: %s" % e)
                    continue

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
                try:
                    dhcp_data = yield self.api_call(neutron.agent_dhcp_networks, None, agent_id=str(_agent['id']))
                except Exception, e:
                    LOG.warning("Unable to determine neutron URL for " +
                                "dhcp agent discovery: %s" % e)
                    continue

                for network in dhcp_data['networks']:
                    _networks.append(network.get('id'))
                    for subnet in network['subnets']:
                        _subnets.append(subnet)

                _agent['dhcp_agent_subnets'] = _subnets
                _agent['dhcp_agent_networks'] = _networks

        results['networks'] = yield self.api_call(neutron.networks, 'networks')
        results['subnets'] = yield self.api_call(neutron.subnets, 'subnets')
        results['routers'] = yield self.api_call(neutron.routers, 'routers')
        results['ports'] = yield self.api_call(neutron.ports, 'ports')
        results['floatingips'] = yield self.api_call(neutron.floatingips, 'floatingips')
        results['cinder_url'] = yield self.api_call(cinder.get_url, None)
        results['volumes'] = yield self.api_call(cinder.volumes, 'volumes')
        # Retry as single in case where we don't use administrator account.
        if not results['volumes']:
            LOG.debug("API returned no data for 'volumes': Re-trying as single tenant.")
            results['volumes'] = yield self.api_call(cinder.volumes_single, 'volumes')

        results['volumetypes'] = yield self.api_call(cinder.volumetypes, 'volume_types')
        results['volsnapshots'] = yield self.api_call(cinder.volumesnapshots, 'snapshots')
        # Retry as single in case where we don't use administrator account.
        if not results['volsnapshots']:
            LOG.debug("API returned no data for Volume Snapshots: Re-trying as single tenant.")
            results['volsnapshots'] = yield self.api_call(cinder.volumesnapshots_single, 'snapshots')
        results['cinder_services'] = yield self.api_call(cinder.services, 'services')
        results['volume_pools'] = yield self.api_call(cinder.pools, 'pools')

        results['quotas'] = []
        for tenant in results['tenants']:
            quota_set = yield self.api_call(cinder.quotas, 'quota_set',
                                            tenant=tenant['id'],
                                            usage=False)
            # Skip quota_sets that are empty (and possibly [] instead of {})
            if quota_set:
                results['quotas'].append(quota_set)

        results['zOpenStackNovaApiHosts'], host_errors = filter_FQDNs(device.zOpenStackNovaApiHosts)
        if host_errors:
            LOG.warning('Invalid host in zOpenStackNovaApiHosts')

        results['zOpenStackCinderApiHosts'], host_errors = filter_FQDNs(device.zOpenStackCinderApiHosts)
        if host_errors:
            LOG.warning('Invalid host in zOpenStackCinderApiHosts')

        results['zOpenStackExtraHosts'], host_errors = filter_FQDNs(device.zOpenStackExtraHosts)
        if host_errors:
            LOG.warning('Invalid host in zOpenStackExtraHosts')

        try:
            results['nova_url_host'] = urlparse(results['nova_url']).hostname
        except:
            results['nova_url_host'] = None

        try:
            results['cinder_url_host'] = urlparse(results['cinder_url']).hostname
        except:
            results['cinder_url_host'] = None

        # Dump all API Error logs at once:
        if self.api_client_logs:
            _api_logs = "collect() API Errors detected: \n  "
            _api_logs += "\n  ".join(self.api_client_logs)
            LOG.warning(_api_logs)

        yield self.preprocess_hosts(device, results)

        returnValue(results)

    @inlineCallbacks
    def preprocess_hosts(self, device, results):
        # spin through the collected data, pre-processing all the fields
        # that reference hosts to have consistent host IDs, so that the
        # process() method does not have to worry about hostname -> ID
        # mapping at all.

        hostmap = HostMap()
        host_ignore_pattern = re.compile('@ceph$|^hostgroup@')

        # load in previous mappings..
        if callable(device.get_host_mappings):
            # needed when we are passed a real device, rather than a
            # deviceproxy, during testing
            hostmap.thaw_mappings(device.get_host_mappings())
        else:
            hostmap.thaw_mappings(device.get_host_mappings)

        for service in results['services']:
            if 'host' in service:
                hostmap.add_hostref(service['host'], source="nova services")

        for agent in results['agents']:
            if 'host' in agent:
                hostmap.add_hostref(agent['host'], source="neutron agents")

        for service in results['cinder_services']:
            if 'host' in service:
                # ------------------------------------------------------------------
                # NOTE: (ZPS-3751) This is not the ultimate fix, but we need to
                #       find some elegance before we continue. Perhaps a
                #       zProperty that filters out these bad hosts will work.
                #       Supressing arbitrary hosts is the ultimate goal.
                #       This happens when we have:
                #         1. Ceph Backend which create ceph@ceph hosts
                #         2. hostgroups with TripleO which create 'hostgroup'
                #
                # See host value config options:
                #   https://github.com/openstack/cinder/blob/219961bff62e2b507737ff11a82e18686bdd2c0a/cinder/cmd/volume.py#L95
                # See hostgroup setup:
                #   https://github.com/openstack/tripleo-heat-templates/blob/master/deployment/cinder/cinder-volume-pacemaker-puppet.yaml#L112
                # ------------------------------------------------------------------
                if (service['host'] is not None
                        and host_ignore_pattern.search(service['host'])
                        and service['binary'] == 'cinder-volume'
                   ):
                    message = ("Ignoring host '{}' from cinder-volume service "
                               "matching ignore pattern.").format(service['host'])
                    LOG.debug(message)
                    continue

                hostmap.add_hostref(service['host'], source="cinder services")

        for hostname in results['zOpenStackNovaApiHosts']:
            hostmap.add_hostref(hostname, source="zOpenStackNovaApiHosts")

        for hostname in results['zOpenStackCinderApiHosts']:
            hostmap.add_hostref(hostname, source="zOpenStackCinderApiHosts")

        for hostname in results['zOpenStackExtraHosts']:
            hostmap.add_hostref(hostname, source="zOpenStackExtraHosts")

        if results['nova_url_host']:
            hostmap.add_hostref(results['nova_url_host'], "Nova API URL")

        if results['cinder_url_host']:
            hostmap.add_hostref(results['cinder_url_host'], "Cinder API URL")

        for mapping in device.zOpenStackHostMapToId:
            if not mapping: continue
            try:
                hostref, hostid = mapping.split("=")
                hostmap.check_hostref(hostref, 'zOpenStackHostMapToId')
                hostmap.add_hostref(hostref, source="zOpenStackHostMapToId")
                hostmap.assert_host_id(hostref, hostid)
            except Exception as ex:
                LOG.error("Invalid value in zOpenStackHostMapToId: '%s'", mapping)

        for mapping in device.zOpenStackHostMapSame:
            if not mapping: continue
            try:
                hostref1, hostref2 = mapping.split("=")
                hostmap.check_hostref(hostref1, 'zOpenStackHostMapSame')
                hostmap.check_hostref(hostref2, 'zOpenStackHostMapSame')
                hostmap.add_hostref(hostref1, source="zOpenStackHostMapSame")
                hostmap.add_hostref(hostref2, source="zOpenStackHostMapSame")
                hostmap.assert_same_host(hostref1, hostref2)
            except Exception as ex:
                LOG.error("assert_same_host error: %s", ex)
                LOG.error("Invalid value in zOpenStackHostMapSame: '%s'", mapping)

        # generate host IDs
        yield hostmap.perform_mapping()

        # store the entire hostmap object so that it is available in process()
        results['hostmap'] = hostmap

        # remember to build an ObjectMap to store these for next time..
        results['host_mappings'] = hostmap.freeze_mappings()

    def replace_hosts_with_ids(self, hostmap, results):
        # Replace all references to hosts in results with their host IDs,
        #  using the information in the hostmap object.
        # ZPS-5043: Guard against missing items due to restricted users.

        for service in results.get('services', {}):
            if 'host' in service:
                service['host'] = hostmap.get_hostid(service['host'])

        for agent in results.get('agents', {}):
            if 'host' in agent:
                agent['host'] = hostmap.get_hostid(agent['host'])

        for service in results.get('cinder_services', {}):
            if 'host' in service:
                if hostmap.has_hostref(service['host']):
                    service['host'] = hostmap.get_hostid(service['host'])
                else:
                    service['host'] = None

        results['zOpenStackNovaApiHosts'] = \
            [hostmap.get_hostid(x) for x in results['zOpenStackNovaApiHosts']]

        results['zOpenStackCinderApiHosts'] = \
            [hostmap.get_hostid(x) for x in results['zOpenStackCinderApiHosts']]

        results['zOpenStackExtraHosts'] = \
            [hostmap.get_hostid(x) for x in results['zOpenStackExtraHosts']]

        if results['nova_url_host']:
            results['nova_url_host'] = hostmap.get_hostid(results['nova_url_host'])

        if results['cinder_url_host']:
            results['cinder_url_host'] = hostmap.get_hostid(results['cinder_url_host'])

    def process(self, device, results, unused):
        # normalize all hostnames to host IDs, so that the rest of
        # process() doesn't have to think about that.
        self.replace_hosts_with_ids(results['hostmap'], results)

        tenants = self.map_tenants(device, results)
        regions = self.map_regions(device, results)
        zones = self.map_zones(device, results)
        flavors = self.map_flavors(device, results)
        images = self.map_images(device, results)
        hypervisors = self.map_hypervisors(device, results)
        servers = self.map_servers(device, results)
        hosts = self.map_hosts(device, results)
        services = self.map_nova_services(device, results)
        cinder_services = self.map_cinder_services(device, results)
        agents = self.map_agents(device, results)
        networks = self.map_networks(device, results)
        subnets = self.map_subnets(device, results)
        ports = self.map_ports(device, results)
        routers = self.map_routers(device, results)
        floatingips = self.map_floatingips(device, results)
        voltypes = self.map_voltypes(device, results)
        volumes = self.map_volumes(device, results)
        volsnapshots = self.map_volumesnapshots(device, results)
        pools = self.map_pools(device, results)
        quotas = self.map_quotas(device, results)
        api_endpoints = self.map_api_endpoints(device, results)

        objmaps = {
            'flavors': flavors,
            'hosts': hosts,
            'hypervisors': hypervisors,
            'images': images,
            'regions': regions,
            'servers': servers,
            'services': services + cinder_services,
            'tenants': tenants,
            'zones': zones,
            'agents': agents,
            'networks': networks,
            'subnets': subnets,
            'routers': routers,
            'ports': ports,
            'floatingips': floatingips,
            'volumes': volumes,
            'voltypes': voltypes,
            'volsnapshots': volsnapshots,
            'pools': pools,
            'quotas': quotas,
            'api_endpoints': api_endpoints
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
            LOG.info("Loading %s" % filename)
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
                        compname = om_dict.pop('compname')
                        modname = om_dict.pop('modname')
                        classname = om_dict.pop('classname')
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
                                            LOG.info("  Adding %s=%s to %s (%s)" % (attr, om_dict[attr], om.id, om.title))
                                            setattr(om, attr, om_dict[attr])
                                    break

                            if not found:
                                LOG.error("Unable to find a matching objectmap to extend: %s" % om_dict)

                            continue

                        objmaps[key].append(ObjectMap(compname=compname,
                                                      modname=modname,
                                                      classname=classname,
                                                      data=om_dict))
                    added_count = len(objmaps[key]) - starting_count
                    if added_count > 0:
                        LOG.info("  Added %d new objectmaps to %s" % (added_count, key))

        # Apply the objmaps in the right order.
        componentsMap = RelationshipMap(relname='components')
        for i in ('tenants', 'regions', 'flavors', 'images', 'servers', 'zones',
                  'hosts', 'hypervisors', 'services', 'networks',
                  'subnets', 'routers', 'ports', 'agents', 'floatingips',
                  'voltypes', 'volumes', 'volsnapshots', 'pools', 'quotas',
                  'api_endpoints'
                  ):
            for objmap in objmaps[i]:
                componentsMap.append(objmap)

        hostmap = results.get('hostmap')
        endpointObjMap = ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Endpoint',
            data=dict(
                set_maintain_proxydevices=True,
                set_host_mappings=hostmap.freeze_mappings()
            )
        )

        return (componentsMap, endpointObjMap)
