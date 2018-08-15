#!/usr/bin/env python

###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2017, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

import Globals

import logging
log = logging.getLogger('zen.OpenStack.txapiclient')

from Products.ZenUtils.Utils import unused
unused(Globals)

from ZenPacks.zenoss.OpenStackInfrastructure.apiclients.session import SessionManager
from ZenPacks.zenoss.OpenStackInfrastructure.apiclients.exceptions import *
from ZenPacks.zenoss.OpenStackInfrastructure.apiclients.base import BaseClient, api

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue


class KeystoneClient(BaseClient):
    keystone_service_type = 'identity'

    _keystonev2errmsg = """
        Unable to connect to keystone Identity Admin API v2.0 to retrieve tenant
        list.  Tenant names will be unknown (tenants will show with their IDs only)
        until this is corrected, either by opening access to the admin API endpoint
        as listed in the keystone service catalog, or by configuring zOpenStackAuthUrl
        to point to a different, accessible endpoint which supports both the public and
        admin APIs.  (This may be as simple as changing the port in the URL from
        5000 to 35357)  Details: %s
    """

    def __init__(self, *args, **kwargs):
        super(KeystoneClient, self).__init__(*args, **kwargs)

        self.public_only = False

    @inlineCallbacks
    def tenants(self):
        api_version = yield self.session_manager.get_api_version()
        if api_version.startswith('v2'):
            if self.public_only:
                result = yield self.get_json('/tenants', interface='public')
            else:
                try:
                    result = yield self.get_json('/tenants', interface='admin')
                except Exception, e:
                    log.error(self._keystonev2errmsg, e)
                    self.public_only = True  # don't try the admin interface again.

                    result = yield self.get_json('/tenants', interface='public')

            returnValue(result)

        elif api_version.startswith('v3'):
            result = yield self.get_json_collection('/projects')
            # Convert into the familiar v2 format expected by our modeler.
            v2_result = {'tenants': [], 'tenants_links': []}
            for project in result['projects']:
                v2_result['tenants'].append({
                    u'description': project['description'],
                    u'enabled': project['enabled'],
                    u'id': project['id'],
                    u'name': project['name']
                })
            result = v2_result

        else:
            raise APIClientError("[tenants] Unsupported identity API version %s" % api_version)

        returnValue(result)


class NovaClient(BaseClient):
    keystone_service_type = 'compute'

    avzones = api('/os-availability-zone/detail')
    flavors = api('/flavors/detail')
    hosts = api('/os-hosts')

    # Note: this will be deprecated in api microversion 2.53.
    # We may want to switch over to the newer api (/os-hypervisors?with_servers=True)
    # with the Pike release.
    hypervisorservers = api('/os-hypervisors/{param[hypervisor_match]}/servers')

    hypervisorsdetailed = api('/os-hypervisors/detail')
    hypervisorstats = api('/os-hypervisors/statistics')
    hypervisor_detail_id = api('/os-hypervisors/{param[hypervisor_id]}')
    images = api('/images/detail')
    servers = api('/servers/detail?all_tenants=1')
    services = api('/os-services')


class NeutronClient(BaseClient):
    keystone_service_type = 'network'

    agents = api('/v2.0/agents.json')
    floatingips = api('/v2.0/floatingips.json')
    security_groups = api('/v2.0/security-groups.json')
    ports = api('/v2.0/ports.json')
    routers = api('/v2.0/routers.json')
    agent_l3_routers = api('/v2.0/agents/{param[agent_id]}/l3-routers')
    agent_dhcp_networks = api('/v2.0/agents/{param[agent_id]}/dhcp-networks')
    networks = api('/v2.0/networks.json')
    subnets = api('/v2.0/subnets.json')


class CinderClient(BaseClient):
    keystone_service_type = 'volumev2'

    volumes = api('/volumes/detail?all_tenants=1')
    volumetypes = api('/types')
    volumebackups = api('/backups/detail?all_tenants=1')
    volumesnapshots = api('/snapshots/detail?all_tenants=1')
    pools = api('/scheduler-stats/get_pools?detail=True')
    quotas = api('/os-quota-sets/{param[tenant]}')
    services = api('/os-services')


