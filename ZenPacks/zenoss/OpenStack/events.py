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
        'flavor_name':  ['set_flavor_name'],
        'tenant_id':    ['set_tenant'],
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


def instance_update_status(device, dmd, evt):
    if not evt.summary:
        evt.summary = "Instance %s status changed to %s" % (
            evt.trait_display_name, evt.trait_state)

    objmap = instance_objmap(evt)
    _apply_traits(evt, 'instance', objmap)

    return [objmap]


# For each eventClassKey, associate it with the appropriate mapper function.
# A mapper function is expected to take an event and return one or more objmaps.
# it may also modify the event, for instance by add missing information
# such as a summary.


MAPPERS = {
    'compute.instance.create.start':  instance_create,
    'compute.instance.create.end':    instance_update,
    'compute.instance.create.error':  instance_update,
    'compute.instance.power_off.end': instance_update_status
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
            adm._applyDataMap(device, datamap)

    return len(datamaps)