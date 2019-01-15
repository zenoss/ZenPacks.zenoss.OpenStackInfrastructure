##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2019, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.DataCollector.ApplyDataMap import ApplyDataMap
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
        raw_id = getattr(evt, traitname, None)
        if raw_id is not None:
            return prepId("{0}-{1}".format(prefix, raw_id))

    # unable to find a valid component ID in this event.
    return None


def instance_id(evt):
    return make_id(evt, 'server', ['trait_instance_id', 'trait_resource_id'])


def instance_name(evt):
    return getattr(evt, "trait_display_name", instance_id(evt))


def floatingip_id(evt):
    return make_id(evt, 'floatingip', ['trait_id', 'trait_resource_id'])


def floatingip_name(evt):
    return floatingip_id(evt)


def network_id(evt):
    return make_id(evt, 'network', ['trait_id', 'trait_resource_id'])


def network_name(evt):
    return getattr(evt, "trait_name", network_id(evt))


def port_id(evt):
    return make_id(evt, 'port', ['trait_id', 'trait_resource_id'])


def port_name(evt):
    return getattr(evt, "trait_name", port_id(evt))


def router_id(evt):
    return make_id(evt, 'router', ['trait_id', 'trait_resource_id'])


def router_name(evt):
    return getattr(evt, "trait_name", router_id(evt))


def subnet_id(evt):
    return make_id(evt, 'subnet', ['trait_id', 'trait_resource_id'])


def subnet_name(evt):
    return getattr(evt, "trait_name", subnet_id(evt))


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
            if hasattr(evt, trait_field):
                # Cast trait_admin_state_up to boolean for renderers
                if trait_field == 'trait_admin_state_up':
                    value = str(getattr(evt, 'trait_admin_state_up')).lower() == 'true'
                else:
                    value = getattr(evt, trait_field)
                setattr(objmap, prop_name, value)

    # Set the Tenant ID
    if hasattr(evt, 'trait_tenant_id'):
        setattr(objmap, 'set_tenant', tenant_id(evt))


def _apply_trait_rel(evt, objmap, trait_name, class_rel):
    ''' Generic: Set the class relation's set_* attribute: (ex: set_network)
        Ex: _apply_trait_rel(evt, objmap, 'trait_network_id', 'network')
    '''
    if hasattr(evt, trait_name):
        attrib_id = make_id(class_rel, getattr(evt, trait_name))
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
    if hasattr(evt, 'trait_external_gateway_info'):

        ext_gw_info = ast.literal_eval(evt.trait_external_gateway_info)
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
    if hasattr(evt, 'trait_dns_nameservers'):
        dns_info = ast.literal_eval(evt.trait_dns_nameservers)
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
            if hasattr(evt, trait_field):
                value = getattr(evt, trait_field)

                # Store server status in uppercase, to match how the nova-api
                # shows it.
                if prop_name == 'serverStatus':
                    value = value.upper()

                setattr(objmap, prop_name, value)

    for prop_name in ['title', 'hostName']:
        setattr(objmap, prop_name, instance_name(evt))

    # special case for publicIps / privateIps
    if hasattr(evt, 'trait_fixed_ips'):
        try:
            fixed_ips = ast.literal_eval(evt.trait_fixed_ips)
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
            LOG.debug("Unable to parse trait_fixed_ips=%s (%s)" % (evt.trait_fixed_ips, e))


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
            if hasattr(evt, trait_field):
                value = getattr(evt, trait_field)
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
            'relname': 'components'
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
        data={'id': _id,
              'relname': 'components'
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
        data={'id': _id,
              'relname': 'components'
              },
    )


def event_summary(component_type, component_name, evt):
    """ Gives correct summary for Create/Update event messages
    """
    if '.create' in evt.eventClassKey:
        action = "Created"
    else:
        action = "Updated"
    return "%s %s %s" % (action, component_type, component_name)


# -----------------------------------------------------------------------------
# Event Functions
# -----------------------------------------------------------------------------
def instance_create(evt):
    evt.summary = "Instance %s created" % (instance_name(evt))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_update(evt):
    evt.summary = "Instance %s updated" % (instance_name(evt))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_delete(evt):
    evt.summary = "Instance %s deleted" % (instance_name(evt))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    objmap.remove = True
    return objmap


def instance_update_status(evt):
    evt.summary = add_statuschange_to_msg(
        evt,
        "Instance %s updated" % (instance_name(evt)))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def add_statuschange_to_msg(evt, msg):
    descr = ''
    if hasattr(evt, 'trait_state_description') and evt.trait_state_description:
        descr = ' [%s]' % evt.trait_state_description

    if hasattr(evt, 'trait_old_state'):
        msg = msg + " (status changed from %s to %s%s)" % (
            evt.trait_old_state, evt.trait_state, descr)
    elif hasattr(evt, 'trait_state'):
        msg = msg + " (status changed to %s%s)" % (
            evt.trait_state, descr)

    return msg


