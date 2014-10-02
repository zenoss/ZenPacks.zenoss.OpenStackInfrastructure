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
// non-containing 1:M
[OrgComponent]*parentOrg-childOrgs1[OrgComponent]
[Host]1hostedSoftware-hostedOn*[SoftwareComponent]
[OrgComponent]1-.-*[Host]
[OrgComponent]1-.-*[SoftwareComponent]
[Flavor]1-.-*[Instance]
[Image]1-.-*[Instance]
[Tenant]1-.-*[Instance]
[Hypervisor]1-.-*[Instance]
// non-containing 1:1
[Hypervisor]1-.-1[Host]
"""

CFG = zenpacklib.ZenPackSpec(
    name=__name__,

    zProperties={
        'DEFAULTS': {'category': 'OpenStack',
                     'type': 'string'},

        'zOpenStackInsecure':         {'type': 'boolean', 'default': False},
        'zOpenStackProjectId':        {},
        'zOpenStackAuthUrl':          {},
        'zOpenStackInfrastructureRegionName':       {},
        'zOpenStackInfrastructureHostDeviceClass':  {'default': '/Server/SSH/Linux/NovaHost'},
        'zOpenStackInfrastructureNovaApiHosts':     {'type': 'lines'},
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
            'impacts': ['hosts'],
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_group': 'Devices',
            'dynamicview_relations': {'openstack_link': ['region']}
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
#                                 'type_': 'entity',
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
            'impacted_by': ['childOrgs', 'hosts', 'softwareComponents'],
            'impacts': ['parentOrg']
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
            'impacted_by': ['hostedOn', 'osprocess_component'],
            'impacts': ['orgComponent'],
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_relations': {'openstack_link': ['orgComponent']}
        },

        'LogicalComponent': {
            'base': 'OpenstackComponent',
            'filter_display': False,
        },

        # Component Types ############################################

        'Tenant': {
            'base': 'OpenstackComponent',
            'meta_type': 'OpenStackInfrastructureTenant',
            'label': 'Tenant',
            'order': 5,
            'properties': {
                'tenantId':   {'grid_display': False,
                               'label': 'Tenant ID'},
                'description': { 'label': 'Description'},
            },
            'impacted_by': ['instances']
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
                'tenant':     {'label_width': 50, 'content_width': 50},
                'flavor':     {'label_width': 50, 'content_width': 50},
                'image':      {'label_width': 50, 'content_width': 50},
            },
            'impacted_by': ['hypervisor', 'vnics'],
            'impacts': ['guestDevice', 'tenant']

            # Note: By (nova) design, hostId is a hash of the actual underlying host and project, and
            # is designed to allow users of a specific project to tell if two VMs are on the same host, nothing
            # more.  It is not a unique identifier of hosts (compute nodes).
        },

        'Vnic': {
            'base': 'LogicalComponent',
            'meta_type': 'OpenStackInfrastructureVnic',
            'label': 'Vnic',
            'order': 8.5,
            'properties': {
                'macaddress': {'label': 'MAC Address',
                               'index_type': 'field',
                               'index_scope': 'global'}
            },
            'impacts': ['instance']
        },

        'Region': {
            'base': 'OrgComponent',
            'meta_type': 'OpenStackInfrastructureRegion',
            'label': 'Region',
            'order': 1,
            'impacted_by': ['childOrgs', 'hosts', 'softwareComponents'], #inherit
            'impacts': ['parentOrg'],                   #inherit
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_relations': {'openstack_link': ['childOrgs', 'softwareComponents']}
        },

        'Cell': {
            'base': 'OrgComponent',
            'meta_type': 'OpenStackInfrastructureCell',
            'label': 'Cell',
            'order': 3,
            'impacted_by': ['childOrgs', 'hosts', 'softwareComponents'], #inherit
            'impacts': ['parentOrg'],                   #inherit            
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_relations': {'openstack_link': ['childOrgs', 'hosts', 'softwareComponents']}
        },

        'AvailabilityZone': {
            'base': 'OrgComponent',
            'meta_type': 'OpenStackInfrastructureAvailabilityZone',
            'label': 'Availability Zone',
            'order': 2,
            'impacted_by': ['childOrgs', 'hosts', 'softwareComponents'], #inherit
            'impacts': ['parentOrg'],                   #inherit            
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_relations': {'openstack_link': ['childOrgs', 'hosts', 'softwareComponents']}
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
            'impacted_by': ['endpoint', 'proxy_device'],
            'impacts': ['hypervisor', 'orgComponent', 'hostedSoftware'],
            'dynamicview_views': ['service_view', 'openstack_view'],
            'dynamicview_relations': {'openstack_link': ['hostedSoftware', 'hypervisor']}
        },

        'NovaService': {
            'base': 'SoftwareComponent',
            'meta_type': 'OpenStackInfrastructureNovaService',
            'label': 'Nova Service',
            'order': 7,
            'impacted_by': ['hostedOn', 'osprocess_component'], #inherit
            'impacts': ['orgComponent'],  #inherit
            'dynamicview_views': ['service_view', 'openstack_view'],            
        },

        'NovaApi': {
            'base': 'SoftwareComponent',
            'meta_type': 'OpenStackInfrastructureNovaApi',
            'label': 'Nova API',
            'order': 7.1,
            'impacted_by': ['hostedOn', 'osprocess_component'], #inherit
            'impacts': ['orgComponent'],  #inherit
            'dynamicview_views': ['service_view', 'openstack_view'],
        },

        'NovaDatabase': {
            'base': 'SoftwareComponent',
            'meta_type': 'OpenStackInfrastructureNovaDatabase',
            'label': 'NovaDatabase',
            'order': 7.2,
            'impacted_by': ['hostedOn', 'osprocess_component'], #inherit
            'impacts': ['orgComponent'],  #inherit
            'dynamicview_views': ['service_view', 'openstack_view']
        },

        'Hypervisor': {
            'base': 'OpenstackComponent',   # SoftwareComponent
            'meta_type': 'OpenStackInfrastructureHypervisor',
            'label': 'Hypervisor',
            'order': 9.1,
            'properties': {
                'hypervisorId':      {'grid_display': False,
                                      'label': 'Hypervisor ID'},
                'hostfqdn':          {'grid_display': False,
                                      'label': 'FQDN'},
            },
            'impacts': ['instances'],
            'impacted_by': ['host'],
            'dynamicview_views': ['service_view', 'openstack_view']
        },

    },

    class_relationships=zenpacklib.relationships_from_yuml(RELATIONSHIPS_YUML),
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
