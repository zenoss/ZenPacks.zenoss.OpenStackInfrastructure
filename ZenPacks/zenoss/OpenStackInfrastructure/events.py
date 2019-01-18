##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2019, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

# These functions process openstack events (as received from ceilometer) into
# ObjectMaps.


from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.ZenUtils.Utils import prepId
from ZenPacks.zenoss.OpenStackInfrastructure.utils import (get_subnets_from_fixedips,
                                                           get_port_instance,
                                                           getNetSubnetsGws_from_GwInfo,
                                                           get_port_fixedips,
                                                           is_uuid,
                                                           )
import ast

import logging
LOG = logging.getLogger('zen.OpenStack.events')


# -----------------------------------------------------------------------------
# ID Functions
# -----------------------------------------------------------------------------
def make_id(evt, prefix, try_traits=[]):
    """Return a valid id in "<prefix>-<raw_id>" format"""
    for traitname in try_traits:
        raw_id = evt.get(traitname, None)
        if raw_id is not None:
            return prepId("{0}-{1}".format(prefix, raw_id))

    # unable to find a valid component ID in this event.
    return None


def instance_id(evt):
    return make_id(evt, 'server', ['trait_instance_id', 'trait_resource_id'])


def instance_name(evt):
    return evt.get("trait_display_name", instance_id(evt))


def floatingip_id(evt):
    return make_id(evt, 'floatingip', ['trait_id', 'trait_resource_id'])


def floatingip_name(evt):
    return floatingip_id(evt)


def network_id(evt):
    return make_id(evt, 'network', ['trait_id', 'trait_resource_id'])


def network_name(evt):
    return evt.get("trait_name", network_id(evt))


def port_id(evt):
    return make_id(evt, 'port', ['trait_id', 'trait_resource_id'])


def port_name(evt):
    return evt.get("trait_name", port_id(evt))


def router_id(evt):
    return make_id(evt, 'router', ['trait_id', 'trait_resource_id'])


def router_name(evt):
    return evt.get("trait_name", router_id(evt))


def subnet_id(evt):
    return make_id(evt, 'subnet', ['trait_id', 'trait_resource_id'])


def subnet_name(evt):
    return evt.get("trait_name", subnet_id(evt))


def tenant_id(evt):
    return make_id(evt, 'tenant', ['trait_tenant_id'])


def volume_id(evt):
    return make_id(evt, 'volume', ['trait_volume_id', 'trait_resource_id'])


def volume_name(evt):
    return volume_id(evt)


def volsnapshot_id(evt):
    return make_id(evt, 'volsnapshot', ['trait_snapshot_id', 'trait_resource_id'])


def volsnapshot_name(evt):
    return volsnapshot_id(evt)


# -----------------------------------------------------------------------------
# Traitmap Functions
# -----------------------------------------------------------------------------
def _apply_neutron_traits(evt, objmap, traitmap):
    for trait in traitmap:
        for prop_name in traitmap[trait]:
            trait_field = 'trait_' + trait
            if trait_field in evt:
                # Cast trait_admin_state_up to boolean for renderers
                if trait_field == 'trait_admin_state_up':
                    value = str(evt.get('trait_admin_state_up')).lower() == 'true'
                else:
                    value = evt.get(trait_field)
                setattr(objmap, prop_name, value)

    # Set the Tenant ID
    if 'trait_tenant_id' in evt:
        setattr(objmap, 'set_tenant', tenant_id(evt))


def _apply_trait_rel(evt, objmap, trait_name, class_rel):
    ''' Generic: Set the class relation's set_* attribute: (ex: set_network)
        Ex: _apply_trait_rel(evt, objmap, 'trait_network_id', 'network')
    '''

    if trait_name in evt:
        attrib_id = make_id(evt, class_rel, [trait_name])
        # for volume attaching to an instance, we do:
        # volume['set_instance'] = 'server-<instance id>'
        if 'instance' in trait_name and 'server' in class_rel:
            # volume attaching to an instance
            setattr(objmap, 'set_instance', attrib_id)
        else:
            set_name = 'set_' + class_rel
            setattr(objmap, set_name, attrib_id)


def _apply_router_gateway_info(evt, objmap):
    ''' Get the router gateways, network, and subnets'''
    if 'trait_external_gateway_info' in evt:

        ext_gw_info = ast.literal_eval(evt['trait_external_gateway_info'])
        if ext_gw_info:
            gateways = set()
            subnets = set()
            (network, subnets, gateways) = getNetSubnetsGws_from_GwInfo(ext_gw_info)

            net_id = make_id('network', network)
            subnet_ids = ['subnet-{0}'.format(x) for x in subnets]

            setattr(objmap, 'gateways', list(gateways))
            setattr(objmap, 'set_network', net_id)
            setattr(objmap, 'set_subnets', subnet_ids)


