##############################################################################
#
# Copyright (C) Zenoss, Inc. 2019, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


# This list of event types and required traits for each one was built by
# manually inspecting the event processing code in events.py

# For reference, traits are specified as a list of used trait names
#
# When an item in the list is a list itself, it means an "or" condition,
# where we need one of the possible ones listed.

instance_id_traits = [['instance_id', 'resource_id']]
floatingip_id_traits = [['id', 'resource_id']]
network_id_traits = [['id', 'resource_id']]
port_id_traits = [['id', 'resource_id']]
router_id_traits = [['id', 'resource_id']]
subnet_id_traits = [['id', 'resource_id']]
tenant_id_traits = [['tenant_id']]
volume_id_traits = [['volume_id', 'resource_id']]
volsnapshot_id_traits = [['snapshot_id', 'resource_id']]
instance_name_traits = ["display_name"] + instance_id_traits
floatingip_name_traits = floatingip_id_traits
network_name_traits = ["name"] + network_id_traits
port_name_traits = port_id_traits
router_name_traits = router_id_traits
subnet_name_traits = subnet_id_traits
volume_name_traits = volume_id_traits
volsnapshot_name_traits = volsnapshot_id_traits

instance_traits = instance_name_traits + [
    'instance_id', 'state', ['flavor_name', 'instance_type'],
    ['host_name', 'host'], 'image_name', 'tenant_id', 'fixed_ips']

instance_create_traits = instance_update_traits = instance_update_status_traits = \
    instance_powered_on_traits = \
    instance_powered_off_traits = instance_shutting_down_traits = \
    instance_shut_down_traits = instance_rebooting_traits = \
    instance_rebooted_traits = instance_rebuilding_traits = \
    instance_rebuilt_traits = instance_suspended_traits = \
    instance_resumed_traits = instance_rescue_traits = instance_unrescue_traits = instance_traits

instance_delete_traits = []

dns_info_traits = ['dns_nameservers']
cinder_traits = ['status', 'display_name', 'availability_zone', 'created_at', ['volume_id', 'resource_id'], 'host', 'type', 'size']
cinder_traits_snapshot = ['status', 'display_name', 'availability_zone', 'created_at', ['volume_id', 'resource_id'], 'size']

floatingip_traits = ['fixed_ip_address', 'floating_ip_address', ['id', 'resource_id'], 'status']
network_traits = ['admin_state_up', ['id', 'resource_id'], 'name', 'provider_network_type', 'router_external', 'status']
port_traits = ['admin_state_up', 'binding_vif_type', 'device_owner', ['id', 'resource_id'], 'mac_address', 'name', 'status']
router_traits = ['admin_state_up', ['id', 'resource_id'], 'routes', 'status', 'name']
subnet_traits = ['cidr', 'gateway_ip', ['id', 'resource_id'], 'name', 'network_id']
router_gateway_info_traits = ['external_gateway_info']

floatingip_update_start_traits = floatingip_name_traits
floatingip_update_traits = floatingip_id_traits + floatingip_name_traits + floatingip_traits + ['floating_network_id', 'router_id', 'port_id']
floatingip_delete_end_traits = floatingip_id_traits + floatingip_name_traits

network_update_traits = network_id_traits + network_name_traits + network_traits
network_delete_end_traits = network_id_traits + network_name_traits

port_update_traits = port_id_traits + port_name_traits + port_traits + ['network_id', 'device_id', 'device_owner', 'fixed_ips']
port_delete_end_traits = port_id_traits + port_name_traits

router_update_traits = router_id_traits + router_name_traits + router_traits + router_gateway_info_traits
router_delete_end_traits = router_id_traits + router_name_traits

subnet_update_traits = subnet_id_traits + subnet_name_traits + subnet_traits + dns_info_traits + ['network_id']
subnet_delete_end_traits = subnet_id_traits + subnet_name_traits

volume_update_traits = volume_id_traits + volume_name_traits + cinder_traits + [['tenant_id', 'project_id'], 'instance_id', 'type']
volume_delete_end_traits = volume_id_traits + volume_name_traits

volsnapshot_update_traits = volsnapshot_id_traits + volsnapshot_name_traits + volume_name_traits + cinder_traits_snapshot + [['tenant_id', 'project_id'], 'volume_id']
volsnapshot_delete_end_traits = volsnapshot_id_traits + volsnapshot_name_traits + volume_name_traits