def instance_powered_on(evt):
    evt.summary = add_statuschange_to_msg(
        evt,
        "Instance %s powered on" % (instance_name(evt)))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_powered_off(evt):
    evt.summary = add_statuschange_to_msg(
        evt,
        "Instance %s powered off" % (instance_name(evt)))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_shutting_down(evt):
    evt.summary = add_statuschange_to_msg(
        evt,
        "Instance %s shutting down" % (instance_name(evt)))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_shut_down(evt):
    evt.summary = add_statuschange_to_msg(
        evt,
        "Instance %s shut down" % (instance_name(evt)))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_rebooting(evt):
    evt.summary = add_statuschange_to_msg(
        evt,
        "Instance %s rebooting" % (instance_name(evt)))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_rebooted(evt):
    evt.summary = add_statuschange_to_msg(
        evt,
        "Instance %s rebooted" % (instance_name(evt)))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_rebuilding(evt):
    evt.summary = add_statuschange_to_msg(
        evt,
        "Instance %s rebuilding" % (instance_name(evt)))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)

    return objmap


def instance_rebuilt(evt):
    evt.summary = add_statuschange_to_msg(
        evt,
        "Instance %s rebuilt" % (instance_name(evt)))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_suspended(evt):
    evt.summary = "Instance %s suspended" % (instance_name(evt))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_resumed(evt):
    evt.summary = "Instance %s resumed" % (instance_name(evt))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_rescue(evt):
    evt.summary = "Instance %s placed in rescue mode" % (instance_name(evt))

    if not instance_id(evt):
        LOG.info("Unable to identify instance component from event: %s" % evt)
        return None

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


def instance_unrescue(evt):
    evt.summary = "Instance %s removed from rescue mode" % (instance_name(evt))

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return objmap


# -----------------------------------------------------------------------------
# FloatingIp
# -----------------------------------------------------------------------------

def floatingip_update(evt):
    evt.summary = event_summary("FloatingIp", floatingip_name(evt), evt)

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
    evt.summary = "FloatingIp %s deleted" % (floatingip_name(evt))

    if not floatingip_id(evt):
        LOG.info("Unable to identify floatingip component from event: %s" % evt)
        return None

    objmap = neutron_objmap(evt, 'FloatingIp')
    objmap.remove = True
    return objmap


# -----------------------------------------------------------------------------
# Network Event Functions
# -----------------------------------------------------------------------------
def network_update(evt):
    evt.summary = event_summary("Network", network_name(evt), evt)

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
    evt.summary = "Network %s deleted" % (network_name(evt))

    if not network_id(evt):
        LOG.info("Unable to identify network component from event: %s" % evt)
        return None

    objmap = neutron_objmap(evt, 'Network')
    objmap.remove = True
    return objmap


# -----------------------------------------------------------------------------
# Port Event Functions
# -----------------------------------------------------------------------------

def port_update(evt):
    evt.summary = event_summary("Port", port_name(evt), evt)

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

    if hasattr(evt, 'trait_device_id') and hasattr(evt, 'trait_device_owner'):
        port_instance = get_port_instance(evt.trait_device_owner,
                                          evt.trait_device_id)
        setattr(objmap, 'set_instance', port_instance)

    # get subnets and fixed_ips
    if hasattr(evt, 'trait_fixed_ips'):
        port_fips = ast.literal_eval(evt.trait_fixed_ips)
        _subnets = get_subnets_from_fixedips(port_fips)
        port_subnets = [prepId('subnet-{}'.format(x)) for x in _subnets]
        port_fixedips = get_port_fixedips(port_fips)
        setattr(objmap, 'set_subnets', port_subnets)
        setattr(objmap, 'fixed_ip_list', port_fixedips)

    return objmap

def port_delete_end(evt):
    evt.summary = "Port %s deleted" % (port_name(evt))

    objmap = neutron_objmap(evt, 'Port')
    objmap.remove = True
    return objmap


# -----------------------------------------------------------------------------
# Router Event Functions
# -----------------------------------------------------------------------------

def router_update(evt):
    evt.summary = event_summary("Router", router_name(evt), evt)

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
    evt.summary = "Router %s deleted" % (router_name(evt))

    objmap = neutron_objmap(evt, 'Router')
    objmap.remove = True
    return objmap


