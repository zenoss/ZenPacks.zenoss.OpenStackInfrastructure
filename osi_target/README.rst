===================================================
Setup for OpenStackInfrastructure Reference Network
===================================================

This utility sets up the OpenStackInfrastructure Zenpack's reference network
that will be used to test against.

Introduction
===============
This build environment uses Ansible to build a Openstack network for use
as a target. Openstack is complex and has many dependencies and services.
It is correct to assume that the environment this tool creates is for use
as a test target only. There are many features of Openstack that this tool
does not provide. Do not expect the resulting environment to be free of
numerous defects.

Overview and Definitions
-------------------------

* The main objective is to build the **Reference Network** onto a Target.
* The **Reference Network** is defined in the reference_network.png image
* The deployment **Host** system will perform all configuration.
* The **Target** system will be configured with Openstack/Packstack/Neutron.
* The order of operations are:

  - Setup the (local) host system with ansible
  - Setup the Target system with common_config to set: user, pass, sudo
  - Setup the Target system with Packstack: Adds in zenoss goodies
  - Setup the Target system Neutron network: tenant, net, subnets, routers, vms

Features and Benefits
------------------------

* Uses a simple command to build entire Openstack/Neturon environement
* Builds the entire stack from a bare VM
* Setups identical networks on each node so that QA comparison is uniform
* Takes care of nearly all networking parameters
* Extendable to multi-host Deployments
* Has debugging and test targets

Bugs, Problems, and Todo's
------------------------------

* VM's are not able to communicate out to gateway
* The Horizon web interface is unable to see and graph all network components.
* Only one network configuration is supported
* Only a single-host Packstack is supports.
* Floating IP's on B7 and C7 networks are damaged when created!

Requirements for Use
=====================

Network Requirements
----------------------

* Target system must be on an isolated subnet with access to the internet.
* Host system has access to the Host subnet and the internet.
* You may need to be on an isolated network segement to access the internal
  Packstack/Openstack VMs.

System Requirements
---------------------

* Must have: VM or baremetal box with 4GB+ ram and single ethernet card.
* Your deployment Host is Centos 7 (others *may* work with minor changes).
* Your Target for Packstack is *already* installed with a *minimal* Centos 7.
* Target has a user "zenoss" with has sudo access, and a valid password
* Target must allow for static ip address assignment
* You have ssh'd into the Target already and accpeted its host-key in your:
  **~/.ssh/known_hosts**

Setup Instructions
=====================

* Copy this entire directory structure to your Controller system:
  The folder that you copy it to will be called $CONTROLLER for convenience.

* In $CONTROLLER/neutron.reference.net/group_vars/all:

  - Take note of the keystone settings. These should not require changes.
    In particular make sure these are set correctly for YOUR system::

      sudo_user: zenoss
      sudo_group: zenoss
      sudo_groups: sudo
      sudo_gid: 1000
      sudo_pass: This is encrypted with value of "zenoss"


* In $CONTROLLER/neutron.reference.net/host_vars/

  - Copy the prototype variables set from
    neutron.reference.net/host_vars/prototype.com to the ip-address or FQDN of
    your Target system::

        cd $CONTROLLER/neutron.reference.net/host_vars
        cp proto.zenoss.loc myhost.zenoss.loc

  - Ensure that "myhost.zenoss.loc" is your actual hostname and that is has
    a valid DNS value in your server. 
    *Using /etc/hosts as a resolver may not work*.

* Edit the variables in neutron.reference.net/host_vars/myhost.zenoss.loc:

   - Make sure all the ip addresses are correct for the defined servers.
   - Make sure all other parameters are correct for your system

* In $CONTROLLER/neutron.reference.net/inventory:

  - Set the value of mpx.zenoss.loc to your Target fqdn/address: myhost.zenoss.loc

* To force a rebuild, remove the file /root/keystonerc_admin on the Target

* To debug your variables, there is a special make target called **vars**
  that will output to /tmp/vars.json.

* WARNING: Rebuilding an environment that is not fresh install has proven to
  be unreliable: Networks, Subnets, IPs, and Routers do not behave.
  We recommend that you re-image a minimal system and start from scratch.

Building Makefile
==================

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

First, cd to $CONTROLLER.
There are three essential build targets:


* make: this target will build all essential features (This is the one to use)
* packstack: This target will only build the Packstack setup
* neutron: This target builds only the network part of neutron

The following make targets are for testing:

* vars: This builds a diagnostic set of variables for debugging
* test: This builds a small set of non-invasive objects for testing.

