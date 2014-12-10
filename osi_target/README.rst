===================================================
Setup for OpenStackInfrastructure Reference Network
===================================================

This utility sets up the OpenStackInfrastructure Zenpack's reference network
that will be used to test against.

Overview and Definitions
==========================

* The main objective is to build the **Reference Network** onto a Target.
* The **Reference Network** is defined in the reference_network.png image
* The deployment **Host** system will perform all configuration.
* The **Target** system will be configured with Openstack/Packstack/Neutron.

Requirements
===============

System Requirements
---------------------

* Your deployment Host is Centos 7 (others *may* work with minor changes).
* Your Target for Packstack is *already* installed and must be Centos 7 
* Target has a user "zenoss" with has sudo access, and a valid password
* Target must allow for static ip address assignment
* You have ssh'd into the Target already and accpeted its host-key in your:
  **~/.ssh/known_hosts**

Network Requirements
----------------------

* Target system must be on an isolated subnet with access to the internet. 
* Host system has access to the Host subnet and the internet. 
* You may need to be on an isolated network segement to access the internal 
  Packstack/Openstack VMs.

Setup
=======

* In neutron.reference.net/group_vars/all:

  - Take note of the keystone settings. These should not require changes.

* Copy the prototype variables set from
  neutron.reference.net/host_vars/prototype.com to the ip-address or FQDN of
  your Target system::

     cd neutron.reference.net/host_vars
     cp prototype.com myhost.zenoss.loc

* Edit the variables in neutron.reference.net/host_vars/<ip-address or FQDN>:
   
   - Make sure all the ip addresses are correct for the defined servers.
   - Make sure all other parameters are correct for your system

* In neutron.reference.net/inventory:

  - Set the value of mpx.zenoss.loc to your Target fqdn/address: myhost.zenoss.loc

* To force a rebuild, remove the file /root/keystonerc_admin on the Target

Makefile
=============

Overview
------------

The top level Makefile will perform the following tasks:

* Setup up the host system by installing ansible and needed packages.
* On the Target:

  - Install all required packages
  - Setup required users
  - Run Packstack Installer
  - Setup all Neutron networking per **Reference Network**

Build Targets
--------------

There are two essential build targets:

* make: this target will build all essential features
* packstack: This target will only build the Packstack setup
* neutron: This target builds only the network part of neutron

The following make targets are for testing:

* vars: This builds a diagnostic set of variables for debugging
* test: This builds a small set of non-invasive objects for testing.
