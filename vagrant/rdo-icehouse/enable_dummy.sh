#!/bin/sh

# NOTE:
#
# This script must be run as root, with administrative openstack cred env vars.
#
# Converts the normal dev environment to a fake driver environment, where VMs
# appear to be created, but do not actually get fired up.
#
# This is meant to be used in combination with the static_objmaps.json file,
# which fills in some missing details (such as software components) on these
# dummy hosts.

# compute driver
openstack-config --set /etc/nova/nova.conf DEFAULT compute_driver fake.FakeDriver

# scheduler driver (place instances on random hosts)
openstack-config --set /etc/nova/nova.conf DEFAULT scheduler_driver nova.scheduler.chance.ChanceScheduler

# disable RAM capacity checking (so that nova-scheduler will dramatically over schedule this host with VMs- it won't matter, since
# VMs won't be real.
openstack-config --set /etc/nova/nova.conf DEFAULT scheduler_default_filters RetryFilter,AvailabilityZoneFilter,ComputeFilter,ComputeCapabilitiesFilter,ImagePropertiesFilter

# Disable the demo user's quotas:
# (as admin user)

ADMIN_TENANT_ID=`keystone tenant-list | grep admin | awk '{print $2}'`
DEMO_TENANT_ID=`keystone tenant-list | grep demo | awk '{print $2}'`
nova quota-update $ADMIN_TENANT_ID --instances -1 --cores -1 --ram -1 --floating-ips -1 --fixed-ips -1
nova quota-update $DEMO_TENANT_ID --instances -1 --cores -1 --ram -1 --floating-ips -1 --fixed-ips -1
neutron quota-update --tenant-id $ADMIN_TENANT_ID --floatingip -1 --network -1 --port -1 --router -1
neutron quota-update --tenant-id $DEMO_TENANT_ID --floatingip -1 --network -1 --port -1 --router -1

# Add more subnets to the neutron public network, so we can create more than 12 instances without running out.
PUBLIC_NET=`neutron net-list | grep public | awk '{print $2}'`
neutron subnet-create $PUBLIC_NET 172.25.0.0/16

# Modify the list of hosts
perl -p -i -e "s/^_FAKE_NODES =.*/_FAKE_NODES = [CONF.host, \'node2\', \'node3\', \'node4\', \'node5\', \'node6\', \'node7\']/g" /usr/lib/python2.6/site-packages/nova/virt/fake.py

# Bounce services:
/etc/init.d/openstack-nova-api restart
/etc/init.d/openstack-nova-compute restart
/etc/init.d/openstack-nova-conductor restart
/etc/init.d/openstack-nova-scheduler restart

# Confirm that all 8 "hosts" are present
nova hypervisor-list