# -----------------------------------------------------------------------------
# Subnet Event Functions
# -----------------------------------------------------------------------------
def subnet_update(evt):
    evt.summary = event_summary("Subnet", subnet_name(evt), evt)

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
    evt.summary = "Subnet %s deleted" % (subnet_name(evt))

    objmap = neutron_objmap(evt, 'Subnet')
    objmap.remove = True
    return objmap


# -----------------------------------------------------------------------------
# Volume Event Functions
# -----------------------------------------------------------------------------

def volume_update(evt):
    if 'create.end' in evt.eventClassKey:
        # the volume is being created
        evt.summary = "Created Volume %s" % (volume_name(evt))
    elif 'attach.end' in evt.eventClassKey:
        # the volume is being attached to an instance
        evt.summary = "Attach Volume %s to instance %s " % \
            (volume_name(evt), getattr(evt, "trait_instance_id", "[unknown]"))
    elif 'detach.end' in evt.eventClassKey:
        # the volume is being detached from an instance
        evt.summary = "Detach Volume %s from instance" % \
            (volume_name(evt))

    if not volume_id(evt):
        LOG.info("Unable to identify volume component from event: %s" % evt)
        return None

    objmap = cinder_objmap(evt, "Volume")
    _apply_cinder_traits(evt, objmap)

    if hasattr(evt, 'trait_tenant_id'):
        _apply_trait_rel(evt, objmap, 'trait_tenant_id', 'tenant')
    elif hasattr(evt, 'trait_project_id'):
        _apply_trait_rel(evt, objmap, 'trait_project_id', 'tenant')

    if hasattr(objmap, 'instanceId') and len(objmap.instanceId) > 0:
        # the volume is being attached to an instance
        _apply_trait_rel(evt, objmap, 'trait_instance_id', 'server')
    elif 'detach.end' in evt.eventClassKey:
        # the volume is being detached from an instance
        setattr(objmap, 'set_instance', '')
    # make sure objmap has volume_type and volume_type is uuid
    if hasattr(objmap, 'volume_type') and is_uuid(objmap.volume_type):
        # set volume type
        _apply_trait_rel(evt, objmap, 'trait_type', 'volType')

    return objmap


def volume_delete_end(evt):
    evt.summary = "Volume %s deleted" % (volume_name(evt))

    if not volume_id(evt):
        LOG.info("Unable to identify volume component from event: %s" % evt)
        return None

    objmap = cinder_objmap(evt, 'Volume')
    objmap.remove = True
    return objmap


# -----------------------------------------------------------------------------
# Snapshot Event Functions
# -----------------------------------------------------------------------------
def volsnapshot_update(evt):
    evt.summary = "Created Volume Snapshot %s for volume %s" % \
        (volsnapshot_name(evt), volume_name(evt))

    if not volsnapshot_id(evt):
        LOG.info("Unable to identify volsnapshot component from event: %s" % evt)
        return None

    objmap = cinder_objmap(evt, "VolSnapshot")
    _apply_cinder_traits(evt, objmap)

    if hasattr(evt, 'trait_tenant_id'):
        _apply_trait_rel(evt, objmap, 'trait_tenant_id', 'tenant')
    elif hasattr(evt, 'trait_project_id'):
        _apply_trait_rel(evt, objmap, 'trait_project_id', 'tenant')

    _apply_trait_rel(evt, objmap, 'trait_volume_id', 'volume')
    return objmap


def volsnapshot_delete_end(evt):
    evt.summary = "Volume Snapshot %s deleted for volume %s" % \
        (volsnapshot_name(evt), volume_name(evt))

    if not volsnapshot_id(evt):
        LOG.info("Unable to identify volsnapshotcomponent from event: %s" % evt)
        return None

    objmap = cinder_objmap(evt, 'VolSnapshot')
    objmap.remove = True
    return objmap


# For each eventClassKey, associate it with the appropriate mapper function.
# A mapper function is expected to take an event and return one or more objmaps.
# it may also modify the event, for instance by add missing information
# such as a summary.