def _apply_dns_info(evt, objmap):
    ''' Get the dns servers for subnets as a string'''
    if 'trait_dns_nameservers' in evt:
        dns_info = ast.literal_eval(evt['trait_dns_nameservers'])
        servers = ", ".join(dns_info)
        setattr(objmap, 'dns_nameservers', servers)


def _apply_instance_traits(evt, objmap):
    traitmap = {
        'instance_id': ['resourceId', 'serverId'],
        'state': ['serverStatus'],
        'flavor_name': ['set_flavor_name'],
        'instance_type': ['set_flavor_name'],
        'host_name': ['set_host_name'],
        'host': ['set_host_name'],
        'image_name': ['set_image_name'],
        'tenant_id': ['set_tenant_id']
    }
    for trait in traitmap:
        for prop_name in traitmap[trait]:
            trait_field = 'trait_' + trait
            if trait_field in evt:
                value = evt.get(trait_field)

                # Store server status in uppercase, to match how the nova-api
                # shows it.
                if prop_name == 'serverStatus':
                    value = value.upper()

                setattr(objmap, prop_name, value)

    for prop_name in ['title', 'hostName']:
        setattr(objmap, prop_name, instance_name(evt))

    # special case for publicIps / privateIps
    if 'trait_fixed_ips' in evt:
        try:
            fixed_ips = ast.literal_eval(evt['trait_fixed_ips'])
            public_ips = set()
            private_ips = set()
            # Assume: Fixed_ips are private, floating_ips are external/public:
            for ip in fixed_ips:
                private_ips.add(ip['address'])
                for fip in ip['floating_ips']:
                    public_ips.add(fip)
            setattr(objmap, 'privateIps', list(private_ips))
            # public_ips may not be listed, so don't delete existing ones.
            if public_ips:
                setattr(objmap, 'publicIps', list(public_ips))
        except Exception, e:
            LOG.debug("Unable to parse trait_fixed_ips=%s (%s)" % (evt['trait_fixed_ips'], e))


def _apply_cinder_traits(evt, objmap):
    traitmap = {
        'status': ['status'],
        'display_name': ['title'],
        'availability_zone': ['avzone'],
        'created_at': ['created_at'],
        'volume_id': ['volumeId'],
        'resource_id': ['volumeId'],
        'host': ['host'],
        'type': ['volume_type'],
        'size': ['size'],
    }
    if 'VolSnapshot' in objmap.modname:
        # volume snapshot events do not not have these, so don't try to apply them even
        # if they are found.
        traitmap.pop('volume_id', None)
        traitmap.pop('availability_zone', None)
        traitmap.pop('host', None)
        traitmap.pop('type', None)

    for trait in traitmap:
        for prop_name in traitmap[trait]:
            trait_field = 'trait_' + trait
            if trait_field in evt:
                value = evt.get(trait_field)
                # awkward!
                if prop_name == 'status':
                    value = value.upper()
                setattr(objmap, prop_name, value)


def instance_objmap(evt):
    return ObjectMap(
        modname='ZenPacks.zenoss.OpenStackInfrastructure.Instance',
        compname='',
        data={
            'id': instance_id(evt),
            'relname': 'components',
            '_add': False
        },
    )


def neutron_objmap(evt, Name):
    """ Create an object map of type Name. Name must be proper module name.
        WARNING: All Neutron events have a 'trait_id' attribute.
                 Make sure that Name.lower() corresponds to a well defined
                 id_function.
    """
    module = 'ZenPacks.zenoss.OpenStackInfrastructure.' + Name
    id_func = eval(Name.lower() + '_id')
    _id = id_func(evt)

    return ObjectMap(
        modname=module,
        compname='',
        data={
            'id': _id,
            'relname': 'components',
            '_add': False
        },
    )


def cinder_objmap(evt, Name):
    """ Create an object map of type Name. Name must be proper module name.
    """
    module = 'ZenPacks.zenoss.OpenStackInfrastructure.' + Name
    id_func = eval(Name.lower() + '_id')
    _id = id_func(evt)

    return ObjectMap(
        modname=module,
        compname='',
        data={
            'id': _id,
            'relname': 'components',
            '_add': False
        }
    )


