#!/bin/sh

# Undoes the steps in disable_dummy.sh, returning the test environment to a more normal state.

nova quota-update admin --instances 10 --cores 20 --ram 51200 --floating-ips 10 --fixed-ips -1
nova quota-update demo --instances 10 --cores 20 --ram 51200 --floating-ips 10 --fixed-ips -1
openstack-config --set /etc/nova/nova.conf DEFAULT scheduler_default_filters RetryFilter,AvailabilityZoneFilter,RamFilter,ComputeFilter,ComputeCapabilitiesFilter,ImagePropertiesFilter,CoreFilter
openstack-config --set /etc/nova/nova.conf DEFAULT compute_driver nova.virt.libvirt.LibvirtDriver
openstack-config --set /etc/nova/nova.conf DEFAULT scheduler_driver nova.scheduler.filter_scheduler.FilterScheduler
perl -p -i -e "s/^_FAKE_NODES =.*/_FAKE_NODES = None/g" /usr/lib/python2.6/site-packages/nova/virt/fake.py

# Bounce services:
/etc/init.d/openstack-nova-api restart
/etc/init.d/openstack-nova-compute restart
/etc/init.d/openstack-nova-conductor restart
/etc/init.d/openstack-nova-scheduler restart

# Confirm that all 8 "hosts" are no longer present
nova hypervisor-list
