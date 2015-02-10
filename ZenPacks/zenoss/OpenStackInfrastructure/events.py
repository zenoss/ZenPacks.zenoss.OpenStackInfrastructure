##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.DataCollector.ApplyDataMap import ApplyDataMap
from Products.ZenUtils.Utils import prepId
import ast

import logging
LOG = logging.getLogger('zen.OpenStack.events')


# Sets of traits we can expect to get (see event_definitions.yaml on the
# openstack side) and what objmap properties they map to.
NEUTRON_TRAITMAPS = {
    'network': {
        'admin_state_up':            ['netState'],
        'name':                      ['title'],
        'id':                        ['netId'],
        'provider_network_type':     ['netType'],
        'router_external':           ['netExternal'],
        'status':                    ['netStatus'],
        'tenant_id':                 ['set_tenant_id']
    },
}


def _apply_instance_traits(evt, objmap):
    traitmap = {
                'display_name': ['title', 'hostName'],
                'instance_id':  ['resourceId', 'serverId'],
                'state':        ['serverStatus'],
                'flavor_name':  ['set_flavor_name'],
                'host_name':    ['set_host_name'],
                'image_name':   ['set_image_name'],
                'tenant_id':    ['set_tenant_id']
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

    # special case for publicIps / privateIps
    if hasattr(evt, 'trait_fixed_ips'):
        try:
            fixed_ips = ast.literal_eval(evt.trait_fixed_ips)
            public_ips = set()
            private_ips = set()
            for ip in fixed_ips:
                if ip['label'].lower() == "public":
                    public_ips.add(ip['address'])
                else:
                    private_ips.add(ip['address'])
            setattr(objmap, 'publicIps', list(public_ips))
            setattr(objmap, 'privateIps', list(private_ips))
        except Exception, e:
            LOG.debug("Unable to parse trait_fixed_ips=%s (%s)" % (evt.trait_fixed_ips, e))


def _apply_network_traits(evt, objmap):
    traitmap = {
                'admin_state_up':            ['netState'],
                'name':                      ['title'],
                'id':                        ['netId'],
                'provider_network_type':     ['netType'],
                'router_external':           ['netExternal'],
                'status':                    ['netStatus'],
                'tenant_id':                 ['set_tenant_id']
                }

    for trait in traitmap:
        for prop_name in traitmap[trait]:
            trait_field = 'trait_' + trait
            if hasattr(evt, trait_field):
                value = getattr(evt, trait_field)
                setattr(objmap, prop_name, value)


def make_id(prefix, original_id):
    """Return a valid id in "<prefix>-<original_id>" format"""
    if not original_id:
        return None
    return '-'.join(map(prepId, (prefix, original_id)))

def instance_id(evt):
    return make_id('server', evt.trait_instance_id)

def network_id(evt):
    return make_id('network', evt.trait_id)

# def instance_id(evt):
#     return 'server-{0}'.format(evt.trait_instance_id)


def instance_objmap(evt):
    return ObjectMap(
        modname='ZenPacks.zenoss.OpenStackInfrastructure.Instance',
        compname='',
        data={
            'id': make_id('server', evt.trait_instance_id),
            'relname': 'components'
        },
    )

def network_objmap(evt):
    return ObjectMap(
        modname='ZenPacks.zenoss.OpenStackInfrastructure.Network',
        compname='',
        data={
            'id': id(evt),
            'relname': 'components'
        },
    )


def instance_create(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s created" % (evt.trait_display_name)

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


def instance_update(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s updated" % (evt.trait_display_name)

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


def instance_delete(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s deleted" % (evt.trait_display_name)

    objmap = instance_objmap(evt)
    objmap.remove = True
    return [objmap]


def instance_update_status(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s updated" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


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


def instance_powering_on(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s powering on" % (evt.trait_display_name)
    return []


def instance_powered_on(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s powered on" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


def instance_powering_off(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s powering off" % (evt.trait_display_name)
    return []


def instance_powered_off(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s powered off" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


def instance_shutting_down(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s shutting down" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


def instance_shut_down(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s shut down" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


def instance_rebooting(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s rebooting" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


def instance_rebooted(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s rebooted" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


def instance_rebuilding(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s rebuilding" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


def instance_rebuilt(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s rebuilt" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


def instance_suspended(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s suspended" % (evt.trait_display_name)

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


def instance_resumed(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s resumed" % (evt.trait_display_name)

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


def instance_rescue(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s placed in rescue mode" % (evt.trait_display_name)

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


def instance_unrescue(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s removed from rescue mode" % (evt.trait_display_name)

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]


def floatingip_create_start(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s placed in rescue mode" % (evt.trait_display_name)

    objmap = instance_objmap(evt)
    _apply_instance_traits(evt, objmap)
    return [objmap]

def floatingip_create_end(device, dmd, evt):
    pass

def floatingip_update_start(device, dmd, evt):
    pass

def floatingip_update_end(device, dmd, evt):
    pass

def floatingip_delete_start(device, dmd, evt):
    pass

def floatingip_delete_end(device, dmd, evt):
    pass


# For each eventClassKey, associate it with the appropriate mapper function.
# A mapper function is expected to take an event and return one or more objmaps.
# it may also modify the event, for instance by add missing information
# such as a summary.

MAPPERS = {
    'openstack|compute.instance.create.start':     (instance_id, instance_create),
    'openstack|compute.instance.create.end':       (instance_id, instance_update),
    'openstack|compute.instance.create.error':     (instance_id, instance_update),
    'openstack|compute.instance.update':           (instance_id, instance_update_status),
    'openstack|compute.instance.delete.start':     (instance_id, None),
    'openstack|compute.instance.delete.end':       (instance_id, instance_delete),

    'openstack|compute.instance.create_ip.start':  (instance_id, None),
    'openstack|compute.instance.create_ip.end':    (instance_id, None),
    'openstack|compute.instance.delete_ip.start':  (instance_id, None),
    'openstack|compute.instance.delete_ip.end':    (instance_id, None),

    'openstack|compute.instance.exists':              (instance_id, None),
    'openstack|compute.instance.exists.verified.old': (instance_id, None),

    # Note: I do not currently have good test data for what a real
    # live migration looks like.  I am assuming that the new host will be
    # carried in the last event, and only processing that one.
    'openstack|compute.instance.live_migration.pre.start': (instance_id, None),
    'openstack|compute.instance.live_migration.pre.end': (instance_id, None),
    'openstack|compute.instance.live_migration.post.dest.start': (instance_id, None),
    'openstack|compute.instance.live_migration.post.dest.end':  (instance_id, None),
    'openstack|compute.instance.live_migration._post.start':  (instance_id, None),
    'openstack|compute.instance.live_migration._post.end': (instance_id, instance_update),

    'openstack|compute.instance.power_off.start':  (instance_id, instance_powering_off),
    'openstack|compute.instance.power_off.end':    (instance_id, instance_powered_off),
    'openstack|compute.instance.power_on.start':   (instance_id, instance_powering_on),
    'openstack|compute.instance.power_on.end':     (instance_id, instance_powered_on),
    'openstack|compute.instance.reboot.start':     (instance_id, instance_rebooting),
    'openstack|compute.instance.reboot.end':       (instance_id, instance_rebooted),
    'openstack|compute.instance.shutdown.start':   (instance_id, instance_shutting_down),
    'openstack|compute.instance.shutdown.end':     (instance_id, instance_shut_down),
    'openstack|compute.instance.rebuild.start':    (instance_id, instance_rebuilding),
    'openstack|compute.instance.rebuild.end':      (instance_id, instance_rebuilt),

    'openstack|compute.instance.rescue.start':     (instance_id, None),
    'openstack|compute.instance.rescue.end':       (instance_id, instance_rescue),
    'openstack|compute.instance.unrescue.start':   (instance_id, None),
    'openstack|compute.instance.unrescue.end':     (instance_id, instance_unrescue),

    'openstack|compute.instance.finish_resize.start':  (instance_id, None),
    'openstack|compute.instance.finish_resize.end':    (instance_id, instance_update),
    'openstack|compute.instance.resize.start':         (instance_id, None),
    'openstack|compute.instance.resize.confirm.start': (instance_id, None),
    'openstack|compute.instance.resize.confirm.end':   (instance_id, None),
    'openstack|compute.instance.resize.prep.end':      (instance_id, None),
    'openstack|compute.instance.resize.prep.start':    (instance_id, None),
    'openstack|compute.instance.resize.revert.end':    (instance_id, instance_update),
    'openstack|compute.instance.resize.revert.start':  (instance_id, None),
    'openstack|compute.instance.resize.end':           (instance_id, instance_update),

    'openstack|compute.instance.snapshot.end':    (instance_id, None),
    'openstack|compute.instance.snapshot.start':  (instance_id, None),

    'openstack|compute.instance.suspend':         (instance_id, instance_suspended),
    'openstack|compute.instance.resume':          (instance_id, instance_resumed),

    'openstack|compute.instance.volume.attach':   (instance_id, None),
    'openstack|compute.instance.volume.detach':   (instance_id, None),

    # -------------------------------------------------------------------------
    # DHCP Agent
    # -------------------------------------------------------------------------
    'openstack|dhcp_agent.network.add':       (None, None),
    'openstack|dhcp_agent.network.remove':    (None, None),

    # -------------------------------------------------------------------------
    #  Firewalls --------------------------------------------------------------
    # -------------------------------------------------------------------------
    # Firewall
    'openstack|firewall.create.start':        (None, None),
    'openstack|firewall.create.end':          (None, None),
    'openstack|firewall.update.start':        (None, None),
    'openstack|firewall.update.end':          (None, None),
    'openstack|firewall.delete.start':        (None, None),
    'openstack|firewall.delete.end':          (None, None),

    # firewall_policy
    'openstack|firewall_policy.create.start': (None, None),
    'openstack|firewall_policy.create.end':   (None, None),
    'openstack|firewall_policy.update.start': (None, None),
    'openstack|firewall_policy.update.end':   (None, None),
    'openstack|firewall_policy.delete.start': (None, None),
    'openstack|firewall_policy.delete.end':   (None, None),

    # firewall_rule
    'openstack|firewall_rule.create.start':   (None, None),
    'openstack|firewall_rule.create.end':     (None, None),
    'openstack|firewall_rule.update.start':   (None, None),
    'openstack|firewall_rule.update.end':     (None, None),
    'openstack|firewall_rule.delete.start':   (None, None),
    'openstack|firewall_rule.delete.end':     (None, None),

    # -------------------------------------------------------------------------
    #  Floating IP's
    # -------------------------------------------------------------------------
    'openstack|floatingip.create.start':      (id, floatingip_create_start),
    'openstack|floatingip.create.end':        (id, floatingip_create_end),
    'openstack|floatingip.update.start':      (id, floatingip_update_start),
    'openstack|floatingip.update.end':        (id, floatingip_update_end),
    'openstack|floatingip.delete.start':      (id, floatingip_delete_start),
    'openstack|floatingip.delete.end':        (id, floatingip_delete_end),

    # -------------------------------------------------------------------------
    #  Network
    # -------------------------------------------------------------------------
    'openstack|network.create.start':         (id, network_create_start),
    'openstack|network.create.end':           (id, network_create_end),
    'openstack|network.update.start':         (id, network_update_start),
    'openstack|network.update.end':           (id, network_update_end),
    'openstack|network.delete.start':         (id, network_delete_start),
    'openstack|network.delete.end':           (id, network_delete_end),

    # -------------------------------------------------------------------------
    #  Port
    # -------------------------------------------------------------------------
    'openstack|port.create.start':            (id, port_create_start),
    'openstack|port.create.end':              (id, port_create_end),
    'openstack|port.update.start':            (id, port_update_start),
    'openstack|port.update.end':              (id, port_update_end),
    'openstack|port.delete.start':            (id, port_delete_start),
    'openstack|port.delete.end':              (id, port_delete_end),

    # -------------------------------------------------------------------------
    #  Routers
    # -------------------------------------------------------------------------
    'openstack|router.create.start':            (id, router_create_start),
    'openstack|router.create.end':              (id, router_create_end),
    'openstack|router.update.start':            (id, router_update_start),
    'openstack|router.update.end':              (id, router_update_end),
    'openstack|router.delete.start':            (id, router_delete_start),
    'openstack|router.delete.end':              (id, router_delete_end),

    'openstack|router.interface.create':        (None, None),
    'openstack|router.interface.update':        (None, None),
    'openstack|router.interface.delete':        (None, None),

    # -------------------------------------------------------------------------
    #  security_group
    # -------------------------------------------------------------------------
    'openstack|security_group.create.start':    (id, security_group_create_start),
    'openstack|security_group.create.end':      (id, security_group_create_end),
    'openstack|security_group.update.start':    (id, security_group_update_start),
    'openstack|security_group.update.end':      (id, security_group_update_end),
    'openstack|security_group.delete.start':    (id, security_group_delete_start),
    'openstack|security_group.delete.end':      (id, security_group_delete_end),

    # -------------------------------------------------------------------------
    #  security_group_rule
    # -------------------------------------------------------------------------
    'openstack|security_group_rule.create.start': (None, None),
    'openstack|security_group_rule.create.end':   (None, None),
    'openstack|security_group_rule.update.start': (None, None),
    'openstack|security_group_rule.update.end':   (None, None),
    'openstack|security_group_rule.delete.start': (None, None),
    'openstack|security_group_rule.delete.end':   (None, None),

}


def process(evt, device, dmd, txnCommit):
    (idfunc, mapper) = MAPPERS.get(evt.eventClassKey, (None, None))

    if idfunc:
        evt.component = idfunc(evt)

    if mapper:
        datamaps = mapper(device, dmd, evt)
        if datamaps:
            adm = ApplyDataMap()
            for datamap in datamaps:
                # LOG.debug("Applying %s" % datamap)
                adm._applyDataMap(device, datamap)

        return len(datamaps)
    else:
        return 0
