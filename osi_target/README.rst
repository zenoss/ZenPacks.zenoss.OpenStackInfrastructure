===================================================
Setup for OpenStackInfrastructure Reference Network
===================================================

This utility sets up the OpenStackInfrastructure Zenpack's reference network
that will be used to test against. As of now it is only suitable for a
single-node Openstack setup.

The following diagram represents the reference network:

.. image:: reference_network.png

Introduction
===============
This build environment builds a Openstack network for use as a target. The
entire process is automated and does not require any knowledge of the
underlying tools.

**WARNING**: Openstack is complex and dynamic set of dependencies and services.
It is correct to assume that the environment this tool creates is for use
as a test target only. There are many features of Openstack that this tool
does not provide. Do not expect the resulting environment to be free of
defects or to be an production-ready Openstack deployment.

Features and Benefits
------------------------

* Uses a simple commands to build/destroy entire Openstack-Neutron environment
* Builds the entire stack from a bare VM
* Setups identical networks on each node so that QA comparison is uniform
* Takes care of nearly all networking parameters
* Installs the Target Ceilometer/RabbitMQ/Zenoss_dispatcher extras
  as per https://github.com/zenoss/ceilometer_zenoss
* Extendible to multi-host Deployments
* Has debugging and test targets


Overview and Definitions
-------------------------

* The main objective is to build the **Reference Network** onto a Target.
* The secondary objective is to destroy the **Reference Network**.
* The **Reference Network** (displayed above) is defined in the
  reference_network.png image.
* The **Control** (deployment) system performs all configuration *to* Target.
* The **Target** system will be configured with Openstack/Packstack/Neutron.
* Note: You must have a separate **Control** system because of reboots and
  network re-configurations.
* Detailed Operations: 

  - Setup the Control system with Ansible
  - Setup the Target system with common_config to set: user, pass, sudo
  - Setup the Target system with Packstack: As per ZP instructions:

    + Add Custom Ceilometer dispatcher
    + Modifies /etc/ceilometer/ceilometer.conf
    + Doen't add [dispatcher_zenoss] section to ceilometer.conf
    + Sets VM State Changes: notify_on_state_change=vm_state in nova.conf
    + Increase polling period to 300 sec in /etc/ceilomster/pipeline.yaml

  - Setup the Target system Neutron network: tenant, net, subnets, routers, vms

Bugs, Problems, and Todo's
------------------------------

* VM's are not able to communicate out to gateway
* The Horizon web interface is unable to see and graph all network components.
* Only one network configuration is supported
* Only a single-host Packstack is supports.
* Floating IPs on B7 and C7 networks are sometimes damaged when created!

Requirements for Use
=====================
Make sure to satisfy the following requirements for all systems and networks.

Network Requirements
----------------------

* Target system must be on an isolated subnet with access to the internet.
* Controller system has access to the Control subnet and the internet.
* You may need to be on an isolated network segment to access the internal
  Packstack/Openstack VMs.

Control System Requirements
-------------------------------
* Your deployment Control is Centos 7. Debian or Ubuntu *may* work.

Target System Requirements
---------------------------

