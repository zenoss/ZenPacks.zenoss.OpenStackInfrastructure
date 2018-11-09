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

from twisted.internet.defer import inlineCallbacks, returnValue

from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
from Products.ZenUtils.Utils import prepId

from ZenPacks.zenoss.OpenStackInfrastructure.hostmap import HostMap
from ZenPacks.zenoss.OpenStackInfrastructure.utils import (
    add_local_lib_path,
    zenpack_path,
    getNetSubnetsGws_from_GwInfo,
    filter_FQDNs,
)

# The order of the mappers below is the required order for process()
from ZenPacks.zenoss.OpenStackInfrastructure.model_mappers import (
    map_tenants,
    map_regions,
    map_flavors,
    map_images,
    map_hypervisors,
    map_servers,
    map_services,
    map_hosts,
    map_extra_services,
    map_agents,
    map_networks,
    map_subnets,
    map_ports,
    map_routers,
    map_floatingips,
    map_voltypes,
    map_volumes,
    map_volsnapshots,
    map_pools,
    map_quotas,
    map_api_endpoints,
)

add_local_lib_path()

from apiclients.session import SessionManager
from apiclients.txapiclient import (
    KeystoneClient,
    NovaClient,
    NeutronClient,
    CinderClient,
    NotFoundError
)

# https://github.com/openstack/nova/blob/master/nova/compute/power_state.py
POWER_STATE_MAP = {
    0: 'pending',
    1: 'running',
    3: 'paused',
    4: 'shutdown',
    6: 'crashed',
    7: 'suspended',
}


