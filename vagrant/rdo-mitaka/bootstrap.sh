#!/bin/sh -x

yum install -y emacs wget telnet

# mitaka is very EOL at this point- some gymnastics are
# required to get yum to find the RPMs.
sudo rpm -ivh https://repos.fedorapeople.org/repos/openstack/EOL/openstack-mitaka/rdo-release-mitaka-7.noarch.rpm
sudo perl -p -i -e 's/mirror.centos.org/buildlogs.centos.org/g' /etc/yum.repos.d/rdo-release.repo
sudo perl -p -i -e 's/gpgcheck=1/gpgcheck=0/g' /etc/yum.repos.d/rdo-release.repo
sudo yum update -y

# Install packstack
sudo yum install -y openstack-packstack openstack-utils 
sudo yum install -y libvirt

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

openstack-config --set /etc/ceilometer/ceilometer.conf DEFAULT meter_dispatchers zenoss
openstack-config --set /etc/ceilometer/ceilometer.conf DEFAULT event_dispatchers zenoss

# These will need to be tweaked for your specific setup.
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss zenoss_device ostack
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_hostname 192.168.2.2
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_port 5672
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_userid zenoss
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_password zenoss
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_virtual_host /zenoss

# bounce ceilometer.
for e in openstack-ceilometer-api openstack-ceilometer-central openstack-ceilometer-collector openstack-ceilometer-compute openstack-ceilometer-notification; do /bin/systemctl restart $e; done

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
