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

# Bounce services:
/bin/systemctl restart openstack-nova-compute
