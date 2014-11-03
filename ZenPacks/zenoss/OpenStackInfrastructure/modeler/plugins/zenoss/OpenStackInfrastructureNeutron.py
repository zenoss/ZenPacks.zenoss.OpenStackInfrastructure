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

""" Get component information using OpenStack Neutron API clients """

import logging
log = logging.getLogger('zen.OpenStackNeutron')

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

from apiclients.keystoneapiclient import KeystoneAPIClient
from apiclients.neutronapiclient import NeutronAPIClient

class OpenStackInfrastructureNeutron(PythonPlugin):
    deviceProperties = PythonPlugin.deviceProperties + (
        'zCommandUsername',
        'zCommandPassword',
        'zOpenStackProjectId',
        'zOpenStackAuthUrl',
        'zOpenStackRegionName',
    )

    @inlineCallbacks
    def collect(self, device, unused):

        results = {}

        keystone_client = KeystoneAPIClient(
            device.zCommandUsername,
            device.zCommandPassword,
            device.zOpenStackAuthUrl,
            device.zOpenStackProjectId)

        neutron_client = NeutronAPIClient(
            username=device.zCommandUsername,
            password=device.zCommandPassword,
            auth_url=device.zOpenStackAuthUrl,
            project_id=device.zOpenStackProjectId,
            region_name=device.zOpenStackRegionName,
            )

        result = yield keystone_client.tenants()
        results['tenants'] = result['tenants']
        log.debug('tenants: %s\n' % str(results['tenants']))

        result = yield neutron_client.agents()
        results['agents'] = result['agents']
        log.debug('agents: %s\n' % str(results['agents']))
        import pdb;pdb.set_trace()

        result = yield neutron_client.networks()
        results['networks'] = result['networks']
        log.debug('networks: %s\n' % str(results['networks']))
        import pdb;pdb.set_trace()

        result = yield neutron_client.subnets()
        results['subnets'] = result['subnets']
        log.debug('subnets: %s\n' % str(results['subnets']))
        import pdb;pdb.set_trace()

        result = yield neutron_client.routers()
        results['routers'] = result['routers']
        log.debug('routers: %s\n' % str(results['routers']))
        import pdb;pdb.set_trace()

        result = yield neutron_client.ports()
        results['ports'] = result['ports']
        log.debug('ports: %s\n' % str(results['ports']))
        import pdb;pdb.set_trace()

        result = yield neutron_client.security_groups()
        results['security_groups'] = result['security_groups']
        log.debug('security_groups: %s\n' % str(results['security_groups']))
        import pdb;pdb.set_trace()

        result = yield neutron_client.floatingips()
        results['floatingips'] = result['floatingips']
        log.debug('floatingips: %s\n' % str(results['floatingips']))
        import pdb;pdb.set_trace()

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
                    # set_net_tenant_id='tenant-{0}'.format(tenant_id),    # tenant-a3a2901f2fd14f808401863e3628a858
                    netStatus=net['status'],                      # ACTIVE
                    netType=net['provider:network_type'].upper(), # local/global
                    subnet_=cidrs,
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
        for i in ('agents', 'networks', 'subnets', 'routers', 'ports',
                  'security_groups', 'floatingips',):
            for objmap in objmaps[i]:
                componentsMap.append(objmap)

        endpointObjMap = ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Endpoint',
            data=dict(
                set_maintain_proxydevices=True
            )
        )

        return (componentsMap, endpointObjMap)