# These are the only events that our event transform does anything with.
zenoss_required_events = {
    'compute.instance.create.start': instance_id_traits + instance_name_traits + instance_create_traits,
    'compute.instance.create.end': instance_id_traits + instance_name_traits + instance_update_traits,
    'compute.instance.create.error': instance_id_traits + instance_name_traits + instance_update_traits,
    'compute.instance.update': instance_id_traits + instance_name_traits + instance_update_status_traits,
    'compute.instance.delete.end': instance_id_traits + instance_name_traits + instance_delete_traits,
    'compute.instance.live_migration._post.end': instance_id_traits + instance_name_traits + instance_update_traits,
    'compute.instance.power_on.end': instance_id_traits + instance_name_traits + instance_powered_on_traits,
    'compute.instance.power_off.end': instance_id_traits + instance_name_traits + instance_powered_off_traits,
    'compute.instance.reboot.start': instance_id_traits + instance_name_traits + instance_rebooting_traits,
    'compute.instance.reboot.end': instance_id_traits + instance_name_traits + instance_rebooted_traits,
    'compute.instance.shutdown.start': instance_id_traits + instance_name_traits + instance_shutting_down_traits,
    'compute.instance.shutdown.end': instance_id_traits + instance_name_traits + instance_shut_down_traits,
    'compute.instance.rebuild.start': instance_id_traits + instance_name_traits + instance_rebuilding_traits,
    'compute.instance.rebuild.end': instance_id_traits + instance_name_traits + instance_rebuilt_traits,
    'compute.instance.rescue.end': instance_id_traits + instance_name_traits + instance_rescue_traits,
    'compute.instance.unrescue.end': instance_id_traits + instance_name_traits + instance_unrescue_traits,
    'compute.instance.finish_resize.end': instance_id_traits + instance_name_traits + instance_update_traits,
    'compute.instance.resize.revert.end': instance_id_traits + instance_name_traits + instance_update_traits,
    'compute.instance.resize.end': instance_id_traits + instance_name_traits + instance_update_traits,
    'compute.instance.suspend': instance_id_traits + instance_name_traits + instance_suspended_traits,
    'compute.instance.resume': instance_id_traits + instance_name_traits + instance_resumed_traits,
    'floatingip.create.end': floatingip_id_traits + floatingip_name_traits + floatingip_update_traits,
    'floatingip.update.start': floatingip_id_traits + floatingip_name_traits + floatingip_update_traits,
    'floatingip.update.end': floatingip_id_traits + floatingip_name_traits + floatingip_update_traits,
    'floatingip.delete.end': floatingip_id_traits + floatingip_name_traits + floatingip_delete_end_traits,
    'network.create.end': network_id_traits + network_name_traits + network_update_traits,
    'network.update.end': network_id_traits + network_name_traits + network_update_traits,
    'network.delete.end': network_id_traits + network_name_traits + network_delete_end_traits,
    'port.create.end': port_id_traits + port_name_traits + port_update_traits,
    'port.update.end': port_id_traits + port_name_traits + port_update_traits,
    'port.delete.end': port_id_traits + port_name_traits + port_delete_end_traits,
    'router.create.end': router_id_traits + router_name_traits + router_update_traits,
    'router.update.end': router_id_traits + router_name_traits + router_update_traits,
    'router.delete.end': router_id_traits + router_name_traits + router_delete_end_traits,
    'subnet.create.end': subnet_id_traits + subnet_name_traits + subnet_update_traits,
    'subnet.update.end': subnet_id_traits + subnet_name_traits + subnet_update_traits,
    'subnet.delete.end': subnet_id_traits + subnet_name_traits + subnet_delete_end_traits,
    'volume.create.end': volume_id_traits + volume_name_traits + volume_update_traits,
    'volume.update.end': volume_id_traits + volume_name_traits + volume_update_traits,
    'volume.delete.end': volume_id_traits + volume_name_traits + volume_delete_end_traits,
    'volume.attach.end': volume_id_traits + volume_name_traits + volume_update_traits,
    'volume.detach.end': volume_id_traits + volume_name_traits + volume_update_traits,
    'snapshot.create.end': volsnapshot_id_traits + volsnapshot_name_traits + volsnapshot_update_traits,
    'snapshot.delete.end': volsnapshot_id_traits + volsnapshot_name_traits + volsnapshot_delete_end_traits
}

# strip out duplicates
for event_type, traits in zenoss_required_events.iteritems():
    unique_traits = []
    for trait in traits:
        if trait not in unique_traits:
            unique_traits.append(trait)
    zenoss_required_events[event_type] = unique_traits