# -----------------------------------------------------------------------------
# Event Functions
# -----------------------------------------------------------------------------
def instance_create(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    objmap._add = True
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_update(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_delete(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    objmap.remove = True
    return objmap


def instance_update_status(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_powered_on(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_powered_off(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_shutting_down(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_shut_down(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_rebooting(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_rebooted(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_rebuilding(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)

    return objmap


def instance_rebuilt(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_suspended(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_resumed(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_rescue(evt):
    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_unrescue(evt):
    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


# -----------------------------------------------------------------------------
# FloatingIp
# -----------------------------------------------------------------------------

def floatingip_create(evt):
    objmap = floatingip_update(evt)
    if objmap:
        objmap._add = True

    return objmap


def floatingip_update(evt):
    if not floatingip_id(evt):
        LOG.info("Unable to identify floatingip component from event: %s" % evt)
        return None

    traitmap = {
        'fixed_ip_address': ['fixed_ip_address'],
        'floating_ip_address': ['floating_ip_address'],
        'id': ['floatingipId'],
        'resource_id': ['floatingipId'],
        'status': ['status'],
        # See: _apply_neutron_traits: set_tenant
        # _apply_trait_rel:  set_network, set_port, set_router,
        # set_network(floating_network_id)
    }

    objmap = neutron_objmap(evt, "FloatingIp")
    _apply_neutron_traits(evt, objmap, traitmap)

    _apply_trait_rel(evt, objmap, 'trait_floating_network_id', 'network')
    _apply_trait_rel(evt, objmap, 'trait_router_id', 'router')
    _apply_trait_rel(evt, objmap, 'trait_port_id', 'port')
    return objmap


def floatingip_delete_end(evt):
    if not floatingip_id(evt):
        LOG.info("Unable to identify floatingip component from event: %s" % evt)
        return None

    objmap = neutron_objmap(evt, 'FloatingIp')
    objmap.remove = True
    return objmap


# -----------------------------------------------------------------------------
# Network Event Functions
# -----------------------------------------------------------------------------

def network_create(evt):
    objmap = network_update(evt)
    if objmap:
        objmap._add = True

    return objmap


def network_update(evt):
    if not network_id(evt):
        LOG.info("Unable to identify network component from event: %s" % evt)
        return None

    traitmap = {
        'admin_state_up': ['admin_state_up'],
        'id': ['netId'],
        'resource_id': ['netId'],
        'name': ['title'],
        'provider_network_type': ['netType'],
        'router_external': ['netExternal'],
        'status': ['netStatus'],
        # See: _apply_neutron_traits: set_tenant
    }

    objmap = neutron_objmap(evt, "Network")
    _apply_neutron_traits(evt, objmap, traitmap)
    return objmap


def network_delete_end(evt):
    if not network_id(evt):
        LOG.info("Unable to identify network component from event: %s" % evt)
        return None

    objmap = neutron_objmap(evt, 'Network')
    objmap.remove = True
    return objmap


# -----------------------------------------------------------------------------
# Port Event Functions
# -----------------------------------------------------------------------------

def port_create(evt):
    objmap = port_update(evt)
    if objmap:
        objmap._add = True

    return objmap


def port_update(evt):
    if not port_id(evt):
        LOG.info("Unable to identify port component from event: %s" % evt)
        return None

    traitmap = {
        'admin_state_up': ['admin_state_up'],
        'binding_vif_type': ['vif_type'],
        'device_owner': ['device_owner'],
        'id': ['portId'],
        'resource_id': ['portId'],
        'mac_address': ['mac_address'],
        'name': ['title'],
        'status': ['status'],
        # See: _apply_neutron_traits: set_tenant, set_network
    }

    objmap = neutron_objmap(evt, "Port")
    _apply_neutron_traits(evt, objmap, traitmap)
    _apply_trait_rel(evt, objmap, 'trait_network_id', 'network')

    if 'trait_device_id' in evt and 'trait_device_owner' in evt:
        port_instance = get_port_instance(evt['trait_device_owner'],
                                          evt['trait_device_id'])
        setattr(objmap, 'set_instance', port_instance)

    # get subnets and fixed_ips
    if 'trait_fixed_ips' in evt:
        port_fips = ast.literal_eval(evt['trait_fixed_ips'])
        _subnets = get_subnets_from_fixedips(port_fips)
        port_subnets = [prepId('subnet-{}'.format(x)) for x in _subnets]
        port_fixedips = get_port_fixedips(port_fips)
        setattr(objmap, 'set_subnets', port_subnets)
        setattr(objmap, 'fixed_ip_list', port_fixedips)

    return objmap


def port_delete_end(evt):
    objmap = neutron_objmap(evt, 'Port')
    objmap.remove = True
    return objmap


# -----------------------------------------------------------------------------
# Router Event Functions
# -----------------------------------------------------------------------------

def router_create(evt):
    objmap = router_update(evt)
    if objmap:
        objmap._add = True

    return objmap


def router_update(evt):
    if not router_id(evt):
        LOG.info("Unable to identify router component from event: %s" % evt)
        return None

    traitmap = {
        'admin_state_up': ['admin_state_up'],
        'id': ['routerId'],
        'resource_id': ['routerId'],
        'routes': ['routes'],
        'status': ['status'],
        'name': ['title'],
        # See: _apply_router_gateway_info:
        # (gateways, set_subnets, set_network)
    }

    objmap = neutron_objmap(evt, "Router")
    _apply_neutron_traits(evt, objmap, traitmap)
    _apply_router_gateway_info(evt, objmap)
    return objmap


def router_delete_end(evt):
    objmap = neutron_objmap(evt, 'Router')
    objmap.remove = True
    return objmap


# -----------------------------------------------------------------------------
# Subnet Event Functions
# -----------------------------------------------------------------------------

def subnet_create(evt):
    objmap = subnet_update(evt)
    if objmap:
        objmap._add = True

    return objmap


def subnet_update(evt):
    if not subnet_id(evt):
        LOG.info("Unable to identify subnet component from event: %s" % evt)
        return None

    traitmap = {
        'cidr': ['cidr'],
        'gateway_ip': ['gateway_ip'],
        'id': ['subnetId'],
        'name': ['title'],
        'network_id': ['subnetId'],
        # See: _apply_dns_info(): dns_nameservers
        # _apply_neutron_traits: set_tenant, set_network,
    }

    objmap = neutron_objmap(evt, "Subnet")
    _apply_dns_info(evt, objmap)
    _apply_neutron_traits(evt, objmap, traitmap)
    _apply_trait_rel(evt, objmap, 'trait_network_id', 'network')
    return objmap


def subnet_delete_end(evt):
    objmap = neutron_objmap(evt, 'Subnet')
    objmap.remove = True
    return objmap


# -----------------------------------------------------------------------------
# Volume Event Functions
# -----------------------------------------------------------------------------
def volume_create(evt):
    objmap = volume_update(evt)
    if objmap:
        objmap._add = True

    return objmap


def volume_update(evt):
    if not volume_id(evt):
        LOG.info("Unable to identify volume component from event: %s" % evt)
        return None

    objmap = cinder_objmap(evt, "Volume")
    _apply_cinder_traits(evt, objmap)

    if 'trait_tenant_id' in evt:
        _apply_trait_rel(evt, objmap, 'trait_tenant_id', 'tenant')
    elif 'trait_project_id' in evt:
        _apply_trait_rel(evt, objmap, 'trait_project_id', 'tenant')

    if 'trait_instance_id' in evt and len(evt['trait_instance_id']):
        # the volume is being attached to an instance
        _apply_trait_rel(evt, objmap, 'trait_instance_id', 'server')

    if 'detach.end' in evt['openstack_event_type']:
        # the volume is being detached from an instance
        setattr(objmap, 'set_instance', None)

    # make sure objmap has volume_type and volume_type is uuid
    if hasattr(objmap, 'volume_type') and is_uuid(objmap.volume_type):
        # set volume type
        _apply_trait_rel(evt, objmap, 'trait_type', 'volType')

    return objmap


def volume_delete_end(evt):
    if not volume_id(evt):
        LOG.info("Unable to identify volume component from event: %s" % evt)
        return None

    objmap = cinder_objmap(evt, 'Volume')
    objmap.remove = True
    return objmap


# -----------------------------------------------------------------------------
# Snapshot Event Functions
# -----------------------------------------------------------------------------
def volsnapshot_create(evt):
    if not volsnapshot_id(evt):
        LOG.info("Unable to identify volsnapshot component from event: %s" % evt)
        return None

    objmap = cinder_objmap(evt, "VolSnapshot")
    objmap._add = True
    _apply_cinder_traits(evt, objmap)

    if 'trait_tenant_id' in evt:
        _apply_trait_rel(evt, objmap, 'trait_tenant_id', 'tenant')
    elif 'trait_project_id' in evt:
        _apply_trait_rel(evt, objmap, 'trait_project_id', 'tenant')

    _apply_trait_rel(evt, objmap, 'trait_volume_id', 'volume')
    return objmap


def volsnapshot_delete_end(evt):
    if not volsnapshot_id(evt):
        LOG.info("Unable to identify volsnapshotcomponent from event: %s" % evt)
        return None

    objmap = cinder_objmap(evt, 'VolSnapshot')
    objmap.remove = True
    return objmap


# For each event type, associate it with the appropriate mapper function.
# A mapper function is expected to take an event and return one or more objmaps.
# it may also modify the event, for instance by add missing information
# such as a summary.

MAPPERS = {
    'compute.instance.create.start': instance_create,
    'compute.instance.create.end': instance_update,
    'compute.instance.create.error': instance_update,
    'compute.instance.update': instance_update_status,
    'compute.instance.delete.end': instance_delete,

    # Note: I do not currently have good test data for what a real
    # live migration looks like.  I am assuming that the new host will be
    # carried in the last event, and only processing that one.
    'compute.instance.live_migration._post.end': instance_update,

    'compute.instance.power_off.end': instance_powered_off,
    'compute.instance.power_on.end': instance_powered_on,
    'compute.instance.reboot.start': instance_rebooting,
    'compute.instance.reboot.end': instance_rebooted,
    'compute.instance.shutdown.start': instance_shutting_down,
    'compute.instance.shutdown.end': instance_shut_down,
    'compute.instance.rebuild.start': instance_rebuilding,
    'compute.instance.rebuild.end': instance_rebuilt,

    'compute.instance.rescue.end': instance_rescue,
    'compute.instance.unrescue.end': instance_unrescue,

    'compute.instance.finish_resize.end': instance_update,
    'compute.instance.resize.revert.end': instance_update,
    'compute.instance.resize.end': instance_update,


    'compute.instance.suspend': instance_suspended,
    'compute.instance.resume': instance_resumed,

    # -------------------------------------------------------------------------
    #  Floating IP's
    # -------------------------------------------------------------------------
    'floatingip.create.end': floatingip_create,
    'floatingip.update.start': floatingip_update,
    'floatingip.update.end': floatingip_update,
    'floatingip.delete.end': floatingip_delete_end,

    # -------------------------------------------------------------------------
    #  Network
    # -------------------------------------------------------------------------
    'network.create.end': network_create,
    'network.update.end': network_update,
    'network.delete.end': network_delete_end,

    # -------------------------------------------------------------------------
    #  Port
    # -------------------------------------------------------------------------
    'port.create.end': port_create,
    'port.update.end': port_update,
    'port.delete.end': port_delete_end,

    # -------------------------------------------------------------------------
    #  Routers
    # -------------------------------------------------------------------------
    'router.create.end': router_create,
    'router.update.end': router_update,
    'router.delete.end': router_delete_end,

    # -------------------------------------------------------------------------
    #  Subnet
    # -------------------------------------------------------------------------
    'subnet.create.end': subnet_create,
    'subnet.update.end': subnet_update,
    'subnet.delete.end': subnet_delete_end,

    # -------------------------------------------------------------------------
    #  Volume
    #
    # volume attaching to instance job flow:
    # 1. volume.attach.start
    # 2. volume.attach.end
    # 3. compute.instance.volume.attach
    # volume detaching from instance job flow:
    # 1. compute.instance.volume.detach
    # 2. volume.detach.start
    # 3. volume.detach.end
    # -------------------------------------------------------------------------
    'volume.create.end': volume_create,
    'volume.update.end': volume_update,
    'volume.delete.end': volume_delete_end,
    'volume.attach.end': volume_update,
    'volume.detach.end': volume_update,

    # -------------------------------------------------------------------------
    #  Snapshot
    # -------------------------------------------------------------------------
    'snapshot.create.end': volsnapshot_create,
    'snapshot.delete.end': volsnapshot_delete_end,
}


def event_is_mapped(evt):
    return evt.get('openstack_event_type') in MAPPERS


def map_event(evt):
    # given an event dictionary, return an ObjectMap, or None.

    # The evt dictionary is expected to contain the keys 'openstack_event_type'
    # and one "trait_<trait name>" for all each of the traits in the ceilometer
    # event.

    event_type = evt.get('openstack_event_type')

    if event_type and event_type in MAPPERS:
        return MAPPERS[event_type](evt)

