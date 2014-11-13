#! /bin/bash 

echo "Ammend and Update Yum Repos"
yum update -y
yum install -y emacs wget telnet
yum install -y https://repos.fedorapeople.org/repos/openstack/openstack-icehouse/rdo-release-icehouse-4.noarch.rpm
yum install -y openstack-packstack

echo "Run the Packstack Installer"
packstack --allinone --os-ceilometer-install=y \
--os-controller-host=${ip_address} \
--os-compute-hosts=${ip_address} \
--os-network-hosts=${ip_address} \
--vcenter-host=${ip_address} \
--amqp-host=${ip_address} \
--mariadb-host=${ip_address} \
--mongodb-host=${ip_address} \
--novanetwork-pubif=${novanetwork_pubif} \
--novanetwork-fixed-range=${novanetwork_fixed_range} \
--novanetwork-floating-range=${novanetwork_floating_range} \
--os-neutron-ml2-type-drivers=local \
--os-neutron-ml2-tenant-network-types=local \
--os-neutron-ml2-mechanism-drivers=openvswitch \
--use-epel=y

# Fix libvirt hypervisor so it can run nested under virtualbox.
echo "Fix libvirt hypervisor: set to Qemu virt_type"
openstack-config --set /etc/nova/nova.conf libvirt virt_type qemu

echo "Enable compute.instance.update events"
# Enable compute.instance.update events
openstack-config --set /etc/nova/nova.conf DEFAULT notify_on_state_change vm_state


# Define nova services to bounce
nova_services=(
openstack-nova-api
openstack-nova-compute
openstack-nova-conductor
openstack-nova-scheduler
)

# Define Neutron services to bounce
neutron_services=(
neutron-dhcp-agent
neutron-l3-agent
neutron-metadata-agent
neutron-openvswitch-agent
neutron-server
)

# Now: bounce most of nova/neutron to pick up those config file changes
echo "Bouncing Nova Services"
for svc in ${nova_services[@]} ; do
   service "$svc" restart; 
done

echo "Bouncing Neutron Services"
for svc in ${neutron_services[@]} ; do
   service "$svc" restart; 
done

/usr/lib/rabbitmq/bin/rabbitmq-plugins enable rabbitmq_management
service rabbitmq-server restart
#    (http://<host>:15672/ - log in as guest/guest)

# When using openvpn, it can picks up a bogus domain name that keeps horizon's
# vhost form working.
perl -p -i -e 's/\.openvpn//g' \
   /etc/httpd/conf.d/15-horizon_vhost.conf \
   /etc/openstack-dashboard/local_settings
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
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_hostname ${amqp_hostname}
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_port 5672
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_userid ${amqp_userid}
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_password ${amqp_password}
openstack-config --set /etc/ceilometer/ceilometer.conf dispatcher_zenoss amqp_virtual_host /zenoss

# Define Ceilometer Services
ceilometer_svcs=(
openstack-ceilometer-alarm-evaluator
openstack-ceilometer-alarm-notifier
openstack-ceilometer-api
openstack-ceilometer-central
openstack-ceilometer-collector
openstack-ceilometer-compute
openstack-ceilometer-notification
)

# bounce ceilometer.
for e in openstack-ceilometer-alarm-evaluator openstack-ceilometer-alarm-notifier openstack-ceilometer-api openstack-ceilometer-central openstack-ceilometer-collector openstack-ceilometer-compute openstack-ceilometer-notification; do service $e restart; done

# Create a zenoss user so that zenoss can monitor this host as well.
adduser zenoss -p '$6$GBeC9/Vf$0/6klsM6XThSI/nXvZTwsn1ESPjKjSbmlXj1Okh1i2CVTCknekldztlvhAF5ki85a94FejZ1cliKd30Met0BT/'

# Increase MaxSessions for sshd:
perl -p -i -e 's/#MaxSessions 10/MaxSessions 100/g' /etc/ssh/sshd_config
/etc/init.d/sshd restart

# set up the zenoss user with the right openstack environment so you can just
# log in and run the openstack commandline tools.
cp /root/keystonerc_admin /home/zenoss/keystonerc_admin
chown zenoss /home/zenoss/keystonerc_admin
echo ". /home/zenoss/keystonerc_admin" >> /home/zenoss/.bashrc

