#!/bin/sh -x

yum install -y emacs wget telnet
sudo yum install -y qemu-kvm sys libguestfs-tools e2fsprogs

sudo yum install -y centos-release-openstack-queens
sudo yum update -y
sudo yum install -y openstack-packstack openstack-utils

sudo systemctl disable firewalld
sudo systemctl stop firewalld
sudo systemctl disable NetworkManager
sudo systemctl stop NetworkManager
sudo systemctl enable network
sudo systemctl start network

#sudo packstack --allinone
sudo packstack --allinone --os-ceilometer-install=y 
#sudo packstack --allinone --os-ceilometer-install=y --os-controller-host=192.168.2.15 --os-compute-hosts=192.168.2.15 --os-network-hosts=192.168.2.15 --vcenter-host=192.168.2.15 --amqp-host=192.168.2.15 --mariadb-host=192.168.2.15 --mongodb-host=192.168.2.15 --novanetwork-pubif=eth1 --novanetwork-fixed-range=192.168.32.0/22 --novanetwork-floating-range=10.3.4.0/22 --os-neutron-ml2-type-drivers=local --os-neutron-ml2-tenant-network-types=local --os-neutron-ml2-mechanism-drivers=openvswitch --use-epel=y

# Fix libvirt hypervisor so it can run nested under virtualbox.
echo "options kvm-intel nested=y" | sudo tee /etc/modprobe.d/kvm-intel.conf
openstack-config --set /etc/nova/nova.conf libvirt virt_type qemu

# Enable compute.instance.update events
openstack-config --set /etc/nova/nova.conf DEFAULT notify_on_state_change vm_state


# bounce most of nova/neutron to pick up those config file changes
for e in openstack-nova-api openstack-nova-compute openstack-nova-conductor openstack-nova-scheduler; do /bin/systemctl restart $e; done
for e in neutron-dhcp-agent neutron-l3-agent neutron-metadata-agent neutron-openvswitch-agent neutron-server; do /bin/systemctl restart $e; done

/usr/lib/rabbitmq/bin/rabbitmq-plugins enable rabbitmq_management
/bin/systemctl restart rabbitmq-server
#    (http://<host>:15672/ - log in as guest/guest)

# When using openvpn, it can picks up a bogus domain name that keeps horizon's
# vhost form working.
perl -p -i -e 's/\.openvpn//g' /etc/httpd/conf.d/15-horizon_vhost.conf /etc/openstack-dashboard/local_settings
/bin/systemctl restart httpd

# Install zenoss plugin (provides dispatcher_zenoss)
sudo yum install -y python-pip
sudo pip -q install --force-reinstall https://github.com/zenoss/ceilometer_zenoss/archive/master.zip

# Configure ceilometer
sudo cp /usr/lib/python2.7/site-packages/ceilometer_zenoss/event_definitions.yaml /etc/ceilometer/
openstack-config --set /etc/ceilometer/ceilometer.conf notification store_events True
openstack-config --set /etc/ceilometer/ceilometer.conf DEFAULT verbose False
openstack-config --set /etc/ceilometer/ceilometer.conf DEFAULT debug True

perl -p -i -e 's|- gnocchi://|- http://192.168.2.2:8242/ceilometer/v1/samples/rdo-queens|g' /etc/ceilometer/pipeline.yaml
perl -p -i -e 's|- gnocchi://|- http://192.168.2.2:8242/ceilometer/v1/events/rdo-queens|g' /etc/ceilometer/event_pipeline.yaml

# bounce ceilometer.
systemctl restart openstack-ceilometer-central openstack-ceilometer-notification

# Fix keystone endpoints to use the externally accessible IP:
. /root/keystonerc_admin
openstack endpoint list -f value -c ID -c URL | perl -ne 'chomp; ($id, $url) = split / /; $url =~ s/10\.0\.2\.15/192\.168\.2\.15/g; print "openstack endpoint set --url \"$url\" $id\n";' | sh -x


# Create a zenoss user so that zenoss can monitor this host as well.
adduser zenoss -p '$6$GBeC9/Vf$0/6klsM6XThSI/nXvZTwsn1ESPjKjSbmlXj1Okh1i2CVTCknekldztlvhAF5ki85a94FejZ1cliKd30Met0BT/'

# Increase MaxSessions for sshd:
perl -p -i -e 's/#MaxSessions 10/MaxSessions 100/g' /etc/ssh/sshd_config
/bin/systemctl restart sshd

# set up the vagrant user with the right openstack environment so you can just
# log in and run the openstack commandline tools.
cp /root/keystonerc_admin /home/vagrant/keystonerc_admin
chown vagrant /home/vagrant/keystonerc_admin
echo ". /home/vagrant/keystonerc_admin" >> /home/vagrant/.bashrc
