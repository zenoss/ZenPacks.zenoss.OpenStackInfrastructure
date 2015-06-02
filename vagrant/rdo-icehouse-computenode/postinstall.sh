#!/bin/sh

# This script should be run after packstack completes installing openstack on this node.
# To invoke packstack on the primary (rdo-icehouse) controller node to add this
# new compute node, see https://openstack.redhat.com/Adding_a_compute_node

# Fix libvirt hypervisor so it can run nested under virtualbox.
openstack-config --set /etc/nova/nova.conf libvirt virt_type qemu

# Enable compute.instance.update events
openstack-config --set /etc/nova/nova.conf DEFAULT notify_on_state_change vm_state


# bounce most of nova/neutron to pick up those config file changes
for e in openstack-nova-api openstack-nova-compute openstack-nova-conductor openstack-nova-scheduler; do service $e restart; done
for e in neutron-dhcp-agent neutron-l3-agent neutron-metadata-agent neutron-openvswitch-agent neutron-server; do service $e restart; done

/usr/lib/rabbitmq/bin/rabbitmq-plugins enable rabbitmq_management
service rabbitmq-server restart
#    (http://<host>:15672/ - log in as guest/guest)

# When using openvpn, it can picks up a bogus domain name that keeps horizon's
# vhost form working.
perl -p -i -e 's/\.openvpn//g' /etc/httpd/conf.d/15-horizon_vhost.conf /etc/openstack-dashboard/local_settings
service httpd  restart

# Install zenoss plugin (provides dispatcher_zenoss)
sudo pip -q install --force-reinstall https://github.com/zenoss/ceilometer_zenoss/archive/master.zip

# Configure ceilometer
cp /usr/lib/python2.6/site-packages/ceilometer_zenoss/event_definitions.yaml /etc/ceilometer/
perl -p -i -e 's/#dispatcher=database/dispatcher=database\ndispatcher=zenoss/g' /etc/ceilometer/ceilometer.conf
openstack-config --set /etc/ceilometer/ceilometer.conf notification store_events True
openstack-config --set /etc/ceilometer/ceilometer.conf DEFAULT verbose False
openstack-config --set /etc/ceilometer/ceilometer.conf DEFAULT debug True

# These will need to be tweaked for your specific setup.
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss zenoss_device ostack
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_hostname 192.168.2.2
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_port 5672
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_userid zenoss
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_password zenoss
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_virtual_host /zenoss

# bounce ceilometer.
for e in openstack-ceilometer-alarm-evaluator openstack-ceilometer-alarm-notifier openstack-ceilometer-api openstack-ceilometer-central openstack-ceilometer-collector openstack-ceilometer-compute openstack-ceilometer-notification; do service $e restart; done
