##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013-2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""ZenPacks.zenoss.OpenStackInfrastructure.- OpenStack monitoring for Zenoss.

This module contains initialization code for the ZenPack. Everything in
the module scope will be executed at startup by all Zenoss Python
processes.

The initialization order for ZenPacks is defined by
$ZENHOME/ZenPacks/easy-install.pth.

"""

from . import zenpacklib


# Useful to avoid making literal string references to module and class names
# throughout the rest of the ZenPack.
MODULE_NAME = {}
CLASS_NAME = {}

RELATIONSHIPS_YUML = """
// containing
[Endpoint]++components-endpoint1[OpenstackComponent]
[Instance]++-[Vnic]
// [SecurityGroup]++-[SecurityGroupRule]
// Non-containing M:M
[NeutronAgent]*agentRouters-.-routerAgents*[Router]
[NeutronAgent]*agentNetworks-.-networkAgents*[Network]
[NeutronAgent]*agentSubnets-.-subnetAgents*[Subnet]
// non-containing 1:M
[OrgComponent]*parentOrg-childOrgs1[OrgComponent]
[Host]1hostedSoftware-hostedOn*[SoftwareComponent]
[OrgComponent]1-.-*[Host]
[OrgComponent]1-.-*[SoftwareComponent]
// Non-containing 1:M
// # Can abstract Tenant -> (Instance,Network,Subnet,Router,Port,FloatingIp)
// # Tenant-> Flavor has no support so its a blank relation
[Tenant]1-.-*[LogicalComponent]
// # Flavor ->
[Flavor]1-.-*[Instance]
[Image]1-.-*[Instance]
// Hypervisor ->
[Hypervisor]1-.-*[Instance]
// Network ->
[Network]1-.-*[Subnet]
[Network]1-.-*[Port]
[Network]1-.-*[FloatingIp]
// -- Routers can have common network gateway
[Network]1-.-*[Router]
// Instance ->
[Instance]1-.-*[Port]
// Ports ->
[Port]1-.-*[FloatingIp]
[Port]1-.-*[Subnet]
// Router -> downstream Subnets and 1 upstream Network
[Router]1-.-*[FloatingIp]
// Router can connect to many subnets, a subnet can connect to several routers
//    EG: router_AB + router_C connect to public_subnet:  subnet -> *router
//    EG: since public network can have multiple subnets: router -> *subnet
[Router]*-.-*[Subnet]
// non-containing 1:1
[Hypervisor]1-.-1[Host]
"""

CFG = zenpacklib.ZenPackSpec(
    name=__name__,

    zProperties={
        'DEFAULTS': {'category': 'OpenStack',
                     'type': 'string'},

        # Pre-defined by ZenPacks.zenoss.OpenStack
        # 'zOpenStackAuthUrl':          {},
        # 'zOpenStackProjectId':        {},
        # 'zOpenStackRegionName':       {},


        'zOpenStackHostDeviceClass':  {'default': '/Server/SSH/Linux/NovaHost'},
        'zOpenStackNovaApiHosts':     {'type': 'lines'},
        'zOpenStackExtraHosts':       {'type': 'lines'},
        'zOpenStackCeilometerUrl':    {},
    },

    device_classes={
        '/OpenStack': {
            'create': True,
            'remove': False
        },
        '/Server/SSH/Linux/NovaHost': {
            'create': True,
            'remove': False,
            'zProperties': {
                'zCollectorPlugins': [
                    'zenoss.cmd.uname',
                    'zenoss.cmd.uname_a',
                    'zenoss.cmd.df',
                    'zenoss.cmd.linux.cpuinfo',
                    'zenoss.cmd.linux.memory',
                    'zenoss.cmd.linux.ifconfig',
                    'zenoss.cmd.linux.netstat_an',
                    'zenoss.cmd.linux.netstat_rn',
                    'zenoss.cmd.linux.process',
                    'zenoss.cmd.linux.rpm',
                    'zenoss.cmd.linux.openstack.nova',
                    'zenoss.cmd.linux.openstack.libvirt'
                ]
            }
        }
    },

    classes={
        # Device Types ###############################################

        'Endpoint': {
            'base': zenpacklib.Device,
            'meta_type': 'OpenStackInfrastructureEndpoint',
            'label': 'OpenStack Endpoint',
            'order': 1,
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_group': 'Devices',
            'dynamicview_relations': {
                'openstack_link': ['region'],
                'impacts': ['hosts']
            }
        },

        'KeystoneEndpoint': {
            'base': 'Endpoint',
            'meta_type': 'OpenStackInfrastructureKeystoneEndpoint',
            'label': 'Keystone Endpoint',
            'order': 2,
        },

        'NovaEndpoint': {
            'base': 'Endpoint',
            'meta_type': 'OpenStackInfrastructureNovaEndpoint',
            'label': 'Nova Endpoint',
            'order': 3,
        },

        # Component Base Types #######################################
        'OpenstackComponent': {
            'base': zenpacklib.Component,
            'filter_display': False,
            'properties': {
                'resourceId': {'grid_display': False,
                               'label': 'Ceilometer Resource ID'}
            }
        },

        'DeviceProxyComponent': {
            'base': 'OpenstackComponent',
            'filter_display': False,
            'properties': {
                'proxy_device': {'label': 'Device',
                                 # 'type_': 'entity',
                                 'renderer': 'Zenoss.render.openstack_uid_renderer',  # workaround to link to a different device
                                 'api_only': True,
                                 'api_backendtype': 'method'}
            }
        },

        'OrgComponent': {
            'base': 'OpenstackComponent',
            'filter_display': False,
            'relationships': {
                # Provide better contextual naming for the relationships in the UI.
                'parentOrg': {'label': 'Parent', 'order': 1.0},
                'childOrgs': {'label': 'Children', 'order': 1.1},
            },
            # these are inherited by child classes:
            #   'impacted_by': ['childOrgs', 'hosts', 'softwareComponents'],
            #   'impacts': ['parentOrg']

        },

        'SoftwareComponent': {
            'base': 'OpenstackComponent',
            'label': 'Software Component',
            'filter_display': False,
            'relationships': {
                # Provide better contextual naming for the relationships in the UI.
                'orgComponent': {'label': 'Supporting',
                                 'render_with_type': True,
                                 'order': 1.0,
                                 'content_width': 150}  # need to fix the default width for render_with_type
            },
            'properties': {
                'binary':     {'label': 'Binary',  'order': 1},
                'enabled':    {'label': 'Enabled', 'order': 2,
                               'renderer': 'Zenoss.render.openstack_ServiceEnabledStatus'},
                'operStatus': {'label': 'State',   'order': 3,
                               'renderer': 'Zenoss.render.openstack_ServiceOperStatus'}
            },

            # these are inherited by child classes:
            #   'impacted_by': ['hostedOn', 'osprocess_component']
            #   'impacts': ['orgComponent']
        },

        'LogicalComponent': {
            'base': 'OpenstackComponent',
            'filter_display': False,
            'relationships':{
                'tenant': {'label_width': 50, 'content_width': 50},
            },
            'dynamicview_relations': {
                'impacts': ['tenant']
            }

        },

        # Component Types ############################################

        'Tenant': {
            'base': 'OpenstackComponent',
            'meta_type': 'OpenStackInfrastructureTenant',
            'label': 'Tenant',
            'order': 5,
            'properties': {
                'tenantId':   {'grid_display': False, 'label': 'Tenant ID'},
                'description': {'label': 'Description','content_width': 180},
            },
            'dynamicview_views': ['service_view'],
            'dynamicview_relations': {
                'impacted_by': ['tenant_impacted_by']
            }
        },

        'Flavor': {
            'base': 'LogicalComponent',
            'meta_type': 'OpenStackInfrastructureFlavor',
            'label': 'Flavor',
            'order': 10,
            'properties': {
                'flavorId':   {'grid_display': False,
                               'label': 'Flavor ID'},                 # 1
                'flavorRAM':  {'type_': 'int',
                               'renderer': 'Zenoss.render.bytesString',
                               'label': 'RAM'},                        # bytes
                'flavorDisk': {'type_': 'int',
                               'renderer': 'Zenoss.render.bytesString',
                               'label': 'Disk'},                       # bytes
                'flavorVCPUs': {'type_': 'int',
                                'label': 'VCPUs'}                      # count
            }
        },

        'Image': {
            'base': 'LogicalComponent',
            'meta_type': 'OpenStackInfrastructureImage',
            'label': 'Image',
            'order': 10,
            'properties': {
                'imageId':      {'grid_display': False,
                                 'label': 'Image ID'},
                'imageStatus':  {'label': 'Status'},
                'imageCreated': {'label': 'Created'},
                'imageUpdated': {'label': 'Updated'},
            }
        },

        'Instance': {
            'base': 'LogicalComponent',
            'meta_type': 'OpenStackInfrastructureInstance',
            'label': 'Instance',
            'order': 8,
            'properties': {
                'serverId':            {'grid_display': False,
                                        'label': 'Server ID'},   # 847424
                'serverStatus':        {'label': 'Status',
                                        'label_width': 65,
                                        'order': 3.3},            # ACTIVE
                'serverBackupEnabled': {'type_': 'boolean',
                                        'label': 'Backup',        # False
                                        'grid_display': False},   # DISABLED
                'serverBackupDaily':   {'grid_display': False,
                                        'label': 'Daily Server Backup'},   # DISABLED
                'serverBackupWeekly':  {'grid_display': False,
                                        'label': 'Weekly Server Backup'},   # DISABLED
                'publicIps':           {'type_': 'lines',
                                        'label': 'Public IPs',
                                        'label_width': 75,
                                        'order': 3.1},            # ['50.57.74.222']
                'privateIps':          {'type_': 'lines',
                                        'label': 'Private IPs',
                                        'label_width': 75,
                                        'order': 3.2},            # ['10.182.13.13']
                'biosUuid':            {'label': 'BIOS UUID',
                                        'grid_display': False},
                'serialNumber':        {'label': 'BIOS Serial Number',
                                        'grid_display': False,
                                        'index_type': 'field',
                                        'index_scope': 'global'},

                # The name this insance is known by within the hypervisor (for instance,
                # for libvirt, it would be something like 'instance-00000001')
                'hypervisorInstanceName': {'label': 'Hypervisor Instance Name',
                                           'grid_display': False},

                'hostId':              {'grid_display': False,
                                        'label': 'Host ID'},   # a84303c0021aa53c7e749cbbbfac265f
                'hostName':            {'grid_display': False,
                                        'index_type': 'field'},   # devstack1
                'host': {'label': 'Host',   # link to the host this is running on.
                         'type_': 'entity',
                         'api_only': True,
                         'api_backendtype': 'method',
                         'order': 3.4}
            },
            'relationships': {
                'hypervisor': {'grid_display': False},
                'vnics':      {'grid_display': False},
                'flavor':     {'label_width': 50, 'content_width': 50},
                'image':      {'label_width': 50, 'content_width': 50},
            },
            'dynamicview_views': ['service_view'],
            'dynamicview_relations': {
                'impacted_by': ['hypervisor', 'ports', 'vnics'],
                'impacts': ['guestDevice', 'tenant']
            }

            # Note: By (nova) design, hostId is a hash of the actual underlying host and project, and
            # is designed to allow users of a specific project to tell if two VMs are on the same host, nothing
            # more.  It is not a unique identifier of hosts (compute nodes).
        },

        'Vnic': {
            'base': 'LogicalComponent',
            'meta_type': 'OpenStackInfrastructureVnic',
            'label': 'Vnic',
            'order': 100,
            'properties': {
                'macaddress': {'label': 'MAC Address',
                               'index_type': 'field',
                               'index_scope': 'global'}
            },
            'dynamicview_views': ['service_view'],
            'dynamicview_relations': {
                'impacts': ['instance']
            }
        },

        'Region': {
            'base': 'OrgComponent',
            'meta_type': 'OpenStackInfrastructureRegion',
            'label': 'Region',
            'order': 1,
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_relations': {
                'openstack_link': ['childOrgs', 'softwareComponents'],
                'impacted_by': ['childOrgs', 'hosts', 'softwareComponents'],  # inherit
                'impacts': ['parentOrg'],  # inherit
            }
        },

        'Cell': {
            'base': 'OrgComponent',
            'meta_type': 'OpenStackInfrastructureCell',
            'label': 'Cell',
            'order': 3,
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_relations': {
                'openstack_link': ['childOrgs', 'hosts', 'softwareComponents'],
                'impacted_by': ['childOrgs', 'hosts', 'softwareComponents'],  # inherit
                'impacts': ['parentOrg'],  # inherit
            }
        },

        'AvailabilityZone': {
            'base': 'OrgComponent',
            'meta_type': 'OpenStackInfrastructureAvailabilityZone',
            'label': 'Availability Zone',
            'order': 2,
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_relations': {
                'openstack_link': ['childOrgs', 'hosts', 'softwareComponents'],
                'impacted_by': ['childOrgs', 'hosts', 'softwareComponents'],  # inherit
                'impacts': ['parentOrg'],  # inherit
            }
        },

        'Host': {
            'base': 'DeviceProxyComponent',
            'meta_type': 'OpenStackInfrastructureHost',
            'label': 'Host',
            'order': 9,
            'properties': {
                'hostfqdn':            {'grid_display': False,
                                        'index_type': 'field'},
                'hostname':            {'grid_display': False,
                                        'index_type': 'field'},
            },
            'relationships': {
                'orgComponent': {'label': 'Supporting',
                                 'render_with_type': True,
                                 'order': 1.0,
                                 'content_width': 150}  # need to fix the default width for render_with_type
            },
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_relations': {
                'openstack_link': ['hostedSoftware', 'hypervisor'],
                'impacted_by': ['endpoint', 'proxy_device'],
                'impacts': ['hypervisor',
                            'orgComponent',
                            'hostedSoftware',
                            ],
            }
        },

        'NovaService': {
            'base': 'SoftwareComponent',
            'meta_type': 'OpenStackInfrastructureNovaService',
            'label': 'Nova Service',
            'order': 7,
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_relations': {
                'impacted_by': ['hostedOn'],  # inherit
                'impacts': ['orgComponent'],   # inherit
            },

            # we use a normal impact adaptor for osprocess_component, rather than
            # dynamicview impacts adaptor, because OSProcess is not part of
            # service_view, and so will not be exported from DV to impact
            # currently (ZEN-14579).
            'impacted_by': ['osprocess_component'],
        },

        'NovaApi': {
            'base': 'SoftwareComponent',
            'meta_type': 'OpenStackInfrastructureNovaApi',
            'label': 'Nova API',
            'order': 7.1,
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_relations': {
                'impacted_by': ['hostedOn'],  # inherit
                'impacts': ['orgComponent'],   # inherit
            },

            # we use a normal impact adaptor for osprocess_component, rather than
            # dynamicview impacts adaptor, because OSProcess is not part of
            # service_view, and so will not be exported from DV to impact
            # currently (ZEN-14579).
            'impacted_by': ['osprocess_component'],
        },

        'NovaDatabase': {
            'base': 'SoftwareComponent',
            'meta_type': 'OpenStackInfrastructureNovaDatabase',
            'label': 'NovaDatabase',
            'order': 7.2,
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_relations': {
                'impacted_by': ['hostedOn'],  # inherit
                'impacts': ['orgComponent'],   # inherit
            },

            # we use a normal impact adaptor for osprocess_component, rather than
            # dynamicview impacts adaptor, because OSProcess is not part of
            # service_view, and so will not be exported from DV to impact
            # currently (ZEN-14579).
            'impacted_by': ['osprocess_component'],
        },

        'Hypervisor': {
            'base': 'OpenstackComponent',   # SoftwareComponent
            'meta_type': 'OpenStackInfrastructureHypervisor',
            'label': 'Hypervisor',
            'order': 9,
            'properties': {
                'hypervisorId':      {'grid_display': False,
                                      'label': 'Hypervisor ID'},
                'hostfqdn':          {'grid_display': False,
                                      'label': 'FQDN'},
            },
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_relations': {
                'impacts': ['instances'],
                'impacted_by': ['hostedSoftware'],
            }
        },

        'NeutronAgent': {
            'base': 'SoftwareComponent',
            'meta_type': 'OpenStackInfrastructureNeutronAgent',
            'label': 'Neutron Agent',
            'order': 11,
            'properties': {
                'agentId':       {'grid_display': False, 'label': 'Agent ID'},
                'type':          {'label': 'Type',
                                  'order': 11.1,
                                  'content_width': 120},
                'binary':        {'grid_display': False},
                'enabled':       {'grid_display': False},
                'state':          {'label': 'Admin State Up',
                                  'order': 11.2,
                                  'content_width': 80},
                'alive':         {'label': 'Alive',
                                  'order': 11.3,
                                  'content_width': 50},
                'operStatus':    {'grid_display': False},
            },
            'dynamicview_relations': {
                'impacts': ['agentNetworks','agentRouters'],
                'impacted_by': ['hostedOn'],
            }
        },

        'Network': {
            'base': 'LogicalComponent',
            'meta_type': 'OpenStackInfrastructureNetwork',
            'label': 'Network',
            'order': 12,
            'properties': {
                'admin_state_up': {'label': 'Admin State', 'content_width': 30},
                'netExternal':    {'label': 'External', 'order': 12.8, 'content_width': 30},
                'netId':          {'label': 'Network ID', 'grid_display': False},
                'netStatus':      {'label': 'Status', 'order': 12.7, 'content_width': 30},
                'netType':        {'label': 'Type', 'order': 12.10, 'content_width': 30},
                'title':          {'label': 'Network', 'grid_display': False},
            },
            'relationships': {
                'ports':       {'grid_display': True, 'content_width': 30},    # Set on ports
                'subnets':     {'grid_display': True, 'content_width': 30},    # Set on subnets
                },
            'dynamicview_relations': {
                'impacted_by': ['networkAgents'],
                'impacts': ['subnets', 'tenant']
            }
        },

        'Subnet': {
            'base': 'LogicalComponent',
            'meta_type': 'OpenStackInfrastructureSubnet',
            'label': 'Subnet',
            'order': 14,
            'properties': {
                'subnetId':        {'grid_display': False, 'label': 'Subnet ID'},
                'cidr':            {'label': 'CIDR', 'content_width': 100},
                'dns_nameservers': {'type': 'lines', 'label': 'DNS Servers'},
                'gateway_ip':      {'label': 'Gateway', 'content_width': 100},
            },
            'relationships': {
                'network':   {'label': 'Network', 'content_width': 100},
                },
            'dynamicview_relations': {
                'impacted_by': ['network', 'routers'],
                'impacts': ['port', 'tenant']
            }
        },

        'Router': {
            'base': 'LogicalComponent',
            'meta_type': 'OpenStackInfrastructureRouter',
            'label': 'Router',
            'order': 15,
            'properties': {
                'admin_state_up': {'label': 'AdminState', 'grid_display': False},
                'gateways':       {'label': 'Gateways', 'type_': 'lines'},
                'routerId':       {'label': 'Router ID', 'grid_display': False},
                'routes':         {'label': 'Routes', 'grid_display': False},
                'status':         {'label': 'Status'},
                'title':          {'label': 'Router','grid_display': False},
            },
            'relationships': {
                'network':        {'label': 'External Network', 'content_width': 100},
            },
            'dynamicview_relations': {
                'impacted_by': ['routerAgents'],
                'impacts': ['subnets', 'floatingIps']
            }
        },

        'Port': {
            'base': 'LogicalComponent',
            'meta_type': 'OpenStackInfrastructurePort',
            'label': 'Port',
            'order': 16,
            'properties': {
                'admin_state_up':  {'label': 'AdminState', 'grid_display': False},
                'device_owner':    {'label': 'Owner', 'content_width': 120},
                'mac_address':     {'label': 'MAC', 'content_width': 120},
                'portId':          {'label': 'Port ID', 'grid_display': False},
                'status':          {'label': 'Status'},
                'title':           {'label': 'Port Name', 'grid_display': False},
                'vif_type':        {'label': 'Type'},
            },
            'relationships': {
                'network':         {'label': 'Network'},
            },
            'dynamicview_relations': {
                'impacted_by': ['subnets', 'floatingIps'],
                'impacts': ['instance'],
            }
        },

        # 'SecurityGroup': {
        #     'base': 'LogicalComponent',
        #     'meta_type': 'OpenStackInfrastructureSecurityGroup',
        #     'label': 'Security Group',
        #     'order': 17,
        #     'properties': {
        #         'sgId':  {'label': 'Security Group ID', 'grid_display': True},
        #         'title': {'label': 'SG Name', 'grid_display': True},
        #         # 'rules': {'label': 'Rules'},
        #     },
        #     'relationships': {
        #         'tenant':          {'grid_display': False},
        #     },
        # },

        # 'SecurityGroupRule': {
        #     'base': 'LogicalComponent',
        #     'meta_type': 'OpenStackInfrastructureSecurityGroupRule',
        #     'label': 'Security Group Rule',
        #     'order': 18,
        #     'properties': {
        #         'sgrId':       {'grid_display': False,
        #                          'label': 'Security Group ID'},
        #         'sgId':        {'label': 'Security Group'},
        #         'direction':   {'label': 'Direction'},          # ingress, egress
        #         'type':        {'label': 'Type'},               # ipv4, ipv6
        #     }
        # },

        'FloatingIp': {
            'base': 'LogicalComponent',
            'meta_type': 'OpenStackInfrastructureFloatingIp',
            'label': 'Floating IP',
            'order': 19,
            'properties': {
                'floatingipId':           {'label': 'Security Group ID',
                                           'grid_display': False},
                'fixed_ip_address':       {'label': 'Address'},
                'floating_ip_address':    {'grid_display': False},
                'floating_network_id':    {'grid_display': False},
                'port_id':                {'grid_display': False},
                'status':                 {'label': 'Status'},
            },
            'relationships': {
                'network':                {'grid_display': True},
                'port':                   {'grid_display': True},
                'router':                 {'grid_display': True},
                },
            'dynamicview_relations': {
                'impacted_by': ['router'],
                'impacts': ['port'],
            }
        },

    },
    class_relationships = zenpacklib.relationships_from_yuml(RELATIONSHIPS_YUML),
)

CFG.create()


import os
import logging
log = logging.getLogger('zen.OpenStack')

from Products.ZenUtils.Utils import zenPath, unused
from . import schema


class ZenPack(schema.ZenPack):
    def install(self, app):
        super(ZenPack, self).install(app)
        self.chmodScripts()
        self.symlinkScripts()
        self.installBinFile('openstack_amqp_config')

    def remove(self, app, leaveObjects=False):
        if not leaveObjects:
            self.removeScriptSymlinks()
            self.removeBinFile('openstack_amqp_config')

        super(ZenPack, self).remove(app, leaveObjects=leaveObjects)

    def chmodScripts(self):
        for script in ('poll_openstack.py', 'openstack_amqp_init.py',
                       'queue_counts.py', 'openstack_helper.py'):
            os.system('chmod 0755 {0}'.format(self.path(script)))

    def symlinkScripts(self):
        for script in ('openstack_amqp_init.py',):
            log.info('Linking %s into $ZENHOME/libexec/' % script)
            script_path = zenPath('libexec', script)
            os.system('ln -sf {0} {1}'.format(
                self.path('openstack_amqp_init.py'), script_path))

    def removeScriptSymlinks(self):
        for script in ('poll_openstack.py', 'openstack_amqp_init.py',
                       'queue_counts.py', 'openstack_helper.py',):
            if os.path.exists(zenPath('libexec', script)):
                log.info('Removing %s link from $ZENHOME/libexec/' % script)
                os.system('rm -f {0}'.format(zenPath('libexec', script)))


# Patch last to avoid import recursion problems.
from ZenPacks.zenoss.OpenStackInfrastructure import patches
unused(patches)
