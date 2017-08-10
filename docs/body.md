<style>
img.thumbnail {
    clear: right;
    float: right;
    margin: 0 0 10px 10px;
    padding: 0px;
    width: 320px;
    font-size: small;
    font-style: italic;
}
br.clear {
    clear: right;
}
dd {
    font-size: smaller;
}
img.gallerythumbnail {
    padding: 0px;
    width: 320px;
    font-size: small;
    font-style: italic;
}

</style>

Gallery
-------

+:---------------------------------------------:+:---------------------------------------------------:+:-------------------------------------------------------------:+
| [![][regions.png]][regions.png]               | [![][tenants.png]][tenants.png]                     | [![][availabilityzones.png]][availabilityzones.png]           |
|                                               |                                                     |                                                               |
| Region                                        | Tenants                                             | Availability Zones                                            |
+-----------------------------------------------+-----------------------------------------------------+---------------------------------------------------------------+
| [![][devicegraphs.png]][devicegraphs.png]     |                                                     | [![][openstackcomponentview.png]][openstackcomponentview.png] |
|                                               |                                                     |                                                               |
| Device Graphs                                 |                                                     | Component View                                                |
+-----------------------------------------------+-----------------------------------------------------+---------------------------------------------------------------+
| [![][hosts.png]][hosts.png]                   | [![][hypervisors.png]][hypervisors.png]             | [![][images.png]][images.png]                                 |
|                                               |                                                     |                                                               |
| Hosts                                         | Hypervisors                                         | Images                                                        |
+-----------------------------------------------+-----------------------------------------------------+---------------------------------------------------------------+
| [![][novaapis.png]][novaapis.png]             | [![][novaservices.png]][novaservices.png]           | [![][neutronagents.png]][neutronagents.png]                   |
|                                               |                                                     |                                                               |
| Nova APIs                                     | Nova Services                                       | Neutron Agents                                                |
+-----------------------------------------------+-----------------------------------------------------+---------------------------------------------------------------+
| [![][instances.png]][instances.png]           | [![][vnics.png]][vnics.png]                         |                                                               |
|                                               |                                                     |                                                               |
| Instances                                     | vNICs                                               |                                                               |
+-----------------------------------------------+-----------------------------------------------------+---------------------------------------------------------------+
| [![][networks.png]][networks.png]             | [![][ports.png]][ports.png]                         |                                                               |
|                                               |                                                     |                                                               |
| Networks                                      | Ports                                               |                                                               |
+-----------------------------------------------+-----------------------------------------------------+---------------------------------------------------------------+
| [![][floatingips.png]][floatingips.png]       | [![][routers.png]][routers.png]                     | [![][subnets.png]][subnets.png]                               |
|                                               |                                                     |                                                               |
| Floating IPs                                  | Routers                                             | Subnets                                                       |
+-----------------------------------------------+-----------------------------------------------------+---------------------------------------------------------------+
| [![][cinderservices.png]][cinderservices.png] | [![][volumes.png]][volumes.png]                     | [![][volsnapshots.png]][volsnapshots.png]                     |
|                                               |                                                     |                                                               |
| Cinder Services                               | Volumes                                             | Volume Snapshots                                              |
+-----------------------------------------------+-----------------------------------------------------+---------------------------------------------------------------+


Prerequisites
-------------

