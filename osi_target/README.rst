===================================================
Setup for OpenStackInfrastructure Reference Network
===================================================

This utility sets up the OpenStackInfrastructure Zenpack's reference network
that will be used to test against.

Requirements
-------------

* Your deployment host is Centos 7
* Your target for Packstack must be Centos 7
* The target has a user "zenoss" with has sudo access, and a valid password
* The target must allow for static ip address assignment
* You may need to be on an isolated network segement get get access to the Packstack VM's
* You have ssh'd into the target already and accpeted its host-key in your:
   **~/.ssh/known_hosts**


Setup
-------

* In neutron.reference.net/group_vars/all:

  - Take note of the keystone settings

* Copy the prototype variables set from
  neutron.reference.net/host_vars/prototype.com to the ip-address or FQDN of
  your target system::

     cd neutron.reference.net/host_vars
     cp prototype.com myhost.zenoss.loc

* Edit the variables in neutron.reference.net/host_vars/<ip-address or FQDN>:
   
   - Make sure all the ip addresses are correct for the defined servers.
   - Make sure all other parameters are correct for your system

* In neutron.reference.net/inventory:

  - Set the value of mpx.zenoss.loc to your target fqdn/address: myhost.zenoss.loc

* To force a rebuild, remove the file /root/keystonerc_admin on the target
