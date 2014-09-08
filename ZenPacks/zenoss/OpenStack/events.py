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

import logging
LOG = logging.getLogger('zen.OpenStack.events')


# Sets of traits we can expect to get (see event_definitions.yaml on the
# openstack side) and what objmap properties they map to.
TRAITMAPS = {
    'instance': {
        'display_name': ['title', 'hostName'],
        'instance_id':  ['resourceId', 'serverId'],
        'state':        ['serverStatus'],
        'flavor_name':  ['set_flavor_name'],
        'host_name':    ['set_host_name'],
        'image_name':   ['set_image_name'],
        'tenant_id':    ['set_tenant'],
        # Todo: handle fixed_IPs
    },
}


def _apply_traits(evt, traitset, objmap):
    traitmap = TRAITMAPS[traitset]

    for trait in traitmap:
        for prop_name in traitmap[trait]:
            trait_field = 'trait_' + trait
            if hasattr(evt, trait_field):
                value = getattr(evt, trait_field)
                setattr(objmap, prop_name, value)


def instance_objmap(evt):
    return ObjectMap(
        modname='ZenPacks.zenoss.OpenStack.Instance',
        compname='',
        data={
            'id': 'server-{0}'.format(evt.trait_instance_id),
            'relname': 'components'
        },
    )


def instance_create(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s created" % (evt.trait_display_name)

    objmap = instance_objmap(evt)
    _apply_traits(evt, 'instance', objmap)
    return [objmap]


def instance_update(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s updated" % (evt.trait_display_name)

    objmap = instance_objmap(evt)
    _apply_traits(evt, 'instance', objmap)
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
    _apply_traits(evt, 'instance', objmap)
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
    _apply_traits(evt, 'instance', objmap)
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
    _apply_traits(evt, 'instance', objmap)
    return [objmap]


def instance_shutting_down(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s shutting down" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_traits(evt, 'instance', objmap)
    return [objmap]


def instance_shut_down(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s shut down" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_traits(evt, 'instance', objmap)
    return [objmap]


def instance_rebooting(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s rebooting" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_traits(evt, 'instance', objmap)
    return [objmap]


def instance_rebooted(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s rebooted" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_traits(evt, 'instance', objmap)
    return [objmap]


def instance_rebuilding(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s rebuilding" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_traits(evt, 'instance', objmap)
    return [objmap]


def instance_rebuilt(device, dmd, evt):
    if not evt.summary:
        evt.summary = add_statuschange_to_msg(
            evt,
            "Instance %s rebuilt" % (evt.trait_display_name)
        )

    objmap = instance_objmap(evt)
    _apply_traits(evt, 'instance', objmap)
    return [objmap]

def instance_suspended(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s suspended" % (evt.trait_display_name)

    objmap = instance_objmap(evt)
    _apply_traits(evt, 'instance', objmap)
    return [objmap]


def instance_resumed(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s resumed" % (evt.trait_display_name)

    objmap = instance_objmap(evt)
    _apply_traits(evt, 'instance', objmap)
    return [objmap]

def instance_rescue(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s placed in rescue mode" % (evt.trait_display_name)

    objmap = instance_objmap(evt)
    _apply_traits(evt, 'instance', objmap)
    return [objmap]


def instance_unrescue(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s removed from rescue mode" % (evt.trait_display_name)

    objmap = instance_objmap(evt)
    _apply_traits(evt, 'instance', objmap)
    return [objmap]

# For each eventClassKey, associate it with the appropriate mapper function.
# A mapper function is expected to take an event and return one or more objmaps.
# it may also modify the event, for instance by add missing information
# such as a summary.


MAPPERS = {
    'compute.instance.create.start':     instance_create,
    'compute.instance.create.end':       instance_update,
    'compute.instance.create.error':     instance_update,
    'compute.instance.update':           instance_update_status,
    'compute.instance.delete.start':     None,
    'compute.instance.delete.end':       instance_delete,

    'compute.instance.create_ip.start':  None,
    'compute.instance.create_ip.end':    None,
    'compute.instance.delete_ip.start':  None,
    'compute.instance.delete_ip.end':    None,

    'compute.instance.exists':              None,
    'compute.instance.exists.verified.old': None,

    # Note: I do not currently have good test data for what a real
    # live migration looks like.  I am assuming that the new host will be
    # carried in the last event, and only processing that one.
    'compute.instance.live_migration.pre.start': None,
    'compute.instance.live_migration.pre.end': None,
    'compute.instance.live_migration.post.dest.start': None,
    'compute.instance.live_migration.post.dest.end':  None,
    'compute.instance.live_migration._post.start':  None,
    'compute.instance.live_migration._post.end': instance_update,

    'compute.instance.power_off.start':  instance_powering_off,
    'compute.instance.power_off.end':    instance_powered_off,
    'compute.instance.power_on.start':   instance_powering_on,
    'compute.instance.power_on.end':     instance_powered_on,
    'compute.instance.reboot.start':     instance_rebooting,
    'compute.instance.reboot.end':       instance_rebooted,
    'compute.instance.shutdown.start':   instance_shutting_down,
    'compute.instance.shutdown.end':     instance_shut_down,
    'compute.instance.rebuild.start':    instance_rebuilding,
    'compute.instance.rebuild.end':      instance_rebuilt,

    'compute.instance.rescue.start':     None,
    'compute.instance.rescue.end':       instance_rescue,
    'compute.instance.unrescue.start':   None,
    'compute.instance.unrescue.end':     instance_unrescue,

    'compute.instance.finish_resize.start':  None,
    'compute.instance.finish_resize.end':    instance_update,
    'compute.instance.resize.start':         None,
    'compute.instance.resize.confirm.start': None,
    'compute.instance.resize.confirm.end':   None,
    'compute.instance.resize.prep.end':      None,
    'compute.instance.resize.prep.start':    None,
    'compute.instance.resize.revert.end':    instance_update,
    'compute.instance.resize.revert.start':  None,
    'compute.instance.resize.end':           instance_update,

    'compute.instance.snapshot.end':    None,
    'compute.instance.snapshot.start':  None,

    'compute.instance.suspend':         instance_suspended,
    'compute.instance.resume':          instance_resumed,

    'compute.instance.volume.attach':   None,
    'compute.instance.volume.detach':   None
}


def process(evt, device, dmd, txnCommit):
    # most events are not particularly noteworthy, so we can send them
    # straight to history.
    if not evt.eventClassKey.endswith('.error'):
        evt._action = 'history'

    mapper = MAPPERS.get(evt.eventClassKey)
    if not mapper:
        return 0

    datamaps = mapper(device, dmd, evt)
    if datamaps:
        adm = ApplyDataMap()
        for datamap in datamaps:
            # LOG.debug("Applying %s" % datamap)
            adm._applyDataMap(device, datamap)

    return len(datamaps)
