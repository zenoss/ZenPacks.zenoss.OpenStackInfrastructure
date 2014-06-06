##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013-2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""ZenPacks.zenoss.OpenStack - OpenStack monitoring for Zenoss.

This module contains initialization code for the ZenPack. Everything in
the module scope will be executed at startup by all Zenoss Python
processes.

The initialization order for ZenPacks is defined by
$ZENHOME/ZenPacks/easy-install.pth.

"""

from . import zenpacklib


RELATIONSHIPS_YUML = """
// containing
[Endpoint]++components-endpoint1[OpenstackComponent]
// non-containing 1:M
[OrgComponent]*parentOrg-childOrgs1[OrgComponent]
[Host]1hostedSoftware-hostedOn*[SoftwareComponent]
[OrgComponent]1-.-*[Host]
[OrgComponent]1-.-*[SoftwareComponent]
[Flavor]1-.-*[Server]
[Image]1-.-*[Server]
[Hypervisor]1-.-*[Server]
// non-containing 1:1
[Hypervisor]1-.-1[Host]
"""

CFG = zenpacklib.ZenPackSpec(
    name=__name__,

    zProperties={
        'DEFAULTS': {'category': 'OpenStack',
                     'type': 'string'},

        'zOpenStackInsecure':          {'type': 'boolean', 'default': False},
        'zOpenStackProjectId':         {},
        'zOpenStackAuthUrl':           {},
        'zOpenStackRegionName':        {},
        'zOpenStackHostDeviceClass':   {'default': '/Server/SSH/Linux/NovaHost'}
    },

    classes={
        # Device Types ###############################################

        'Endpoint': {
            'base': zenpacklib.Device,
            'meta_type': 'OpenStackEndpoint',
            'label': 'OpenStack Endpoint'
        },

        'KeystoneEndpoint': {
            'base': 'Endpoint',
            'meta_type': 'OpenStackKeystoneEndpoint',
            'label': 'Keystone Endpoint'
        },

        'NovaEndpoint': {
            'base': 'Endpoint',
            'meta_type': 'OpenStackNovaEndpoint',
            'label': 'Nova Endpoint'
        },

        # Component Base Types #######################################
        'OpenstackComponent': {
            'base': zenpacklib.Component,
        },

        'DeviceProxyComponent': {
            'base': 'OpenstackComponent',
            'properties': {
                'proxy_device': {'label': 'Device',
                                 'type_': 'entity',
                                 'api_only': True,
                                 'api_backendtype': 'method'}
            }
        },

        'OrgComponent': {
            'base': 'OpenstackComponent',
            'relationships': {
                # Provide better contextual naming for the relationships in the UI.
                'parentOrg': {'label': 'Parent', 'order': 1.0},
                'childOrgs': {'label': 'Children', 'order': 1.1},
            }
        },

        'SoftwareComponent': {
            'base': 'OpenstackComponent',
            'properties': {
                'binary':   {'label': 'Binary'},
            }
        },

        'LogicalComponent': {
            'base': 'OpenstackComponent'
        },

        # Component Types ############################################

        'Flavor': {
            'base': 'LogicalComponent',
            'meta_type': 'OpenStackFlavor',
            'label': 'Flavor',
            'order': 1,
            'properties': {
                'flavorId':   {'grid_display': False},                 # 1
                'flavorRAM':  {'type_': 'int',
                               'renderer': 'Zenoss.render.bytesString',
                               'label': 'RAM'},                        # bytes
                'flavorDisk': {'type_': 'int',
                               'renderer': 'Zenoss.render.bytesString',
                               'label': 'Disk'}                        # bytes
            }
        },

        'Image': {
            'base': 'LogicalComponent',
            'meta_type': 'OpenStackImage',
            'label': 'Image',
            'order': 2,
            'properties': {
                'imageId':      {'grid_display': False},
                'imageStatus':  {'label': 'Status'},
                'imageCreated': {'label': 'Created'},
                'imageUpdated': {'label': 'Updated'},
            }
        },

        'Server': {
            'base': 'LogicalComponent',
            'meta_type': 'OpenStackServer',
            'label': 'Server',
            'order': 3,
            'properties': {
                'serverId':            {'grid_display': False},   # 847424
                'serverStatus':        {'label': 'Status'},   # ACTIVE
                'serverBackupEnabled': {'type_': 'boolean',
                                        'label': 'Backup'},    # False
                'serverBackupDaily':   {'grid_display': False},   # DISABLED
                'serverBackupWeekly':  {'grid_display': False},   # DISABLED
                'publicIps':           {'type_': 'lines',
                                        'label': 'Public IPs'},   # ['50.57.74.222']
                'privateIps':          {'type_': 'lines',
                                        'label': 'Private IPs'},  # ['10.182.13.13']
                'hostId':              {'grid_display': False},   # a84303c0021aa53c7e749cbbbfac265f
                'hostName':            {'grid_display': False,
                                        'index_type': 'field'},   # devstack1
            }

            # Note: By (nova) design, hostId is a hash of the actual underlying host and project, and
            # is designed to allow users of a specific project to tell if two VMs are on the same host, nothing
            # more.  It is not a unique identifier of hosts (compute nodes).
        },

        'Region': {
            'base': 'OrgComponent',
            'meta_type': 'OpenStackRegion',
            'label': 'Region',
            'order': 4
        },

        'Cell': {
            'base': 'OrgComponent',
            'meta_type': 'OpenStackCell',
            'label': 'Cell',
            'order': 5
        },

        'AvailabilityZone': {
            'base': 'OrgComponent',
            'meta_type': 'OpenStackAvailabilityZone',
            'label': 'Availability Zone',
            'order': 6
        },

        'Host': {
            'base': 'DeviceProxyComponent',
            'meta_type': 'OpenStackHost',
            'label': 'Host',
            'order': 8
        },

        'NovaService': {
            'base': 'SoftwareComponent',
            'meta_type': 'OpenStackNovaService',
            'label': 'Nova Service',
            'order': 10
        },

        'NovaApi': {
            'base': 'SoftwareComponent',
            'meta_type': 'OpenStackNovaApi',
            'label': 'NovaApi',
            'order': 9
        },

        'NovaDatabase': {
            'base': 'SoftwareComponent',
            'meta_type': 'OpenStackNovaDatabase',
            'label': 'NovaDatabase',
            'order': 13
        },

        'Hypervisor': {
            'base': 'OpenstackComponent',   # SoftwareComponent
            'meta_type': 'OpenStackHypervisor',
            'label': 'Hypervisor',
            'order': 14,
            'properties': {
                'hypervisorId':      {'grid_display': False}
            }
        }
    },

    class_relationships=zenpacklib.relationships_from_yuml(RELATIONSHIPS_YUML),
)

CFG.create()
