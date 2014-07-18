#!/bin/sh -x

yum update -y
yum install emacs mongodb wget
yum install -y http://rdo.fedorapeople.org/rdo-release.rpm
yum install -y openstack-packstack
packstack --allinone --os-ceilometer-install=y

cp /vagrant/event_definitions.yaml /etc/ceilometer/
cd /etc/neutron/plugins/ml2/
patch -p0 < /vagrant/ml2_conf.ini.patch

cd /etc/nova
patch -p0 < /vagrant/nova.conf.patch

# bounce most of nova/neutron to pick up those config file changes
for e in openstack-nova-api openstack-nova-compute openstack-nova-conductor openstack-nova-scheduler; do service $e restart; done
for e in neutron-dhcp-agent neutron-l3-agent neutron-metadata-agent neutron-openvswitch-agent neutron-server; do service $e restart; done

/usr/lib/rabbitmq/bin/rabbitmq-plugins enable rabbitmq_management
service rabbitmq-server restart
#    (http://<host>:15672/ - log in as guest/guest)