class OpenStackInfrastructure(PythonPlugin):
    deviceProperties = PythonPlugin.deviceProperties + (
        'zCommandUsername',
        'zCommandPassword',
        'zOpenStackProjectId',
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

    @inlineCallbacks
    def collect(self, device, unused):

        if not device.zCommandUsername or not device.zCommandPassword:
            log.error("Password/Username should be set to proper values. Check your Openstack credentials.")
            returnValue({})

        if not device.zOpenStackAuthUrl or not device.zOpenStackProjectId or not device.zOpenStackRegionName:
            log.error("Openstack credentials should be set to proper values. Check your OpenStackAuthUrl, OpenStackProjectId and OpenStackRegionName")
            returnValue({})

        sm = SessionManager(
            device.zCommandUsername,
            device.zCommandPassword,
            device.zOpenStackAuthUrl,
            device.zOpenStackProjectId,
            device.zOpenStackRegionName
        )
        keystone = KeystoneClient(session_manager=sm)
        nova = NovaClient(session_manager=sm)
        neutron = NeutronClient(session_manager=sm)
        cinder = CinderClient(session_manager=sm)

        results = {}

        results['nova_url'] = yield nova.get_url()

        _tenants = yield keystone.tenants()
        results['tenants'] = _tenants.get('tenants', [])
        log.debug('tenants: %s\n' % str(results['tenants']))

        _public_flavors = yield nova.flavors(is_public=True)
        results['flavors'] = _public_flavors.get('flavors', [])
        _private_flavors = yield nova.flavors(is_public=False)
        for flavor in _private_flavors.get('flavors', []):
            if flavor not in results['flavors']:
                results['flavors'].append(flavor)
        log.debug('flavors: %s\n' % str(results['flavors']))

        _images = yield nova.images()
        results['images'] = _images.get('images', [])
        log.debug('images: %s\n' % str(results['images']))

        _hypervisorservers = yield nova.hypervisorservers(hypervisor_match='%')
        results['hypervisors'] = _hypervisorservers.get('hypervisors', [])
        log.debug('hypervisors: %s\n' % str(results['hypervisors']))

        _hypervisors = yield nova.hypervisorsdetailed()
        results['hypervisors_detailed'] = _hypervisors.get('hypervisors', [])
        log.debug('hypervisors_detailed: %s\n' % str(results['hypervisors_detailed']))

        # get hypervisor details for each individual hypervisor
        results['hypervisor_details'] = {}
        for hypervisor in results['hypervisors']:
            _hypervisor_detail_id = yield nova.hypervisor_detail_id(hypervisor_id=hypervisor['id'])
            hypervisor_id = prepId("hypervisor-{0}".format(hypervisor['id']))
            results['hypervisor_details'][hypervisor_id] = _hypervisor_detail_id.get('hypervisor', [])

        _nova_servers = yield nova.servers()
        results['servers'] = _nova_servers.get('servers', [])
        log.debug('servers: %s\n' % str(results['servers']))

        _nova_services = yield nova.services()
        results['services'] = _nova_services.get('services', [])
        log.debug('services: %s\n' % str(results['services']))

        # Neutron
        results['agents'] = []
        try:
            _neutron_agens = yield neutron.agents()
            results['agents'] = _neutron_agens.get('agents', [])
        except NotFoundError:
            # Some networks, like Nuage network, do not have network agents
            log.info("Neutron agents not found.")
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
                try:
                    router_data = yield neutron.agent_l3_routers(agent_id=str(_agent['id']))
                except Exception, e:
                    log.warning("Unable to determine neutron URL for " +
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
                    dhcp_data = yield neutron.agent_dhcp_networks(agent_id=str(_agent['id']))
                except Exception, e:
                    log.warning("Unable to determine neutron URL for " +
                                "dhcp agent discovery: %s" % e)
                    continue

                for network in dhcp_data['networks']:
                    _networks.append(network.get('id'))
                    for subnet in network['subnets']:
                        _subnets.append(subnet)

                _agent['dhcp_agent_subnets'] = _subnets
                _agent['dhcp_agent_networks'] = _networks

        _neutron_networks = yield neutron.networks()
        results['networks'] = _neutron_networks.get('networks', [])

        _neutron_subnets = yield neutron.subnets()
        results['subnets'] = _neutron_subnets.get('subnets', [])

        _neutron_routers = yield neutron.routers()
        results['routers'] = _neutron_routers.get('routers', [])

        _neutron_ports = yield neutron.ports()
        results['ports'] = _neutron_ports.get('ports', [])

        _neutron_floatingips = yield neutron.floatingips()
        results['floatingips'] = _neutron_floatingips.get('floatingips', [])

        # Cinder
        results['cinder_url'] = yield cinder.get_url()

        _cinder_volumes = yield cinder.volumes()
        results['volumes'] = _cinder_volumes.get('volumes', [])

        _cinder_volumetypes = yield cinder.volumetypes()
        results['volumetypes'] = _cinder_volumetypes.get('volume_types', [])

        _cinder_volumesnapshots = yield cinder.volumesnapshots()
        results['volsnapshots'] = _cinder_volumesnapshots.get('snapshots', [])

        _cinder_services = yield cinder.services()
        results['cinder_services'] = _cinder_services.get('services', [])

        _cinder_pools = yield cinder.pools()
        results['volume_pools'] = _cinder_pools.get('pools', [])

        results['quotas'] = {}
        for tenant in results['tenants']:
            try:
                _cinder_quotas = yield cinder.quotas(tenant=tenant['id'].encode(
                    'ascii', 'ignore'), usage=False)
            except Exception, e:
                try:
                    message = re.search('\"message\":\s?\"(.*)\.\"', e.message).groups()[0]
                except AttributeError:
                    message = e.message

                log.warn("Unable to obtain quotas for %s. Error message: %s" %
                         (tenant['name'], message))
            else:
                results['quotas'][tenant['id']] = _cinder_quotas.get('quota_set', [])

        results['zOpenStackNovaApiHosts'], host_errors = filter_FQDNs(device.zOpenStackNovaApiHosts)
        if host_errors:
            log.warn('Invalid host in zOpenStackNovaApiHosts')

        results['zOpenStackCinderApiHosts'], host_errors = filter_FQDNs(device.zOpenStackCinderApiHosts)
        if host_errors:
            log.warn('Invalid host in zOpenStackCinderApiHosts')

        results['zOpenStackExtraHosts'], host_errors = filter_FQDNs(device.zOpenStackExtraHosts)
        if host_errors:
            log.warn('Invalid host in zOpenStackExtraHosts')

        try:
            results['nova_url_host'] = urlparse(results['nova_url']).hostname
        except:
            results['nova_url_host'] = None

        try:
            results['cinder_url_host'] = urlparse(results['cinder_url']).hostname
        except:
            results['cinder_url_host'] = None

        yield self.preprocess_hosts(device, results)

        returnValue(results)

    @inlineCallbacks
    def preprocess_hosts(self, device, results):
        # spin through the collected data, pre-processing all the fields
        # that reference hosts to have consistent host IDs, so that the
        # process() method does not have to worry about hostname -> ID
        # mapping at all.

        hostmap = HostMap()
        self.hostmap = hostmap

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

                # with the ceph backend, it seems like the cinder-volume
                # hostname may not be relevant.  (At least on the test servers,
                # I see 'ceph@ceph' here, which is meaningless)  (ZPS-3751)
                if service['binary'] == 'cinder-volume' and service['host'].endswith('@ceph'):
                    log.debug("Ignoring host '%s' from cinder-volume service", service['host'])
                    continue

                hostmap.add_hostref(service['host'], source="cinder services")

        for hostname in results['zOpenStackNovaApiHosts']:
            hostmap.add_hostref(hostname, source="zOpenStackNovaApiHosts")

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
                log.error("Invalid value in zOpenStackHostMapToId: '%s'", mapping)

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
                log.error("assert_same_host error: %s", ex)
                log.error("Invalid value in zOpenStackHostMapSame: '%s'", mapping)

        # generate host IDs
        yield hostmap.perform_mapping()

        # replace all references to hosts with their host IDs, so
        # process() doesn't have to think about this stuff.
        for service in results['services']:
            if 'host' in service:
                service['host'] = hostmap.get_hostid(service['host'])

        for agent in results['agents']:
            if 'host' in agent:
                agent['host'] = hostmap.get_hostid(agent['host'])

        for service in results['cinder_services']:
            if 'host' in service:
                if hostmap.has_hostref(service['host']):
                    service['host'] = hostmap.get_hostid(service['host'])
                else:
                    service['host'] = None

        results['zOpenStackNovaApiHosts'] = \
            [hostmap.get_hostid(x) for x in results['zOpenStackNovaApiHosts']]

        results['zOpenStackExtraHosts'] = \
            [hostmap.get_hostid(x) for x in results['zOpenStackExtraHosts']]

        if results['nova_url_host']:
            results['nova_url_host'] = hostmap.get_hostid(results['nova_url_host'])

        if results['cinder_url_host']:
            results['cinder_url_host'] = hostmap.get_hostid(results['cinder_url_host'])

        # remember to build an ObjectMap to store these for next time..
        results['host_mappings'] = hostmap.freeze_mappings()

    def process(self, device, results, unused):
        tenants = map_tenants(device, results, self.hostmap)
        regions = map_regions(device, results, self.hostmap)
        flavors = map_flavors(device, results, self.hostmap)
        images = map_images(device, results, self.hostmap)
        hypervisors = map_hypervisors(device, results, self.hostmap)
        servers = map_servers(device, results, self.hostmap)
        services = map_services(device, results, self.hostmap)
        hosts = map_hosts(device, results, self.hostmap)
        extra_services = map_extra_services(device, results, self.hostmap)
        agents = map_agents(device, results, self.hostmap)
        networks = map_networks(device, results, self.hostmap)
        subnets = map_subnets(device, results, self.hostmap)
        ports = map_ports(device, results, self.hostmap)
        routers = map_routers(device, results, self.hostmap)
        floatingips = map_floatingips(device, results, self.hostmap)
        voltypes = map_voltypes(device, results, self.hostmap)
        volumes = map_volumes(device, results, self.hostmap)
        volsnapshots = map_volsnapshots(device, results, self.hostmap)
        pools = map_pools(device, results, self.hostmap)
        quotas = map_quotas(device, results, self.hostmap)
        api_endpoints = map_api_endpoints(device, results, self.hostmap)

        objmaps = {
            'flavors': flavors,
            'hosts': hosts,
            'hypervisors': hypervisors,
            'images': images,
            'regions': regions,
            'servers': servers,
            'services': services + extra_services,
            'tenants': tenants,
            'zones': results.get('process_zones'),
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
                  'voltypes', 'volumes', 'volsnapshots', 'pools', 'quotas',
                  'api_endpoints'
                  ):
            for objmap in objmaps[i]:
                componentsMap.append(objmap)

        endpointObjMap = ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Endpoint',
            data=dict(
                set_maintain_proxydevices=True,
                set_host_mappings=self.hostmap.freeze_mappings()
            )
        )

        return (componentsMap, endpointObjMap)