- A supported OpenStack version (see below)
- ceilometer_zenoss compatible with your version of OpenStack (See [Ceilometer Enablement](#ceilometer-enablement))
    - This Zenoss-specific plugin must be installed on all your Ceilometer nodes as described.
      If not installed and configured properly,    Instances and vNICs graphs
      will be blank, and Zenoss will not detect changes (such as new instances or
      instance state changes) until a full model is performed.
* Administrative credentials for your OpenStack environment 
    - Username, password, keystone URL, Region
- Once the zenpack is installed, provide SSH credentials to the linux devices in your OpenStack environment before adding any devices.
    - Configure the zCommandUsername/zCommandPassword/zKeyPath properties on the /Devices/Server/SSH/Linux/NovaHost device class.
    - If your OpenStack nodes are already managed under Zenoss, move them into /Devices/Server/SSH/Linux/NovaHost


### Supported OpenStack Releases

* 2.0.x support Icehouse and Juno
* 2.1.x support Juno and Kilo
* 2.2.x support Juno, Kilo, and Liberty
* 2.3.x support Mitaka

Installed Items
---------------

### Configuration Properties 
- zOpenStackAuthUrl: The URL of the Identity endpoint. 
- zOpenStackExtraHosts: The list of extra hosts that will be added to the
system once OpenStack Infrastructure device is modeled. 
- zOpenStackExtraApiEndpoints: A list of URLs to monitor for openstack
APIs. Format is \<service type\>:\<full url\> for each. 
- zOpenStackHostDeviceClass: Used as a default device class for defined
hosts in zOpenStackExtraHosts and zOpenStackNovaApiHosts properties.
Default is /Server/SSH/Linux/NovaHost. 
- zOpenStackNovaApiHosts: The
list of hosts upon which nova-api runs. This is required when the IP
address in the nova API url does not match any known host. 
- zOpenStackCinderApiHosts: The list of hosts upon which cinder-api runs.
This is required when the IP address in the cinder API url does not
match any known host. 
- zOpenStackHostMapToId: A list of \<name\>=\<id\>,
used to force a host referred to by openstack with the given name to be
represented in Zenoss as a host component with the given ID. (this is
not commonly used) 
- zOpenStackHostMapSame: A list of \<name1\>=\<name2\>,
used to inform the modeler that the same host may be referred to with an
alternate name by some part of openstack. (this is not commonly used) 
- zOpenStackNeutronConfigDir: Path to directory that contains Neutron configuration files. Default is /etc/neutron. 
- zOpenStackProjectId: Corresponds to tenant name, project to work on. 
- zOpenStackRegionName: The name of the OpenStack Region to use. Regions are 
autonomous OpenStack clouds joined together through shared Keystone identity
server and managed through a common interface. 
- zOpenStackRunNovaManageInContainer, zOpenStackRunVirshQemuInContainer, zOpenStackRunNeutronCommonInContainer: 
Used when openstack processes are running inside of docker containers. Provide the container names (or a pattern to match them) here, or leave blank in a non-containerized openstack environment.

### Device Classes 
- /OpenStack: Root OpenStack device class. Typically, devices should not be put in this device class. 
- /OpenStack/Infrastructure: Device class for OpenStack Infrastructure endpoints. 
- /Server/SSH/Linux/NovaHost: Device class for Nova host instances.

### Modeler Plugins 
- zenoss.OpenStackInfrastructure: Main modeler plugin- Queries the OpenStack APIs to populate the zenoss model.
- zenoss.cmd.linux.openstack.hostfqdn: Used to get OpenStack host FQDN. 
- zenoss.cmd.linux.openstack.inifiles: Used to gather neutron.conf and ml2_conf.ini files. 
- zenoss.cmd.linux.openstack.libvirt: Used to get OpenStack instance virtual NIC information using libvert. 
- zenoss.cmd.linux.openstack.nova: Used to get installed OpenStack version.

### Datasources 
- CinderServiceStatusDataSource: Checks the status of Cinder services via the Cinder API. 
- EventsAMQPDataSource: Stores events received from OpenStack Ceilometer via AMQP.
- HeartbeatsAMQPDataSource: Checks that heartbeats are received from OpenStack Ceilometer via AMQP. 
- NeutronAgentStatusDataSource: Checks the status of Neutron agents via the Neutron API. 
- NovaServiceStatusDataSource: Checks the status of Nova services via the Nova API. 
- PerfAMQPDataSource: Stores performance data received from OpenStack Ceilometer via AMQP. 
- PerfCeilometerAPIDataSource: Used to capture datapoints from OpenStack Ceilometer. 
- QueueSizeDataSource: Checks the number of unprocessed messages in Ceilometer AMQP queues.

### Monitoring Templates 
- /OpenStack/Infrastructure/ 
    - Endpoint 
    - Instance 
    - vNIC

### Event Classes and Mappings 
- /OpenStack 
    - OpenStack Events Default
- /OpenStack/Cinder 
- /OpenStack/Cinder/Snapshot 
    - Cinder Snapshot default mapping 
- /OpenStack/Cinder/Volume 
    - cinder.volume default mapping 
- /OpenStack/compute 
- /OpenStack/compute/instance 
    - compute.instance default mapping 
    - compute.instance.create.error 
    - compute.instance.exists 
    - compute.instance.exists.verified.old 
- /OpenStack/dhcp_agent 
    - dhcp_agent default mapping 
- /OpenStack/firewall 
    - firewall default mapping 
- /OpenStack/firewall_policy 
    - firewall_policy default mapping 
- /OpenStack/firewall_rule 
    - firewall_rule default mapping 
- /OpenStack/floatingip 
    - floatingip default mapping 
- /OpenStack/network 
    - network default mapping 
- /OpenStack/port 
    - port default mapping 
- /OpenStack/router 
    - router default mapping 
- /OpenStack/security_group 
    - security_group default mapping 
- /OpenStack/security_group_rule 
    - security_group_rule default mapping 
- /OpenStack/subnet 
    - subnet default mapping 
- /Status/Heartbeat/ 
    - openStackCeilometerHeartbeat 
- /Status 
    - openStackCinderServiceStatus 
    - openStackIniFileAccess 
    - openStackIniFileOptionParsing 
    - openStackNeutronAgentStatus 
    - openStackNovaServiceStatus 
    - openStackApiEndpointStatus

### Processes 
- /OpenStack 
- /OpenStack/ceilometer-agent-central 
- /OpenStack/ceilometer-agent-compute 
- /OpenStack/ceilometer-agent-notification 
- /OpenStack/ceilometer-alarm-evaluator 
- /OpenStack/ceilometer-alarm-notifier 
- /OpenStack/ceilometer-api 
- /OpenStack/ceilometer-collector 
- /OpenStack/ceilometer-polling 
- /OpenStack/cinder-api 
- /OpenStack/cinder-backup 
- /OpenStack/cinder-scheduler 
- /OpenStack/cinder-volume 
- /OpenStack/glance-api 
- /OpenStack/glance-registry 
- /OpenStack/gnocchi-metricd 
- /OpenStack/gnocchi-statsd 
- /OpenStack/keystone-admin 
- /OpenStack/keystone-all 
- /OpenStack/keystone-main 
- /OpenStack/neutron-dhcp-agent 
- /OpenStack/neutron-l3-agent 
- /OpenStack/neutron-lbaas-agent 
- /OpenStack/neutron-metadata-agent 
- /OpenStack/neutron-metering-agent
- /OpenStack/neutron-openvswitch-agent 
- /OpenStack/neutron-server 
- /OpenStack/nova-api 
- /OpenStack/nova-cert 
- /OpenStack/nova-compute
- /OpenStack/nova-conductor 
- /OpenStack/nova-consoleauth 
- /OpenStack/nova-network 
- /OpenStack/nova-scheduler 
- /OpenStack/rabbitmq-server

Basic Usage
-----------

The OpenStackInfrastructrue ZenPack models vNICs associated with
OpenStack Instances. In order to correctly model these vNICs, you must
first fully model the OpenStack environment and then configure and model
the /Server/SSH/Linux/NovaHost devices. See the section below for
details on configuration specifics.

### Device Setup via UI

Once the OpenStack ZenPack is installed and you can begin monitoring by
going to the infrastructure screen and clicking the normal button for
adding devices. You'll find a new option labeled, "Add OpenStack
Endpoint (Infrastructure)."

Choose that option and you'll be presented with a dialog asking for the
following inputs.

* Device To Create - non-empty, non-ip, non-dns, unique name to use for this device in Zenoss. ''See note below''.
* Auth URL - A keystone URL, such as http://\<hostname\>:5000/v2.0/
* Username, Password/API Key, Project/Tenant ID - *Administrative* credentials to your Zenoss instance.
* Region Name - choose the correct region from the drop-down. You may only choose one, so each region you wish to manage must be registered as a separate endpoint in Zenoss.

Once you click Add, Zenoss will contact the OpenStack API and discover
servers, images and flavors. Once it is complete you'll find a new
device in the OpenStack device class with the same name as the hostname
or IP you entered into the dialog. Click into this new device to see
everything that was discovered.

{{note|'''Device Name'''}} The '''Device name''' should be a non-empty,
non-hostname, non-IP, since that name will be used when the host is
registered as a Linux device. The name should be unique within the
Zenoss environment. This is especially important if you are adding
another device that share the same IP address or hostname that already
exist on another device. Not doing this may result in devices with the
same name conflicting with each other. (e.g. attempting to model device
would show modeling results that belong to another device OR device
would show relations that do not belong to that device)

### Device Setup via Zenbatchload

You can setup the device using *zenbatchload* as follows:

``` {.bash}
zenbatchload <filename>
```

where <filename> should have the form:

```
/Devices/OpenStack/Infrastructure loader='openstackinfrastructure',\
    loader_arg_keys=['deviceName', 'username', 'api_key', 'project_id', 'auth_url', 'region_name', 'collector']
<devicename> username='<username>', api_key='<password>', project_id='<tenant ID>', \
    auth_url='http://<ip address>:5000/v2.0/', region_name='RegionOne'

/Devices/Server/SSH/Linux/NovaHost zCommandUsername='username',
zCommandPassword='password'
```

* As mentioned before, zCommandUsername/zCommandPassword properties
    must be set for /Devices/Server/SSH/Linux/NovaHost devices (and
    vNICs) to be correctly modeled.

### Organizational Elements

The following organizational elements are discovered:

* Regions
* Availability Zones
* Tenants

The following virtual-machine elements are discovered:

* Nova Services (processes supporting nova servers)
* Instances (Servers)
* Hosts
* Hypervisors
* Images
* Flavors
* Nova API Endpoints

The following network elements are discovered:

* Neutron Agents
* Networks
* Subnets
* Routers
* Ports
* Floating-Ips
* vNICs (from NovaHost linux device modeling)

The following block storage elements are discovered:

* Cinder Services (processes supporting block storage)
* Cinder API Endpoints
* Volumes
* Volume Snapshots
* Volume Types
* Storage Pools
* Cinder Quotas

### Metrics

The following component level metrics are collected:

Instances

* CPU Utilization (percent)
* Disk Requests (requests/sec)
* Disk IO Rate (bytes/sec) vNICs
* Network Packet Rate (packets/sec)
* Network Throughput (bytes/sec) Hosts
* Load Average (processes)
* CPU Utilization (percent)
* Free Memory (bytes)
* Free Swap (bytes)
* IO (sectors/sec) Nova Services
* CPU Utilization (percent)
* Memory
* Utilization (bytes)
* Process Count (processes) Neutron Agents
* CPU
* Utilization (percent)
* Memory Utilization (bytes)
* Process Count (processes)
* Cinder Services
* CPU Utilization (percent)
* Memory Utilization (bytes)
* Process Count (processes) Volumes (requires LinuxMonitor ZenPack \>= 2.0.0)
* Storage Utilization (percent)
* Operation Throughput (operations/sec)
* Merge Rate (merged/sec)
* Sector Throughput (sectors/sec)
* IO Operations (operations)
* IO Utilization (percent)
* Weighted IO Utilization (weighted percent)
* Volume Snapshots (requires LinuxMonitor ZenPack \>= 2.0.0)
* Storage Utilization (percent)
* Operation Throughput (operations/sec)
* Merge Rate (merged/sec)
* Sector Throughput (sectors/sec)
* IO Operations (operations)
* IO Utilization (percent)
* Weighted IO Utilization (weighted percent)

The following device level metrics are collected:

* Flavors
* Total (count) Images
* Total (count)
* Total count per image state Servers
* Total (count)
* Total count per server state
* Queues
* Event (count)
* Performance (count) Agents
* Total (count)
* Total count per agent type Networks
* Total (count)
* Total count per network state Routers
* Total (count)
* Total count per router state Volumes
* Total (count)
* Total count per volume state Volume Snapshots
* Total (count)
* Total count per volume snapshot state Volume Pool
* Total (count)
* Total count per volume pool state

Note: All events processed through Ceilometer are automatically 
exposed via the Zenoss Event Console, and all metrics collected by Ceilometer
may be collected and graphed in Zenoss through the use of custom monitoring 
templates.

Daemons
-------

+--------------------------------------+--------------------------------------+
| Type                                 | Name                                 |
+======================================+======================================+
| Modeler                              | zenmodeler                           |
+--------------------------------------+--------------------------------------+
| Performance Collector                | zencommand, zenpython                |
+--------------------------------------+--------------------------------------+

Ceilometer Enablement
---------------------

Although you may add an OpenStack device to Zenoss, as shown above,
event and performance data will not be collected until the following
steps are performed.

### Zenoss Configuration Steps - First-Time Installation

The first time you install this zenpack, you must run `openstack_amqp_config` to create the RabbitMQ exchanges that are used to integrate with ceilometer.  

To run this script, log into the master server (Zenoss 4.x) or Zope container (zenoss 5.x) and run it as follows:

``` {.bash}
$ $ZENHOME/ZenPacks/ZenPacks.zenoss.OpenStackInfrastructure*/ZenPacks/zenoss/OpenStackInfrastructure/bin/openstack_amqp_config
```

It will do the following:

* If not already set, populate the `zOpenStackAMQPUsername` and `zOpenStackAMQPPassword` zProperties.   (Generating a random password)
* Create the required AMQP exchanges in RabbitMQ if they are missing
* Register the user from `zOpenStackAMQPUsername` in rabbitmq and update its password to match `zOpenStackAMQPPassword`.
* Display the configuration parameters that you will need to add to the `ceilometer.conf` file on your OpenStack servers (see below.)

You may safely re-run `openstack_amqp_config` at any time to display the
configuration parameters, or to update the username/password after you have changed `zOpenStackAMQPUsername` and `zOpenStackAMQPPassword`

### Zenoss Configuration Steps - ZenPack Upgrades

If this is the first time you are upgrading from a version of the zenpack prior to 2.4.0, you should first set `zOpenStackAMQPUsername` and `zOpenStackAMQPPassword` to match the values of `amqp_userid` and `amqp_password` from `ceilometer.conf` on your openstack systems.

If you do not do this, if you run `openstack_amqp_config` in the future, it will generate a new password and reconfigure rabbitmq to use that password instead of the one you have been using, which would interrupt monitoring.

For upgrade from version 2.4.0 or higher, there are no special steps required, no changes required on the OpenStack side, and no need to run `openstack_amqp_config`.

### Zenoss 5.x - RabbitMQ-Ceilometer

Version 2.4.0 of this zenpack introduces a new service, `RabbitMQ-Ceilometer`.  This is a dedicated instance of RabbitMQ on each collector which is used solely for integration with ceilometer, rather than using the standard `RabbitMQ` service that is used by Zenoss itself.  This better distributes any load as well as providing better support for distributed collector scenarios where the target OpenStack environment might not have network access to the central Zenoss servers.

This ZenPack still supports the previous configuration, where messages were sent from ceilometer to the main `RabbitMQ` service in zenoss,  so if you were previously using it that way successfully, there is no need to reconfigure your ceilometer.conf to point it at the new location.

For new openstack installs, we recommend using the RabbitMQ-Ceilometer endpoint, which is what will be reported by `openstack_amqp_config`.

### OpenStack Ceilometer Configuration Steps

Zenoss relies upon a Ceilometer dispatcher plugin to ship raw event and
metering data from Ceilometer to Zenoss for storage in the Zenoss event
and performance databases. This integration is done by publishing
messages to Zenoss's RabbitMQ server.

This dispatcher should be installed on all nodes running any ceilometer,
but particularly those running ceilometer-collector or
ceilometer-agent-notification.

Ceilometer_zenoss must be installed on all ceilometer nodes in the openstack
environment.  To install the latest released version from RPM:

Download the appropriate RPM and install as usual:

* [ceilometer_zenoss-1.1.1-1.el6.noarch.rpm]
* [ceilometer_zenoss-1.1.1-1.el7.noarch.rpm]

Alternatively, the module may be installed from source as follows:

``` {.bash]
$ sudo pip -q install --force-reinstall https://github.com/zenoss/ceilometer_zenoss/archive/master.zip 
```

It is then necessary to install a modified `/etc/ceilometer/event_definitions.yaml` file that
is included in ceilometer_zenoss:

``` {.bash}
$ sudo cp /usr/lib/*/site-packages/ceilometer_zenoss/event_definitions.yaml /etc/ceilometer/
```

Then, ensure that the configuration options output by the `openstack_amqp_config`
script previously are added to /etc/ceilometer/ceilometer.conf file on all
openstack nodes.

Restart all Ceilometer services on all hosts after making these changes.

### Optional Steps

#### VM State Changes

By default, instance state changes will be captured by Zenoss when
certain events occur, for example, when an instance is shut down, the
state change to SHUTDOWN will be reflected in Zenoss.

However, certain state changes that don't correspond to another defined
event may not be picked up until the next time Zenoss models the
environment.

If you would like to reduce the likelihood of this occurring, you can
configure OpenStack Nova to send an event (through ceilometer) to Zenoss
whenever any VM state change occurs by adding the following to
/etc/nova/nova.conf on all Nova hosts:

```
[DEFAULT]
notify_on_state_change=vm_and_task_state 
```

For Liberty:
```
[oslo_messaging_notifications]
notification_driver = messagingv2
```

For Mitaka:
```
[oslo_messaging_notifications]
driver = messagingv2
```

Save /etc/nova/nova.conf and restart nova services.

Note that notify_on_state_change will cause increased event load,
both on OpenStack and Zenoss, and additional processing within the event
transforms in Zenoss to keep the model consistent. Since most instance
changes will still be caught without this option enabled, it is
recommended to leave notify_on_state_change disabled if your
OpenStack environment is very large.

#### Increasing Polling Interval

Zenoss will process performance datapoints from Ceilometer every 10
minutes, since by default, Ceilometer will only produce one datapoint
every 10 minutes. This can be adjusted by modifying the "interval: 600"
line in your pipeline.yaml file (typically
/etc/ceilometer/pipeline.yaml).

#### Troubleshooting

For additional details on ceilometer integration and troubleshooting tips,
please reference this [knowledgebase article](https://support.zenoss.com/hc/en-us/articles/115001165446-Understanding-and-Troubleshooting-OpenStack-Ceilometer-Integration-with-Zenoss-Resource-Manager).


Host Identification
-------------------

The openstack APIs do not contain an authoritative list of hosts with unique
IDs.  Instead, various APIs show hosts by name or IP.   There zenpack does
its best to identify IPs and names that refer to the same host, and represent
them as a single host component.   In some cases, though, it can't tell, 
and the same host may be modeled twice, or with an incorrect name.

Two zProperties are provided to override the default behavior of the zenpack
when this happens.

* zOpenStackHostMapSame

    Specifies that two names refer to the same host.  It is a list of entries of the form:
    ```
    <name1>=<name2>
    ```
    For example, 

    ```
    my.example.com=myothername.example.com
    my.example.com=10.1.1.1
    ```

    This means that any time the host "my.example.com", "myothername.example.com",
    or "10.1.1.1" is encountered, they will be considered to be the same host,
    rather than separate ones.

* zOpenStackHostMapToId

    It is also possible to specify not only that the devices are the same, but that
    they should be identified with one specific identifier  (otherwise, one 
    may be chosen at random).   In this case, a list of entries of the form
    ```
    <name>=<id>
    ```
    may be provided in the zOpenStackHostMapToId zProperty.   For example,
    ```
    myothername.example.com=my.example.com
    10.1.1.1=my.example.com
    ```
    This would cause "my.example.com", "myothername.example.com",
    or "10.1.1.1" to all be definitely identified as "my.example.com", without
    the ambiguity that could exist if zOpenStackHostMapSame were used.

* zOpenStackHostLocalDomain

    In some environments (in particular, the Red Hat OpenStack Platform),
    hosts are assigned names that end in '.localdomain'.   This would cause
    problems for zenoss, because it is not possible to create a device
    in zenoss with such a name, as they all resolve to 127.0.0.1, rather than
    their actual IP.

    The default value of zOpenStackHostLocalDomain is a blank string, meaning
    that the '.localdomain' suffix will be stripped from host names, and
    devices will be created in zenoss with those shortened names.  If those
    names do not resolve in DNS, they will be created without IPs, and
    will not be modeled.  You would need to manually set their management IPs
    so that they can be modeled.

    Alternatively, if you already have these hostnames in dns, but just with
    a different domain name than ".localdomain", you may specify this domain
    name here, and it will be substituted for localdomain, and the devices 
    will model automatically, based on the IPs returned from DNS.

Modeling Containerized Environments
-----------------------------------

If the target openstack environment runs processes inside of docker containers,
it is necessary to configure several zProperties before modeling will 
succeed. 

* zOpenStackRunNovaManageInContainer:  Container to run "nova-manage" in
* zOpenStackRunVirshQemuInContainer: Container to run "virsh" in
* zOpenStackRunNeutronCommonInContainer: Container to access neutron configuration files in.

These should be set to container names or substrings of the container names.
These can be set on the /Server/SSH/Linux/NovaHost device class or 
specific devices within it, as necessary. 

NOTE:  These zProperties must be set on the linux devices, not the 
openstack (/OpenStack/Infrastructure) devices.

Zenoss Analytics
----------------

This ZenPack provides additional support for Zenoss Analytics. Perform
the following steps to install extra reporting resources into Zenoss
Analytics after installing the ZenPack.

1.  Copy vsphere-analytics.zip from
    \$ZENHOME/ZenPacks/ZenPacks.zenoss.OpenStackInfrastructure\*/ZenPacks/zenoss/OpenStackInfrastructure/analytics/
    on your Zenoss server.
2.  Navigate to Zenoss Analytics in your browser.
3.  Login as superuser.
4.  Remove any existing *OpenStackInfrastructure ZenPack* folder.
    1.  Choose *Repository* from the *View* menu at the top of the page.
    2.  Expand *Public* in the list of folders.
    3.  Right-click on *OpenStackInfrastructure ZenPack* folder and choose *Delete*.
    4.  Confirm deletion by clicking *OK*.
5.  Add the new *OpenStackInfrastructure ZenPack* folder.
    1.  Choose *Server Settings* from the ''Manage' menu at the top of
        the page.
    2.  Choose *Import* in the left page.
    3.  Remove checks from all check boxes.
    4.  Click *Choose File* to import a data file.
    5.  Choose the OpenStackInfrastructure-analytics.zip file copied from your Zenoss
        server.
    6.  Click *Import*.

You can now navigate back to the ''OpenStackInfrastructure ZenPack''
folder in the repository to see the following resources added by the
bundle.

* Domains
    * OpenStackInfrastructure Domain

* Ad Hoc Views
    * OpenStack Instance List

The OpenStackInfrastructure Domain can be used to create ad hoc views using the
following steps.

1.  Choose *Ad Hoc View* from the *Create* menu.
2.  Click *Domains* at the top of the data chooser dialog.
3.  Expand *Public* then *OpenStackInfrastructure ZenPack*.
4.  Choose the *OpenStackInfrastructure Domain* domain


Service Impact and Root Cause Analysis
--------------------------------------

When combined with the Zenoss Service Dynamics product, this ZenPack
adds built-in service impact and root cause analysis capabilities for
OpenStack infrastructure and instances. The service impact relationships
shown in the diagram and described below are automatically added. These
will be included in any services that contain one or more of the
explicitly mentioned components.


[![][impact.png]][impact.png]


### Recommended Impact Setup

Since most components will be related to Tenants and Region we
recommend:

* Navigate to Services (Impact)
* Add a Dynamic Service to your Services tab
* Add all Tenants to the Dynamic Service
* Add all Regions to the Dynamic Service

### Impact Relations

Component failures will affect Impact as follows:

Internal Impact Relationships

* OpenStack API endpoint impacts all Hosts
* Availability zone impacts associated Region
* Host impacts associated Hypervisors, Nova Services, Cells, Nova Apis,
    Neutron Agents, and Cinder Services
* Hypervisor impacts the resident Instances (VMs)
* Nova Service affects the Availability Zone or Region that it supports
* Instance impacts the associated Tenant
* vNIC impacts the related Instance.
* Port impacts associated Instance
* Subnet impacts associated Ports and Tenants
* Floating-IP impacts associated Port
* Network impacts associated Subnets and Tenants
* Router impacts associated Subnets and Floating-ips
* Neutron Agent impacts associated Networks, Subnets and Routers
* volume impacts Instances (VMs), Volume Snapshots

External Impact Relationships

* Instance impacts guest operating system device.
* Cisco UCS vNIC impacts related host's underlying Linux device NIC.
* Cisco UCS service profile impacts host's underlying Linux device.
* Host impacted by associated Linux device.
* OS Processes on an underlying Linux device impact corresponding Nova APIs,
    Nova Services, Neutron Agents and Cinder Services on Host.

### Examples

+:-----------------------------------------------:+:-------------------------------------------------------------------------------:+
| [![][impact_instance.png]][impact_instance.png] | [![][impact_instance_with_floatingip.png]][impact_instance_with_floatingip.png] |
|                                                 |                                                                                 |
| Impact (Instance)                               | Impact (Floating IP)                                                            |
+-------------------------------------------------+---------------------------------------------------------------------------------+
| [![][impact_region.png]][impact_region.png]     | [![][impact_tenant.png]][impact_tenant.png]                                     |
|                                                 |                                                                                 |
| Impact (Region)                                 | Impact (Tenant)                                                                 |
+-------------------------------------------------+---------------------------------------------------------------------------------+


Integration with other ZenPacks
-------------------------------

In some cases, the underlying network or storage technology is monitored
by a different zenpack.  The OpenStackInfrastructure zenpack is able
to integrate with the following zenpacks to provide component-level linkage
and impact model integration:

* Neutron OpenvSwitch ml2 plugin <-> [OpenvSwitch](https://www.zenoss.com/product/zenpacks/openvswitch) ZenPack
* Neutron APIC ml2 plugin <-> [Cisco APIC](https://www.zenoss.com/product/zenpacks/cisco-apic) ZenPack
* Neutron NSX ml2 plugin <-> [VMWare NSX](https://www.zenoss.com/product/zenpacks/vmware-nsx) ZenPack
* Cinder LVM  logical volumes <-> [Linux Monitor](https://www.zenoss.com/product/zenpacks/linux-monitor) ZenPack (>= 2.0.0)
* Ceph RBD volumes <-> [Ceph](https://www.zenoss.com/product/zenpacks/ceph) ZenPack

Known Issues
------------

- [ZEN-14585](https://jira.zenoss.com/browse/ZEN-14585): The same endpoint can not be monitored both as user and an infrastructure endpoints.
    - Workaround: If you have been previously monitoring the endpoint as a User endpoint, delete the device before you re-add it as an Infrastructure endpoint.
- [ZEN-17905](https://jira.zenoss.com/browse/ZEN-17905): Nova APIs component: Grey icons for Enabled and State after model/monitor.
    - OpenStack nova service API does not provide information about Nova-API, so its status is, in fact, unknown.
- ZPS-1762: When using OpenvSwitch integration, the Linux devices must be added to the system first (normally through automatic discovery by the OpenStackInfrastructure ZenPack) before the corresponding OpenvSwitch devices are registered.  This is because the two devices use the same management IP address, and a special exclusion is in place for OpenvSwitch devices, allowing them to be added after the linux device, but not the other way around.


Changes
-------

2.4.0

- Model API endpoints (currently only the public keystone API
endpoint). Allow user to specify additional ones via
zOpenStackExtraApiEndpoints. Supported API services are included in the
provided ApiEndpoint monitoring template.
- Removed zOpenStackCeilometerUrl zproperty, which was unused

2.3.3
- Fix error in modeler when neutron agent extension is not available (ZPS-1243)
- Fix certain problems modeling openstack environments where hosts have .localdomain names (ZPS-1244)

2.3.2

- Wrap brain.getObject() into try/except block (ZPS-442)

2.3.1

- Upgrade txsshclient to fix critical change in twisted.conch (ZEN-25870)

2.3.0

- Added support for Mitaka. 
- Provide various host-checking fixes: (ZEN-24803, ZEN-25262) 
- Prevent queues from being deleted when device is removed/re-added (ZEN-24803) 
- Use publicURL if adminURL not working: (ZEN-24546) 
- Upgrade ZenPackLib to 1.1.0 to fix Liberty/Mitaka status: (ZEN-24464)

2.2.0f

- Added Cinder block storage components. 
- Added LVM, Ceph block storage integration via LinuxMonitor and Ceph ZenPacks. 
- Various bug fixes

2.1.3

- Fix malformed hostnames in the F5 LBAAS plugin (ZEN-22126)

2.1.2

- Remove deprecated ceilometer-agent-notification heartbeats

2.1.1 

- Various bug fixes 
- Add meta.zcml feature tags for Neutron Integration

2.1.0

- Added Neutron network components 
- Update Impact models for Neutron 
- Update multiple UI interfaces 
- Upgrade to ZenPackLib 1.0.1
- Add ML2 Plugin Capability

2.0.0

- Initial Release



[ceilometer_zenoss-1.1.1-1.el6.noarch.rpm]: ceilometer_zenoss-1.1.1-1.el6.noarch.rpm
[ceilometer_zenoss-1.1.1-1.el7.noarch.rpm]: ceilometer_zenoss-1.1.1-1.el7.noarch.rpm

[impact.png]: ../docs/images/impact.png "Impact Diagram"

[availabilityzones.png]: ../docs/images/availabilityzones.png "Availability Zones" {.gallerythumbnail}
[devicegraphs.png]: ../docs/images/devicegraphs.png "Device Graphs" {.gallerythumbnail}
[floatingips.png]: ../docs/images/floatingips.png "Floating IP" {.gallerythumbnail}
[hosts.png]: ../docs/images/hosts.png "Host" {.gallerythumbnail}
[hypervisors.png]: ../docs/images/hypervisors.png "Hypervisor" {.gallerythumbnail}
[images.png]: ../docs/images/images.png "Image" {.gallerythumbnail}
[impact_instance.png]: ../docs/images/impact_instance.png "Impact Instance" {.gallerythumbnail}
[impact_instance_with_floatingip.png]: ../docs/images/impact_instance_with_floatingip.png "Impact with FloatingIP" {.gallerythumbnail}
[impact_region.png]: ../docs/images/impact_region.png "Impact Region" {.gallerythumbnail}
[impact_tenant.png]: ../docs/images/impact_tenant.png "Impact" {.gallerythumbnail}
[instances.png]: ../docs/images/instances.png "Instance" {.gallerythumbnail}
[networks.png]: ../docs/images/networks.png "Network" {.gallerythumbnail}
[neutronagents.png]: ../docs/images/neutronagents.png "Neutron Agent" {.gallerythumbnail}
[novaapis.png]: ../docs/images/novaapis.png "Nova API" {.gallerythumbnail}
[novaservices.png]: ../docs/images/novaservices.png "Nova Service" {.gallerythumbnail}
[openstackcomponentview.png]: ../docs/images/openstackcomponentview.png "Component View" {.gallerythumbnail}
[ports.png]: ../docs/images/ports.png "Port" {.gallerythumbnail}
[regions.png]: ../docs/images/regions.png "Region" {.gallerythumbnail}
[routers.png]: ../docs/images/routers.png "Router" {.gallerythumbnail}
[subnets.png]: ../docs/images/subnets.png "Subnet" {.gallerythumbnail}
[tenants.png]: ../docs/images/tenants.png "Tenant" {.gallerythumbnail}
[vnics.png]: ../docs/images/vnics.png "vNIC" {.gallerythumbnail}
[cinderservices.png]: ../docs/images/cinderservices.png "Cinder Service" {.gallerythumbnail}
[volumes.png]: ../docs/images/volumes.png "Volume" {.gallerythumbnail}
[volsnapshots.png]: ../docs/images/volsnapshots.png "Volume Snapshot" {.gallerythumbnail}
