#!/bin/sh -x

yum update -y
yum install emacs mongodb wget telnet
yum install -y http://rdo.fedorapeople.org/rdo-release.rpm
yum install -y openstack-packstack
packstack --allinone --os-ceilometer-install=y --os-controller-host=192.168.2.11 --os-compute-hosts=192.168.2.11 --os-network-hosts=192.168.2.11 --vcenter-host=192.168.2.11 --amqp-host=192.168.2.11 --mysql-host=192.168.2.11 --mongodb-host=192.168.2.11 --novanetwork-pubif=eth1 --novanetwork-fixed-range=192.168.32.0/22 --novanetwork-floating-range=10.3.4.0/22 --os-neutron-ml2-type-drivers=local --os-neutron-ml2-tenant-network-types=local --os-neutron-ml2-mechanism-drivers=openvswitch

# Fix libvirt hypervisor so it can run nested under virtualbox.
openstack-config --set /etc/nova/nova.conf libvirt virt_type qemu

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

# Configure ceilometer
cp /vagrant/event_definitions.yaml /etc/ceilometer/
perl -p -i -e 's/#dispatcher=database/dispatcher=database\ndispatcher=zenoss/g' /etc/ceilometer/ceilometer.conf
openstack-config --set /etc/ceilometer/ceilometer.conf notification store_events True

# These will need to be tweaked for your specific setup.
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss zenoss_device packstack1
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_hostname 192.168.2.2
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_port 5672
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_userid zenoss
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_password zenoss
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_virtual_host /zenoss

# Install zenoss plugin (provides dispatcher_zenoss)
easy_install --no-deps /vagrant/ceilometer_zenoss-0.9.0-py2.7.egg

# bounce ceilometer.
for e in openstack-ceilometer-alarm-evaluator openstack-ceilometer-alarm-notifier openstack-ceilometer-api openstack-ceilometer-central openstack-ceilometer-collector openstack-ceilometer-compute openstack-ceilometer-notification; do service $e restart; done

# Create a zenoss user so that zenoss can monitor this host as well.
adduser zenoss -p '$6$GBeC9/Vf$0/6klsM6XThSI/nXvZTwsn1ESPjKjSbmlXj1Okh1i2CVTCknekldztlvhAF5ki85a94FejZ1cliKd30Met0BT/'

# set up the vagrant user with the right openstack environment so you can just
# log in and run the openstack commandline tools.
cp /root/keystonerc_admin /home/vagrant/keystonerc_admin
chown vagrant /home/vagrant/keystonerc_admin
echo ". /home/vagrant/keystonerc_admin" >> /home/vagrant/.bashrc