* Must have: VM or bare-metal box with 4GB+ ram and single ethernet card.
* Your Target for Packstack must be installed with a *minimal* Centos 7.
* Target has a user "zenoss" with has sudo access, and a valid password
* Target must allow for static IP address assignment. (AWS won't work!)
* You have SSH'd into the Target once and accepted its host-key in your:
  **~/.ssh/known_hosts**
* Ensure that 'Defaults env_reset' is commented out of /etc/sudoers
* Ensure that 'requiretty' is commented out of /etc/sudoers

Setup Instructions
=====================

* Copy this entire directory structure to your Controller system:
  The folder that you copy it to will be called $OSI_DIR for convenience.

* In $OSI_DIR/neutron.reference.net/inventory:

  - Set the value of the [packstack] target to your Target IP 
    address. For example if your target has the IP 10.11.12.13::
    
      [packstack]
      10.11.12.13

* In $OSI_DIR/neutron.reference.net/group_vars/all:

  - Take note of the keystone settings. These should not require changes.
    In particular make sure these are set correctly for YOUR system::

      sudo_user: zenoss
      sudo_group: zenoss
      sudo_groups: sudo
      sudo_gid: 1000
      sudo_pass: This is encrypted with value of "zenoss"


* (Optional) In $OSI_DIR/neutron.reference.net/host_vars/

  - You do this **ONLY** if you need to override variables from group_vars/all

  - Copy the prototype variables set from
    neutron.reference.net/host_vars/proto.zenoss.com to the IP-address or FQDN
    of your Target system::

        cd $OSI_DIR/neutron.reference.net/host_vars
        cp proto.zenoss.loc myhost.zenoss.loc

  - Ensure that "myhost.zenoss.loc" is your actual hostname and that is has
    a valid DNS value in your server.
    *Using /etc/hosts as a resolver may not work*.

  - Edit the variables in neutron.reference.net/host_vars/myhost.zenoss.loc:

    + Make sure all the ip addresses are correct for the defined servers.
    + Make sure all other parameters are correct for your system

* To force a rebuild, remove /root/keystonerc_admin on the Target

* To debug your variables, there is a special make target called **vars**
  that will output to /tmp/vars.json.

* WARNING: Rebuilding an environment that is not a fresh Linux install has
  proven to be unreliable: Networks, Subnets, IPs, and Routers do not behave.
  We recommend that you re-image a minimal system and start from scratch.

Building with Make
==================

Overview of Execution
------------------------

The top level Makefile (make) will perform the following tasks:

* Setup up the host system by installing Ansible and needed packages.
* On the Target:

  - Install all required packages
  - Setup required users
  - Run Packstack Installer
  - Setup all Neutron networking per **Reference Network**

Build Targets
--------------

First, cd to $OSI_DIR. There are three essential build targets. You normally
will use the first option:

* make: This (primary) target will build all essential features
* packstack: This target will only build the Packstack setup
* neutron: This target builds only the network part of neutron

The following make targets are for testing:

* vars: This builds a diagnostic set of variables for debugging
* test: This builds a small set of non-invasive objects for testing.
* destroy: This destroys all of the Neutron network.

Specific Build Instruction
---------------------------
Once logged in to your Control system (Centos7 recommended), copy the 
files listed above onto it. Then execute the following:

* cd $OSI_DIR
* make
* (enter the password and <enter> for the sudo user when asked)
* (hit <enter> again when asked for the sudo passord)
* Here is a sample invocation::

   [bash: ~]: make
   chmod 700 setup.sh
   Running ./setup.sh
    -> Installing Required prereq Packages on your Server
    .....................................................
   Linux Distribution = Centos
    -> Installing ansible ...............................
   Make sure to edit the configuration files listed in README.rst

    Please Hit <return> to continue or ctrl-c to stop:

   cd neutron.reference.net && make all
   make[1]: Entering directory '$OSI_TARGET/neutron.reference.net'
   ansible-playbook -vvvvv -i inventory all.yml -Kk
   SSH password: *************
   sudo password [defaults to SSH password]: <ret>

Specific Build Troubleshooting
-------------------------------
* If you have an error in the beginning of the install process like this:
  "ansible: ssh connection error waiting for sudo or su password prompt"
  you should go back and ensure the /etc/sudoers is setup as in the
  requirements.

* If Ansible fails during a Reboot, just type "make" again. Sometimes the
  reboot will confuse Ansible.

Rebuilding the Neutron Network
-------------------------------
* make neutron  

Specific Destroy Instruction
-----------------------------

Just type::

   make destroy

Video Links
------------------
https://docs.google.com/a/zenoss.com/file/d/0B7N3MU9SXh19RjhGa215ckViRms/edit?usp=drive_web

