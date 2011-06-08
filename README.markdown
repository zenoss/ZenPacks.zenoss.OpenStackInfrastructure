# ZenPacks.zenoss.OpenStack

## About
This project is a [Zenoss][] extension (ZenPack) that allows for monitoring of
OpenStack. This means that you can monitor the flavors, images and servers
a user or consumer perspective. OpenStack Compute v1.1 (Cactus) is known to be
supported. Specifically this means that Rackspace's CloudServers can be
monitored.

In the future it is likely that support for monitoring OpenStack Storage
(Swift) will be added.

[OpenStack][] is a global collaboration of developers and cloud computing
technologists producing the ubiquitous open source cloud computing platform
for public and private clouds. The project aims to deliver solutions for all
types of clouds by being simple to implement, massively scalable, and feature
rich. The technology consists of a series of interrelated projects delivering
various components for a cloud infrastructure solution.

## Installation
You must first have, or install, Zenoss 3.1.0 or later. Core and Enterprise
versions are supported. You can download the free Core version of Zenoss from
<http://community.zenoss.org/community/download>.

### Normal Installation (packaged egg)
Download the [latest OpenStack ZenPack][]. Copy this file to your Zenoss
server and run the following commands as the zenoss user.

    zenpack --install ZenPacks.zenoss.OpenStack-1.0.2-py2.6.egg
    zenoss restart

### Developer Installation (link mode)
If you wish to further develop and possibly contribute back to the OpenStack
ZenPack you should clone the [git repository][], then install the ZenPack in
developer mode using the following commands.

    git clone git://github.com/zenoss/ZenPacks.zenoss.OpenStack.git
    zenpack --link --install ZenPacks.zenoss.OpenStack
    zenoss restart

## Usage
Once the OpenStack ZenPack is installed you can begin monitoring by going to
the infrastructure screen and clicking the normal button for adding devices.
You'll find a new option labeled, "Add OpenStack."

Choose that option and you'll be presented with a dialog asking for the
following inputs.

 1. Hostname or IP - An example would be rackspacecloud.com.
 2. Auth URL - For Rackspace this would be https://auth.api.rackspacecloud.com/v1.0
 3. Username - Same username used to login to OpenStack web interface
 4. API Key - Can be found by going to "Your Account/API Access"

Once you click Add, Zenoss will contact the OpenStack API and discover
servers, images and flavors. Once it is complete you'll find a new device in
the OpenStack device class with the same name as the hostname or IP you
entered into the dialog. Click into this new device to see everything that was
discovered.

The following types of elements are discovered.

 * Servers
 * Images
 * Flavors

The following metrics are collected.

 * Total Servers and Servers by State
  * States: Active, Build, Rebuild, Suspended, Queue Resize, Prep Resize,
            Resize, Verify Resize, Password, Rescue, Reboot, Hard Reboot,
            Delete IP, Unknown, Other
 * Total Images and Images by State
  * States: Active, Saving, Preparing, Queued, Failed, Unknown, Other
 * Total Flavors

Status monitoring is performed on servers and images with the following
mapping of state to Zenoss event severity.

Servers State to Severity Mapping:

 * Reboot, Hard Reboot, Build, Rebuild, Rescue, Unknown == Critical
 * Resize == Error
 * Prep Resize, Delete IP == Warning
 * Suspended, Queue Resize, Verify Resize, Password == Info
 * Active == Clear

Images State to Severity Mapping:

 * Failed, Unknown == Critical
 * Queued, Saving, Preparing == Info
 * Active == Clear

If you are also using Zenoss to monitor the guest operating system running
within the server Zenoss will present the graphs for that operating system
when the graphs option is chosen for the OpenStack server.


[Zenoss]: <http://www.zenoss.com/>
[latest OpenStack ZenPack]: <https://github.com/downloads/zenoss/ZenPacks.zenoss.OpenStack/ZenPacks.zenoss.OpenStack-1.0.2-py2.6.egg>
[git repository]: <https://github.com/zenoss/ZenPacks.zenoss.OpenStack>
[OpenStack]: <http://www.openstack.org/>
