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

from .NeutronIntegrationComponent import NeutronIntegrationComponent


# Useful to avoid making literal string references to module and class names
# throughout the rest of the ZenPack.
MODULE_NAME = {}
CLASS_NAME = {}

RELATIONSHIPS_YUML = """
// containing
[Endpoint]++components-endpoint1[OpenstackComponent]
[Instance]++-[Vnic]
// Non-containing M:M
[NeutronAgent]*-.-*[Router]
[NeutronAgent]*-.-*[Network]
[NeutronAgent]*-.-*[Subnet]
// non-containing 1:M
[OrgComponent]*parentOrg-childOrgs1[OrgComponent]
[Host]1hostedSoftware-hostedOn*[SoftwareComponent]
[OrgComponent]1-.-*[Host]
[OrgComponent]1-.-*[SoftwareComponent]
// Non-containing 1:M
// # Tenant -> * (Instance,Network,Subnet,Router,Port,FloatingIp)
[Tenant]1-.-*[Instance]
[Tenant]1-.-*[Network]
[Tenant]1-.-*[Subnet]
[Tenant]1-.-*[Router]
[Tenant]1-.-*[Port]
[Tenant]1-.-*[FloatingIp]
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
// # Ports* <-> * Subnets:
//   Port can have many subnets via fixed_ips.
//   Many Ports can associate to a single Subnet
[Port]*-.-*[Subnet]
[Port]1-.-*[FloatingIp]
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
                    'zenoss.cmd.linux.openstack.libvirt',
                    'zenoss.cmd.linux.openstack.inifiles'
                ],
                'zOpenStackNeutronConfigDir': '/etc/neutron',
                'zSshConcurrentSessions': 5,
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
            },
            'properties': {
                'neutron_core_plugin':            {'grid_display': False,
                                                   'label': 'Neutron Core Plugin'},
                'neutron_mechanism_drivers':      {'grid_display': False,
                                                   'label': 'Neutron ML2 Mechanism Drivers',
                                                   'default': [],
                                                   'type': 'lines'},
                'neutron_type_drivers':           {'grid_display': False,
                                                   'label': 'Neutron ML2 Type Drivers',
                                                   'default': [],
                                                   'type': 'lines'},
                'neutron_ini':                    {'api_only': True,
                                                   'default': None}
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
                'parentOrg': {'label': 'Parent Region', 'order': 1.0},
                'childOrgs': {'label': 'Children', 'order': 1.1},
                'hosts':     {'label': 'Host', 'order': 1.0},
                'softwareComponents': {'label_width': 150},
            },
            # these are inherited by child classes:
            #   'impacted_by': ['childOrgs', 'hosts', 'softwareComponents'],
            #   'impacts': ['parentOrg']

        },

        'SoftwareComponent': {
            'base': 'OpenstackComponent',
            'label': 'Software Component',
            'label_width': 120,
            'filter_display': False,
            'relationships': {
                # Provide better contextual naming for the relationships in the UI.
                # 'hostedOn': {'grid_display': False},
                'hostedOn': {'order': -1, 'content_width': 100},
                'orgComponent': {'grid_display': False,
                                 'label': 'Supporting',
                                 'render_with_type': True,
                                 'order': 1.0,
                                 'content_width': 0}  # need to fix the default width for render_with_type
            },
            'properties': {
                'binary':     {'grid_display': False, 'label': 'Binary',  'order': 1},
                'enabled':    {'label': 'Enabled', 'order': 2,
                               'label_width': 35,
                               'renderer': 'Zenoss.render.openstack_ServiceEnabledStatus'},
                'operStatus': {'label': 'State',   'order': 3,
                               'label_width': 20,
                               'renderer': 'Zenoss.render.openstack_ServiceOperStatus'}
            },
            'extra_paths': [
                ('orgComponent', '(parentOrg)+')
            ]

            # these are inherited by child classes:
            #   'impacted_by': ['hostedOn', 'osprocess_component']
            #   'impacts': ['orgComponent']
        },

        'LogicalComponent': {
            'base': 'OpenstackComponent',
            'filter_display': False,
        },

        # Component Types ############################################

        'Tenant': {
            'base': [NeutronIntegrationComponent, 'OpenstackComponent'],
            'meta_type': 'OpenStackInfrastructureTenant',
            'label': 'Tenant',
            'order': 5,
            'properties': {
                'tenantId':   {'grid_display': False, 'label': 'Tenant ID'},
                'description': {'label': 'Description', 'content_width': 40},
                'implementation_components': {
                    'label': 'Neutron Implementation',
                    'grid_display': False,
                    'type_': 'entity',
                    'api_only': True,
                    'api_backendtype': 'method'
                }
            },
            'relationships': {
                'instances': {'label_width': 50},
                'networks': {'label_width': 50},
                'subnets': {'label_width': 50},
                'routers': {'label_width': 50},
                'ports': {'label_width': 50},
                'floatingIps': {'label_width': 70},
            },
            'dynamicview_views': ['service_view'],
            'dynamicview_relations': {
                'impacted_by': ['instances', 'networks', 'subnets', 'implementation_components']
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
                'imageId':      {'grid_display': False, 'label': 'Image ID'},
                'imageCreated': {'order': 3.1, 'label_width': 140, 'label': 'Created'},
                'imageUpdated': {'order': 3.2, 'label_width': 140, 'label': 'Updated'},
                'imageStatus':  {'order': 3.5, 'label_width': 40, 'label': 'Status'},
            },
            'relationships': {
                'instances':      {'order': 1.3, 'label_width': 50, 'content_width': 10},
            },
        },

        'Instance': {
            'base': 'LogicalComponent',
            'meta_type': 'OpenStackInfrastructureInstance',
            'label': 'Instance',
            'order': 8,
            'properties': {
                'biosUuid':               {'label': 'BIOS UUID', 'grid_display': False},
                'host':                   {'order': 3.0, 'label': 'Host',
                                           'type_': 'entity',
                                           'api_only': True,
                                           'label_width': 90,
                                           'api_backendtype': 'method'},
                'hostId':                 {'grid_display': False, 'label': 'Host ID'},
                'hostName':               {'grid_display': False,
                                           'label': 'Host Name',
                                           'index_type': 'field'},
                'hypervisorInstanceName': {'label': 'Hypervisor Instance Name',
                                              'grid_display': False},
                'privateIps':             {'order': 3.2, 'type_': 'lines',
                                              'label': 'Fixed IPs',
                                              'label_width': 90,},
                'publicIps':              {'order': 3.1, 'type_': 'lines',
                                              'label': 'Floating IPs',
                                              'label_width': 90,},
                'serialNumber':           {'label': 'BIOS Serial Number',
                                              'grid_display': False,
                                              'index_type': 'field',
                                              'index_scope': 'global'},
                'serverBackupDaily':      {'grid_display': False,
                                              'label': 'Daily Server Backup'},
                'serverBackupEnabled':    {'type_': 'boolean',
                                              'label': 'Backup',
                                              'grid_display': False},
                'serverBackupWeekly':     {'grid_display': False,
                                              'label': 'Weekly Server Backup'},
                'serverId':               {'grid_display': False, 'label': 'Server ID'},
                'serverStatus':           {'order': 3.5, 'label':
                                              'Status', 'label_width': 65,},
            },
            'relationships': {
                # 'host':       {'order': 1.0, 'label': 'Host'},
                'hypervisor': {'grid_display': False},
                'ports':      {'grid_display': False, 'label': 'Ports'},
                'vnics':      {'grid_display': False, 'label': 'Vnics'},
                'flavor':     {'order': 1.1, 'label_width': 35, 'content_width': 35},
                'image':      {'order': 1.2, 'label_width': 35, 'content_width': 35},
                'tenant':     {'order': 1.3, 'label_width': 45, 'content_width': 45},
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
                'macaddress': {
                    'order': 1.0,
                    'content_width': 120,
                    'label': 'MAC Address',
                    'index_type': 'field',
                    'index_scope': 'global',
                    'renderer':
                    'Zenoss.render.openstack_uppercase_renderer', },
                'instance': {'label': 'Instance',   # link to the host this is running on.
                         'type_': 'entity',
                         'api_only': True,
                         'api_backendtype': 'method',
                         'order': 1.4}

            },
            'relationships': {
                'instance':   {'grid_display': False},
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
            'filter_hide_from': ['Region', 'Cell', 'AvailabilityZone'],
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
            'filter_hide_from': ['Region', 'Cell', 'AvailabilityZone'],
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
            'filter_hide_from': ['AvailabilityZone'],
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
                                        'label': 'FQDN',
                                        'index_type': 'field'},
                'hostname':            {'label': 'Host Name',
                                        'grid_display': False,
                                        'index_type': 'field'}
            },
            'relationships': {
                'orgComponent': {'label': 'Supporting',
                                 'render_with_type': True,
                                 'order': 1.0,
                                 'content_width': 110}  # need to fix the default width for render_with_type
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
                'impacted_by': ['host'],
            }
        },

        'NeutronAgent': {
            'base': 'SoftwareComponent',
            'meta_type': 'OpenStackInfrastructureNeutronAgent',
            'label': 'Neutron Agent',
            'order': 11,
            'properties': {
                'agentId':    {'grid_display': False, 'label': 'Agent ID'},
                'operStatus': {'order': 11.100,
                               'label': 'Status',
                               'label_width': 40,
                               'renderer': 'Zenoss.render.openstack_ServiceOperStatus'},
                'type':       {'label': 'Type',
                               'order': 1.1,
                               'content_width': 60},
            },
            'relationships': {
                'networks':      {'order': 1.1, 'label_width': 45},
                'subnets':       {'order': 1.2, 'label_width': 40},
                'routers':       {'order': 1.3, 'label_width': 40},
            },
            'dynamicview_relations': {
                'impacts': ['networks', 'subnets', 'routers'],
                'impacted_by': ['hostedOn'],
            }
        },

        'Network': {
            'base': [NeutronIntegrationComponent, 'LogicalComponent'],
            'meta_type': 'OpenStackInfrastructureNetwork',
            'label': 'Network',
            'order': 12,
            'properties': {
                'admin_state_up': {'order': 2.20, 'label': 'Admin State',
                                     'label_width': 54,
                                     'renderer': 'Zenoss.render.openstack_ServiceEnabledStatus'},
                'netExternal':    {'grid_display': False, 'label': 'Net External'},
                'netId':          {'grid_display': False, 'label': 'Net ID'},
                'netStatus':      {'order': 2.19, 'label': 'Status', 'label_width': 35},
                'netType':        {'order': 2.10, 'label': 'Type', 'label_width': 40},
                'title':          {'grid_display': False, 'label': 'Title'},
                'implementation_components': {
                    'label': 'Neutron Implementation',
                    'grid_display': False,
                    'type_': 'entity',
                    'api_only': True,
                    'api_backendtype': 'method'
                }
            },
            'relationships': {
                'floatingIps':    {'grid_display': False},
                'neutronAgents':  {'grid_display': False},
                'ports':          {'order': 1.1, 'label_width': 25},
                'routers':        {'order': 1.2, 'label_width': 40},
                'subnets':        {'order': 1.3, 'label_width': 40},
                'tenant':         {'order': 1.5, 'label_width': 50},
            },
            'dynamicview_relations': {
                'impacted_by': ['neutronAgents', 'implementation_components'],
                'impacts': ['subnets', 'tenant']
            }
        },

        'Subnet': {
            'base': [NeutronIntegrationComponent, 'LogicalComponent'],
            'meta_type': 'OpenStackInfrastructureSubnet',
            'label': 'Subnet',
            'order': 14,
            'properties': {
                'subnetId':        {'grid_display': False, 'label': 'Subnet ID'},
                'cidr':            {'order': 1.1, 'label': 'CIDR', 'label_width': 90, 'content_width': 70},
                'dns_nameservers': {'grid_display': False, 'label': 'DNS Nameservers'},
                'gateway_ip':      {'label': 'Gateway', 'label_width': 50, 'content_width': 90},
                'implementation_components': {
                    'label': 'Neutron Implementation',
                    'grid_display': False,
                    'type_': 'entity',
                    'api_only': True,
                    'api_backendtype': 'method'
                }
            },
            'relationships': {
                'network':        {'order': 2.0, 'label': 'Network', 'label_width': 80},
                'neutronAgents':  {'grid_display': False},
                'ports':          {'order': 2.1, 'label_width': 35},
                'routers':        {'order': 2.2, 'label_width': 45},
                'tenant':         {'order': 2.3, 'label_width': 50},
            },
            'dynamicview_relations': {
                'impacted_by': ['network', 'routers', 'neutronAgents', 'implementation_components'],
                'impacts': ['port', 'tenant']
            }
        },

        'Router': {
            'base': [NeutronIntegrationComponent, 'LogicalComponent'],
            'meta_type': 'OpenStackInfrastructureRouter',
            'label': 'Router',
            'order': 15,
            'properties': {
                'admin_state_up': {'order': 1.1, 'label': 'Admin State', 'grid_display': False},
                'gateways':       {'order': 1.2, 'label': 'Gateways', 'type_': 'lines'},
                'routerId':       {'order': 1.3, 'label': 'Router ID', 'grid_display': False},
                'routes':         {'order': 1.4, 'label': 'Routes', 'grid_display': False},
                'status':         {'order': 1.5, 'label': 'Status', 'label_width': 35},
                'title':          {'order': 1.6, 'label': 'Router', 'grid_display': False},
                'implementation_components': {
                    'label': 'Neutron Implementation',
                    'grid_display': False,
                    'type_': 'entity',
                    'api_only': True,
                    'api_backendtype': 'method'
                }
            },
            'relationships': {
                'floatingIps':    {'order': 2.3, 'label': 'Floating IPs', 'label_width': 60},
                'network':        {'order': 2.1, 'label': 'External Network', 'content_width': 90},
                'neutronAgents':  {'grid_display': False},
                'subnets':        {'order': 2.2, 'label': 'Subnets', 'label_width': 40},
                'tenant':         {'order': 2.4, 'label_width': 45, 'content_width': 50},
            },
            'dynamicview_relations': {
                'impacted_by': ['neutronAgents', 'implementation_components'],
                'impacts': ['subnets', 'floatingIps']
            }
        },

        'Port': {
            'base': [NeutronIntegrationComponent, 'LogicalComponent'],
            'meta_type': 'OpenStackInfrastructurePort',
            'label': 'Port',
            'order': 16,
            'properties': {
                'admin_state_up':  {'label': 'Admin State',
                                    'label_width': 60,
                                    'content_width': 50,
                                    'order': 1.20,
                                    'renderer': 'Zenoss.render.openstack_ServiceEnabledStatus'},
                'device_owner':    {'grid_display': False,
                                    'label': 'Device Owner',
                                    'order': 1.18},
                'fixed_ip_list':   {'label': 'Fixed IPs', 'label_width': 70, 'order': 1.12},
                'mac_address':     {'label': 'MAC',
                                    'content_width': 105,
                                    'order': 1.14},
                'portId':          {'grid_display': False,
                                    'label': 'Port ID',
                                    'label_width': 40},
                'status':          {'label': 'Status', 'label_width': 35, 'order': 1.19},
                'title':           {'label': 'Title', 'grid_display': False},
                'vif_type':        {'label': 'Type',
                                    'label_width': 30,
                                    'order': 1.13},
                'implementation_components': {
                    'label': 'Neutron Implementation',
                    'grid_display': False,
                    'type_': 'entity',
                    'api_only': True,
                    'api_backendtype': 'method'
                }
            },
            'relationships': {
                'floatingIps':     {'grid_display': False},
                'instance':        {'grid_display': True,
                                    'content_width': 40,
                                    'label_width': 40,
                                    'order': 1.1},
                'network':         {'label': 'Network',
                                    'label_width': 40,
                                    'order': 1.2},
                'subnets':         {'grid_display': False},
                'tenant':          {'grid_display': True,
                                    'label_width': 35,
                                    'content_width': 35,
                                    'order': 1.3},
            },
            'dynamicview_relations': {
                'impacted_by': ['subnets', 'floatingIps', 'implementation_components'],
                'impacts': ['instance'],
            }
        },

        'FloatingIp': {
            'base': [NeutronIntegrationComponent, 'LogicalComponent'],
            'meta_type': 'OpenStackInfrastructureFloatingIp',
            'label': 'Floating IP',
            'order': 19,
            'properties': {
                'floatingipId':           {'grid_display': False, 'label': 'Floating ID'},
                'fixed_ip_address':       {'order': 2.2, 'label_width': 80, 'content_width': 80, 'label': 'Attached IP'},
                'floating_ip_address':    {'order': 2.3, 'label_width': 80, 'content_width': 80, 'label': 'Floating IP'},
                'status':                 {'order': 2.6, 'label_width': 35, 'label': 'Status'},
                'implementation_components': {
                    'label': 'Neutron Implementation',
                    'grid_display': False,
                    'type_': 'entity',
                    'api_only': True,
                    'api_backendtype': 'method'
                },
            },
            'relationships': {
                'network':        {'grid_display': False, 'order': 1.1, 'label_width': 40},
                'port':           {'order': 1.2, 'label_width': 90},
                'router':         {'order': 1.3, 'label_width': 50},
                'tenant':         {'order': 1.4, 'label_width': 50},
                },
            'dynamicview_relations': {
                'impacted_by': ['router', 'implementation_components'],
                'impacts': ['port'],
            }
        },

    },
    class_relationships=zenpacklib.relationships_from_yuml(RELATIONSHIPS_YUML),
)

CFG.create()


import os
import logging
log = logging.getLogger('zen.OpenStack')

from Products.ZenUtils.Utils import unused
from OFS.CopySupport import CopyError

from . import schema


class ZenPack(schema.ZenPack):
    def install(self, app):
        self._migrate_productversions()

        super(ZenPack, self).install(app)
        self.chmodScripts()

    def _migrate_productversions(self):
        # Rename products for openstack versions which did not yet have names
        # in previous versions of the zenpack.   This can not be done in a
        # traditional migrate script because it needs to happen before
        # objects.xml is loaded.
        rename_versions = {
            "2015.2": "Liberty (2015.2)"
        }
        try:
            os_products = self.dmd.getObjByPath("Manufacturers/OpenStack/products")
        except KeyError:
            # First time installing the zenpack.. no prior versions in there.
            pass
        else:
            for old_version, new_version in rename_versions.iteritems():
                if old_version in os_products.objectIds():
                    try:
                        os_products.manage_renameObject(old_version, new_version)
                        log.debug("Migrated version '%s' to '%s'" % (old_version, new_version))
                    except CopyError:
                        raise Exception("Version '%s' is invalid or already in use." % new_version)

    def remove(self, app, leaveObjects=False):
        super(ZenPack, self).remove(app, leaveObjects=leaveObjects)

    def chmodScripts(self):
        for script in ('poll_openstack.py',
                       'openstack_amqp_init.py',
                       'openstack_helper.py'):
            os.system('chmod 0755 {0}'.format(self.path(script)))

# Patch last to avoid import recursion problems.
from ZenPacks.zenoss.OpenStackInfrastructure import patches
unused(patches)
