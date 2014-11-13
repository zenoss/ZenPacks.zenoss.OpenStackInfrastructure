#!/bin/sh -x

yum update -y
yum install -y emacs wget telnet
yum install -y https://repos.fedorapeople.org/repos/openstack/openstack-icehouse/rdo-release-icehouse-4.noarch.rpm
yum install -y openstack-packstack

# Create a zenoss user so that zenoss can monitor this host as well.
adduser zenoss -p '$6$GBeC9/Vf$0/6klsM6XThSI/nXvZTwsn1ESPjKjSbmlXj1Okh1i2CVTCknekldztlvhAF5ki85a94FejZ1cliKd30Met0BT/'

# Increase MaxSessions for sshd:
perl -p -i -e 's/#MaxSessions 10/MaxSessions 100/g' /etc/ssh/sshd_config
/bin/systemctl restart sshd