@inlineCallbacks
def main():
    logging.basicConfig(level=logging.DEBUG)
    import pprint

    # sm = SessionManager('admin', '0ed3ab06fb234024', 'http://192.168.2.12:5000/v2.0/', 'admin', 'RegionOne')
    # sm = SessionManager('admin', '0ed3ab06fb234024', 'http://192.168.2.12:5000/v3/', 'admin', 'RegionOne')
    # sm = SessionManager('admin', '0ed3ab06fb234024', 'http://192.168.2.12:5000/', 'admin', 'RegionOne')
    sm = SessionManager('admin', '354f6fc8937c47f7', 'http://192.168.2.15:5000/v3/', 'admin', 'RegionOne')
    version = yield sm.get_api_version()
    print "Identity API %s" % version

    keystone = KeystoneClient(session_manager=sm)
    tenants = yield keystone.tenants()

    nova = NovaClient(session_manager=sm)
    neutron = NeutronClient(session_manager=sm)
    cinder = CinderClient(session_manager=sm)

    # Nova
    try:
        avzones = yield nova.avzones()
        public_flavors = yield nova.flavors(is_public=True)
        private_flavors = yield nova.flavors(is_public=False)
        hosts = yield nova.hosts()
        hypervisors = yield nova.hypervisorservers(hypervisor_match='%')
        hypervisorStats = yield nova.hypervisorstats()
        hypervisor_1 = yield nova.hypervisor_detail_id(hypervisor_id='1')
        images = yield nova.images(detailed=True)
        novaservices = yield nova.services()
        servers = yield nova.servers(detailed=True)
    except APIClientError as e:
        pprint.pprint(e.message)
    else:
        pprint.pprint(avzones)
        pprint.pprint(public_flavors)
        pprint.pprint(private_flavors)
        pprint.pprint(hosts)
        pprint.pprint(hypervisors)
        pprint.pprint(hypervisorStats)
        pprint.pprint(hypervisor_1)
        pprint.pprint(images)
        pprint.pprint(novaservices)
        pprint.pprint(servers)

    # Neutron
    try:
        neutronagents = yield neutron.agents()
        floatingips = yield neutron.floatingips()
        networks = yield neutron.networks()
        ports = yield neutron.ports()
        routers = yield neutron.routers()
        security_groups = yield neutron.security_groups()
        subnets = yield neutron.subnets()
    except APIClientError as e:
        pprint.pprint(e.message)
    else:
        pprint.pprint(neutronagents)
        pprint.pprint(floatingips)
        pprint.pprint(networks)
        pprint.pprint(ports)
        pprint.pprint(routers)
        pprint.pprint(security_groups)
        pprint.pprint(subnets)

    # Cinder
    try:
        volumes = yield cinder.volumes()
        volumetypes = yield cinder.volumetypes()
        volumebackups = yield cinder.volumebackups()
        volumesnapshots = yield cinder.volumesnapshots()
        cinderservices = yield cinder.services(detailed=True)
        cinderpools = yield cinder.pools(detailed=True)
    except APIClientError as e:
        pprint.pprint(e.message)
    else:
        pprint.pprint(volumes)
        pprint.pprint(volumetypes)
        pprint.pprint(volumebackups)
        pprint.pprint(volumesnapshots)
        pprint.pprint(cinderservices)
        pprint.pprint(cinderpools)

    if tenants and 'tenants' in tenants:
        for tenant in tenants['tenants']:
            try:
                quotas = yield cinder.quotas(tenant=tenant['id'].encode('ascii', 'ignore'), usage=False)
            except APIClientError as e:
                pprint.pprint(e.message)
            else:
                pprint.pprint(quotas)
    try:
        avzones = yield nova.avzones()
        public_flavors = yield nova.flavors(is_public=True)
        private_flavors = yield nova.flavors(is_public=False)
        hosts = yield nova.hosts()
        hypervisors = yield nova.hypervisorservers(hypervisor_match='%', servers=True)
        images = yield nova.images(detailed=True)
        novaservices = yield nova.services()
        servers = yield nova.servers(detailed=True)
    except APIClientError as e:
        pprint.pprint(e.message)
    else:
        pprint.pprint(avzones)
        pprint.pprint(public_flavors)
        pprint.pprint(private_flavors)
        pprint.pprint(hosts)
        pprint.pprint(hypervisors)
        pprint.pprint(images)
        pprint.pprint(novaservices)
        pprint.pprint(servers)

    if reactor.running:
        reactor.stop()

if __name__ == '__main__':
    main()
    reactor.run()