MAPPERS = {
    'openstack|compute.instance.create.start': (instance_id, instance_create),
    'openstack|compute.instance.create.end': (instance_id, instance_update),
    'openstack|compute.instance.create.error': (instance_id, instance_update),
    'openstack|compute.instance.update': (instance_id, instance_update_status),
    'openstack|compute.instance.delete.end': (instance_id, instance_delete),

    # Note: I do not currently have good test data for what a real
    # live migration looks like.  I am assuming that the new host will be
    # carried in the last event, and only processing that one.
    'openstack|compute.instance.live_migration._post.end': (instance_id, instance_update),

    'openstack|compute.instance.power_off.end': (instance_id, instance_powered_off),
    'openstack|compute.instance.power_on.end': (instance_id, instance_powered_on),
    'openstack|compute.instance.reboot.start': (instance_id, instance_rebooting),
    'openstack|compute.instance.reboot.end': (instance_id, instance_rebooted),
    'openstack|compute.instance.shutdown.start': (instance_id, instance_shutting_down),
    'openstack|compute.instance.shutdown.end': (instance_id, instance_shut_down),
    'openstack|compute.instance.rebuild.start': (instance_id, instance_rebuilding),
    'openstack|compute.instance.rebuild.end': (instance_id, instance_rebuilt),

    'openstack|compute.instance.rescue.end': (instance_id, instance_rescue),
    'openstack|compute.instance.unrescue.end': (instance_id, instance_unrescue),

    'openstack|compute.instance.finish_resize.end': (instance_id, instance_update),
    'openstack|compute.instance.resize.revert.end': (instance_id, instance_update),
    'openstack|compute.instance.resize.end': (instance_id, instance_update),


    'openstack|compute.instance.suspend': (instance_id, instance_suspended),
    'openstack|compute.instance.resume': (instance_id, instance_resumed),

    # -------------------------------------------------------------------------
    #  Floating IP's
    # -------------------------------------------------------------------------
    'openstack|floatingip.create.end': (floatingip_id, floatingip_update),
    'openstack|floatingip.update.start': (floatingip_id, floatingip_update),
    'openstack|floatingip.update.end': (floatingip_id, floatingip_update),
    'openstack|floatingip.delete.end': (floatingip_id, floatingip_delete_end),

    # -------------------------------------------------------------------------
    #  Network
    # -------------------------------------------------------------------------
    'openstack|network.create.end': (network_id, network_update),
    'openstack|network.update.end': (network_id, network_update),
    'openstack|network.delete.end': (network_id, network_delete_end),

    # -------------------------------------------------------------------------
    #  Port
    # -------------------------------------------------------------------------
    'openstack|port.create.end': (port_id, port_update),
    'openstack|port.update.end': (port_id, port_update),
    'openstack|port.delete.end': (port_id, port_delete_end),

    # -------------------------------------------------------------------------
    #  Routers
    # -------------------------------------------------------------------------
    'openstack|router.create.end': (router_id, router_update),
    'openstack|router.update.end': (router_id, router_update),
    'openstack|router.delete.end': (router_id, router_delete_end),

    # -------------------------------------------------------------------------
    #  Subnet
    # -------------------------------------------------------------------------
    'openstack|subnet.create.end': (subnet_id, subnet_update),
    'openstack|subnet.update.end': (subnet_id, subnet_update),
    'openstack|subnet.delete.end': (subnet_id, subnet_delete_end),

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
    'openstack|volume.create.end': (volume_id, volume_update),
    'openstack|volume.update.end': (volume_id, volume_update),
    'openstack|volume.delete.end': (volume_id, volume_delete_end),
    'openstack|volume.attach.end': (volume_id, volume_update),
    'openstack|volume.detach.end': (volume_id, volume_update),

    # -------------------------------------------------------------------------
    #  Snapshot
    # -------------------------------------------------------------------------
    'openstack|snapshot.create.end': (volsnapshot_id, volsnapshot_update),
    'openstack|snapshot.delete.end': (volsnapshot_id, volsnapshot_delete_end),

}


def event_is_mapped(evt):
    return evt.eventClassKey in MAPPERS


def map_event(evt):
    # given an event, return an ObjectMap, or None.

    (idfunc, mapper) = MAPPERS.get(evt.eventClassKey, (None, None))

    if idfunc:
        component_id = idfunc(evt)
        if component_id is None:
            LOG.error("Unable to identify component ID for %s event: %s",
                      evt.eventClassKey, evt.getStateToCopy())
            return None
        evt.component = idfunc(evt)

    if mapper:
        return mapper(evt)


# ==============================================================================
#  This is the main process() function that is called by the Events Transform
#  subsystem. See objects.xml for further detail.
# ==============================================================================
def process(evt, device, dmd, txnCommit):    
    try:
        objectmap = map_event(evt)

        if objectmap:
            adm = ApplyDataMap(device)
            adm._applyDataMap(device, objectmap)
            return 1
        else:
            return 0

    except Exception:
        # We don't want any exceptions to make it back to zeneventd, as
        # this will cause it to disable the transform, which will most likely
        # cause more problems than it solves.  Exceptions are most likely
        # to occur if we receive any event that is not formatted as we
        # expect, and that could cause us to lose all event processing if
        # the transform gets disabled.
        LOG.exception("An exception occurred while processing an openstack event")
        return 0
