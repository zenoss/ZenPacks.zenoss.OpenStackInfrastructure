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

+-----------------------------------------------+-------------------------------------------+---------------------------------------------------------------+
| [![][regions.png]][regions.png]               | [![][tenants.png]][tenants.png]           | [![][availabilityzones.png]][availabilityzones.png]           |
|                                               |                                           |                                                               |
| Region                                        | Tenants                                   | Availability Zones                                            |
+-----------------------------------------------+-------------------------------------------+---------------------------------------------------------------+
| [![][devicegraphs.png]][devicegraphs.png]     |                                           | [![][openstackcomponentview.png]][openstackcomponentview.png] |
|                                               |                                           |                                                               |
| Device Graphs                                 |                                           | Component View                                                |
+-----------------------------------------------+-------------------------------------------+---------------------------------------------------------------+
| [![][hosts.png]][hosts.png]                   | [![][hypervisors.png]][hypervisors.png]   | [![][images.png]][images.png]                                 |
|                                               |                                           |                                                               |
| Hosts                                         | Hypervisors                               | Images                                                        |
+-----------------------------------------------+-------------------------------------------+---------------------------------------------------------------+
| [![][novaapis.png]][novaapis.png]             | [![][novaservices.png]][novaservices.png] | [![][neutronagents.png]][neutronagents.png]                   |
|                                               |                                           |                                                               |
| Nova APIs                                     | Nova Services                             | Neutron Agents                                                |
+-----------------------------------------------+-------------------------------------------+---------------------------------------------------------------+
| [![][instances.png]][instances.png]           | [![][vnics.png]][vnics.png]               |                                                               |
|                                               |                                           |                                                               |
| Instances                                     | vNICs                                     |                                                               |
+-----------------------------------------------+-------------------------------------------+---------------------------------------------------------------+
| [![][networks.png]][networks.png]             | [![][ports.png]][ports.png]               |                                                               |
|                                               |                                           |                                                               |
| Networks                                      | Ports                                     |                                                               |
+-----------------------------------------------+-------------------------------------------+---------------------------------------------------------------+
| [![][floatingips.png]][floatingips.png]       | [![][routers.png]][routers.png]           | [![][subnets.png]][subnets.png]                               |
|                                               |                                           |                                                               |
| Floating IPs                                  | Routers                                   | Subnets                                                       |
+-----------------------------------------------+-------------------------------------------+---------------------------------------------------------------+
| [![][cinderservices.png]][cinderservices.png] | [![][volumes.png]][volumes.png]           | [![][volsnapshots.png]][volsnapshots.png]                     |
|                                               |                                           |                                                               |
| Cinder Services                               | Volumes                                   | Volume Snapshots                                              |
+-----------------------------------------------+-------------------------------------------+---------------------------------------------------------------+


Prerequisites
-------------

- A supported OpenStack version (see below)
- Administrative credentials for your OpenStack environment
    - Username, password, keystone URL, Region
- SSH access and credentials to the Linux devices in your OpenStack environment
    (See [Post-ZenPack-Installation Notes](#post-zenpack-installation))


### Supported OpenStack Releases

* 2.3.x supports Mitaka
* 2.4.x supports Mitaka, Newton, and Ocata
* 3.0.0 supports Pike, Queens, Rocky, and Red Hat OpenStack Platform (RHOSP) version 13 and 14

Note: We denote Pike, Queens, and Rocky, RHOSP 13 and 14 as **Pike+**


Restricted Users
---------------------

Restricted (non-administrator) users can also model and monitor OpenStack
devices, with access to those devices consistent with that user's privileges.
In other words, you should expect reduced visibility for restricted users.

A restricted should expect to see:

* Fewer modeled components
* Reduced monitored metrics
* Absent events for missing components

In particular, restricted users can see diminished components and metrics for:

* Cinder Pools
* Cinder Services
* Cinder Volumes
* Hypervisors
* Neutron Agents
* Nova Services
* Tenants
* Any API item that requires administrator access

If you believe a user should have more access to data, it is your responsibility
to adjust the user's access level on OpenStack.

Organizational Elements
-------------------------------

The following organizational elements are discovered:

* Regions
* Availability Zones
* Tenants
* API Endpoints

The following virtual-machine elements are discovered:

* Nova Services (processes supporting nova servers)
* Instances (Servers)
* Hosts
* Hypervisors
* Images
* Flavors

The following network elements are discovered:

* Neutron Agents
* Networks
* Subnets
* Routers
* Ports
* Floating-Ips
* vNICs

The following block storage elements are discovered:

* Cinder Services (processes supporting block storage)
* Volumes
* Volume Snapshots
* Volume Types
* Storage Pools
* Cinder Quotas

### Metrics

The following component level metrics are collected:

#### Instances

* CPU Utilization (percent)
* Disk Requests (requests/sec)
* Disk IO Rate (bytes/sec)

#### vNICs

* Network Packet Rate (packets/sec)
* Network Throughput (bytes/sec)

#### Hosts

* Load Average (processes)
* CPU Utilization (percent)
* Free Memory (bytes)
* Free Swap (bytes)
* IO (sectors/sec)

#### Nova Services

* CPU Utilization (percent)
* Memory Utilization (bytes)
* Process Count (processes)

#### Neutron Agents

* CPU Utilization (percent)
* Memory Utilization (bytes)
* Process Count (processes)

#### Cinder Services

* CPU Utilization (percent)
* Memory Utilization (bytes)
* Process Count (processes)

#### Volumes

* Storage Utilization (percent)
* Operation Throughput (operations/sec)
* Merge Rate (merged/sec)
* Sector Throughput (sectors/sec)
* IO Operations (operations)
* IO Utilization (percent)
* Weighted IO Utilization (weighted percent)

#### Volume Snapshots

* Storage Utilization (percent)
* Operation Throughput (operations/sec)
* Merge Rate (merged/sec)
* Sector Throughput (sectors/sec)
* IO Operations (operations)
* IO Utilization (percent)
* Weighted IO Utilization (weighted percent)

The following device level metrics are collected:

#### Flavors

* Total (count)

#### Images

* Total (count)
* Total count per image state

#### Servers

* Total (count)
* Total count per server state

#### Queues

* Event (count)
* Performance (count)

#### Agents

* Total (count)
* Total count per agent type

#### Networks

* Total (count)
* Total count per network state

#### Routers

* Total (count)
* Total count per router state

#### Volumes

* Total (count)
* Total count per volume state

#### Volume Snapshots

* Total (count)
* Total count per volume snapshot state

#### Volume Pool

* Total (count)
* Total count per volume pool state

Installed Items
---------------
Once installed, the ZenPack installs the following properties and components.

### Daemons

The following daemons are installed:

+--------------------------------------+--------------------------------------+
| Type                                 | Name                                 |
+======================================+======================================+
| Modeler                              | zenmodeler                           |
+--------------------------------------+--------------------------------------+
| Performance Collector                | zencommand, zenpython, zenopenstack, |
|                                      | proxy-zenopenstack                   |
+--------------------------------------+--------------------------------------+

### Configuration Properties

- zOpenStackAuthUrl: The URL of the Identity endpoint.
- zOpenStackExtraHosts: The list of extra hosts that will be added to the
  system once OpenStack Infrastructure device is modeled.
- zOpenStackExtraApiEndpoints: A list of URLs to monitor for OpenStack
  APIs. Format is \<service type\>:\<full URL\> for each.
- zOpenStackHostDeviceClass: Used as a default device class for defined
  hosts in zOpenStackExtraHosts and zOpenStackNovaApiHosts properties.
  Default is /Server/SSH/Linux/NovaHost.
- zOpenStackNovaApiHosts: The list of hosts upon which nova-api runs. This is
  required when the IP address in the nova API URL does not match any known host.
- zOpenStackCinderApiHosts: The list of hosts upon which cinder-api runs.
  This is required when the IP address in the cinder API URL does not
  match any known host.
- zOpenStackHostMapToId: A list of \<name\>=\<id\>,
  used to force a host referred to by OpenStack with the given name to be
  represented in Zenoss as a host component with the given ID. (this is
  not commonly used)
- zOpenStackHostMapSame: A list of \<name1\>=\<name2\>,
  used to inform the modeler that the same host may be referred to with an
  alternate name by some part of OpenStack. (this is not commonly used)
- zOpenStackNeutronConfigDir: Path to directory that contains Neutron configuration files. Default is /etc/neutron.
- zOpenStackProjectId: Corresponds to tenant name, project to work on.
- zOpenStackRegionName: The name of the OpenStack Region to use. Regions are
  autonomous OpenStack clouds joined together through shared Keystone identity
  server and managed through a common interface.
- zOpenStackRunNovaManageInContainer, zOpenStackRunVirshQemuInContainer, zOpenStackRunNeutronCommonInContainer:
  Used when OpenStack processes are running inside of docker containers. Provide
  the container names (or a pattern to match them) here, or leave blank in a
  non-containerized OpenStack environment.
- zOpenStackHostLocalDomain: When OpenStack hosts report names ending in .localdomain,
  replace domain with this value.
- zOpenStackAMQPUsername: Username for Ceilometer AMQP integration.
- zOpenStackAMQPPassword: Password for Ceilometer AMQP integration.
- zOpenStackProcessEventTypes: List of OpenStack event types to pass to Zenoss event system.
  (Other event types may be processed for model changes, but will not be stored as events in Zenoss)
- zOpenStackIncrementalShortLivedSeconds: Incremental Modeling - Delay component
    creation this period of time until no deletions are detected. (seconds)
- zOpenStackIncrementalBlackListSeconds: Incremental Modeling - Once a component
  is deleted, wait this interval between attempts to remodel same component to
  avoid flapping. (seconds)
- zOpenStackIncrementalConsolidateSeconds: Incremental Modeling - Wait this
    amount of time to aggregate components' properties before updating a
    component map. Ignored by deletions. (seconds)
- zOpenStackUserDomainName: Domain name containing opentstack user for authorization scope.
- zOpenStackProjectDomainName: Domain name containing opentstack project for authorization scope.

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
- ApiEndpointStatusDataSource: Checks that API endpoints are available.
- CinderServiceStatusDataSource: Checks the status of Cinder services via the Cinder API.
- EventsAMQPDataSource: Stores events received from OpenStack Ceilometer via AMQP.
- NeutronAgentStatusDataSource: Checks the status of Neutron agents via the Neutron API.
- NovaServiceStatusDataSource: Checks the status of Nova services via the Nova API.
- PerfAMQPDataSource: Stores performance data received from OpenStack Ceilometer.
- QueueSizeDataSource: Checks the number of unprocessed messages in Ceilometer AMQP queues.

#### Notes

-   As of the Pike+ (Late 2017) OpenStack release, the dispatcher mechanism
    previously used by this zenpack is no longer supported by Ceilometer. Because
    of this, the "heartbeat" mechanism that was previously used to verify
    connectivity between Ceilometer and Zenoss is no longer possible, and
    /Status/Heartbeat events will not be created if Zenoss stops receiving data
    from Ceilometer.

    Connectivity problems between Ceilometer and Zenoss will still be reported in
    the Ceilometer agent-notification.log file on the OpenStack hosts.

 -   All `OpenStack Ceilometer Perf AMQP` datasources' *cycletime* parameter
     will not work in Pike+ . Cycletime must be regulated in
     OpenStack itself. The *cycletime* setting is still present for backward
     compatibility with Ocata and prior versions.

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


Zenpack Installation
-----------------------

### Zenoss Configuration Steps - First-Time Installation

If you are installing the ZenPack for the first time, install as per
usual ZenPack installation.

### Zenoss Configuration Steps - ZenPack Upgrades

If this is the first time you are upgrading to 3.0.0+ from a version of the
zenpack 2.4.0 or earlier, there are no special steps required,
nor any changes required on the OpenStack side.

If upgrading to 2.4.0, from a prior version, please consult the old
documentation, *old_ceilometer.md*, located in the docs folder of this
[git repo](https://github.com/zenoss/ZenPacks.zenoss.OpenStackInfrastructure/tree/master/docs).


### Post-ZenPack Installation

*   Make sure to restart the Zproxy service to see the new UI elements
    *User Domain Name* and *Project Domain Name* in the *Add OpenStack Endpoint*
    Dialog.

*   Zenoss doesn't assign IP addresses for services proxy-zenopenstack and
    RabbitMQ-Ceilometer, you must assign the correct collectors' host to those
    services. Then you must restart those services in ControlCenter.

    Once [CC-4195](https://jira.zenoss.com/browse/CC-4195) is completed,
    this assignment will automatic. Note, this step must be done before
    configuring Ceilometer on OpenStack.

*   Make sure you restart ceilometer-notification service whenever you change
    `pipeline.yaml` or `event_pipeline.yaml`.

*   For Queens and Rocky devices, make sure to restart ceilometer-polling service
    if you have updated `/etc/ceilometer/polling.yaml`

*   Once the zenpack is installed, provide SSH credentials to the Linux devices in your OpenStack environment before adding any devices.
        - Configure the zCommandUsername/zCommandPassword/zKeyPath properties on the /Devices/Server/SSH/Linux/NovaHost device class.
        - If your OpenStack nodes are already managed under Zenoss, move them into /Devices/Server/SSH/Linux/NovaHost


Device Setup
-----------------------------

### Device Setup via UI

Once the OpenStack ZenPack is installed and you can begin monitoring by
going to the infrastructure screen and clicking the normal button for
adding devices. You'll find a new option labeled,
"Add OpenStack Endpoint (Infrastructure)."

Choose that option and you'll be presented with a dialog asking for the
following inputs.

* Device To Create - non-empty, non-ip, non-dns, unique name to use for this
  device in Zenoss. ''See note below''.
* Auth URL - A keystone URL.  For Keystone's v3 API, it should look like
  `http://\<hostname\>:5000/v3/`.
  <br>For Keystone's v2 API, it should look like `http://\<hostname\>:5000/v2.0/`.
  To have the ZenPack choose the newest supported API version, leave the path
  off, like `http://\<hostname\>:5000/` (sets zOpenStackAuthUrl).
* Username: Enter your OS_USERNAME (sets zCommandUsername).
* Password: Enter your OS_PASSWORD (sets zCommandPassword).
* User Domain Name: Enter the user domain name per OS_USER_DOMAIN_NAME
  (sets zOpenStackUserDomainName).
* Project Domain Name: Enter the project domain name per OS_PROJECT_DOMAIN_NAME
  (sets zOpenStackDomainName).
* Region Name - choose the correct region from the drop-down. You may only
  choose one, so each region you wish to manage must be registered as a separate
  endpoint in Zenoss (sets zOpenStackRegionName).

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

        /Devices/OpenStack/Infrastructure loader='openstackinfrastructure',\
            loader_arg_keys=['deviceName', 'username', 'api_key', 'project_id, 'user_domain_name', 'project_domain_name', 'auth_url', 'region_name', 'collector']
        <devicename> username='<username>', api_key='<password>', project_id='<tenant ID>', user_domain_name='default',  \
            project_domain_name='default', auth_url='http://<ip address>:5000/v2.0/', region_name='RegionOne'

        /Devices/Server/SSH/Linux/NovaHost zCommandUsername='myusername', zCommandPassword='mypassword'


* As mentioned before, zCommandUsername and zCommandPassword properties must be set
  for /Devices/Server/SSH/Linux/NovaHost devices (and vNICs) to be correctly
  modeled.

### Host Identification

The OpenStack APIs do not contain an authoritative list of hosts with unique
IDs. Instead, various APIs show hosts by name or IP. There zenpack does
its best to identify IPs and names that refer to the same host, and represent
them as a single host component. In some cases, though, it can't tell,
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
    problems for Zenoss, because it is not possible to create a device
    in Zenoss with such a name, as they all resolve to 127.0.0.1, rather than
    their actual IP.

    The default value of zOpenStackHostLocalDomain is a blank string, meaning
    that the '.localdomain' suffix will be stripped from host names, and
    devices will be created in Zenoss with those shortened names.  If those
    names do not resolve in DNS, they will be created without IPs, and
    will not be modeled.  You would need to manually set their management IPs
    so that they can be modeled.

    Alternatively, if you already have these hostnames in dns, but just with
    a different domain name than ".localdomain", you may specify this domain
    name here, and it will be substituted for localdomain, and the devices
    will model automatically, based on the IPs returned from DNS.

### Modeling Containerized Environments

If the target OpenStack environment runs processes inside of docker containers,
it is necessary to configure several zProperties before modeling will
succeed.

* zOpenStackRunNovaManageInContainer:  Container to run "nova-manage" in
* zOpenStackRunVirshQemuInContainer: Container to run "virsh" in
* zOpenStackRunNeutronCommonInContainer: Container to access neutron configuration files in.

These should be set to container names or substrings of the container names.
These can be set on the /Server/SSH/Linux/NovaHost device class or
specific devices within it, as necessary.

NOTE:  These zProperties must be set on the Linux devices, not the
OpenStack (/OpenStack/Infrastructure) devices.

OpenStack Configuration
-----------------------

Before event and performance data can be collected, the following
steps must be  performed.

### OpenStack Ceilometer Configuration (Pike+)

Ceilometer must be configured to send data to each Zenoss collector.
This ZenPack supports configuration of multiple Zenoss instances via Ceilometer.
Each collector must direct network access to each OpenStack instance it monitors.

First you must assign IP's to the zenopenstack service:

    serviced service assign-ip proxy-zenopenstack
    serviced service start /zenopenstack /proxy-zenopenstack

Once you do that, you will find 2 URLs on the device overview page: Once for
events and one for sample (metrics). For example:

For Zenoss instance 10.0.0.10

    Samples: https://10.0.0.10:8342/ceilometer/v1/samples/myopenstack?verify_ssl=False
    Events:  https://10.0.0.10:8342/ceilometer/v1/events/myopenstack?verify_ssl=False

For Zenoss instance 10.0.0.12

    Samples: https://10.0.0.12:8342/ceilometer/v1/samples/myopenstack?verify_ssl=False
    Events:  https://10.0.0.12:8342/ceilometer/v1/events/myopenstack?verify_ssl=False

#### Manual Configuration

For manual configuration, you must modify every Ceilometer node as follows:

* Add Zenoss specific extensions to the Ceilometer event definitions:

  Edit `/etc/ceilometer/event_definitions.yaml` and add the contents of
  [zenoss_additions.yaml](https://raw.githubusercontent.com/zenoss/ZenPacks.zenoss.OpenStackInfrastructure/develop/event_definitions/zenoss_additions.yaml)
  to the bottom of the file.

*   The /etc/ceilometer/event_pipeline.yaml file contains one sink, named
    `event_sink`. In its publishers section, add the event URL from above:

    For example:

        ---
        sources:
            - name: event_source
              events:
                  - "*"
              sinks:
                  - event_sink
        sinks:
            - name: event_sink
              transformers:
              triggers:
              publishers:
                  - https://10.0.0.10:8342/ceilometer/v1/events/myopenstack?verify_ssl=False
                  - https://10.0.0.12:8342/ceilometer/v1/events/myopenstack?verify_ssl=False
                  - <some_other_publisher>


*   The /etc/ceilometer/pipeline.yaml add the samples URL to the publish
    sections for the three sinks, cpu_sink, disk_sink, and network_sink:

    For example:

        ---
        sources:
            - name: meter_source
              meters:
                  - "*"
              sinks:
                  - meter_sink
             ... etc ...
        sinks:
            - name: meter_sink
              transformers:
              publishers:
                  - https://10.0.0.10:8342/ceilometer/v1/samples/myopenstack?verify_ssl=False
                  - https://10.0.0.12:8342/ceilometer/v1/samples/myopenstack?verify_ssl=False
                  - <some_other_publisher>
            - name: cpu_sink
              transformers:
                  - name: "rate_of_change"
                    parameters:
                        target:
                            name: "cpu_util"
                            unit: "%"
                            type: "gauge"
                            max: 100
                            scale: "100.0 / (10**9 * (resource_metadata.cpu_number or 1))"
              publishers:
                  - https://10.0.0.10:8342/ceilometer/v1/samples/myopenstack?verify_ssl=False
                  - https://10.0.0.12:8342/ceilometer/v1/samples/myopenstack?verify_ssl=False
                  - <some_other_publisher>
            - name: disk_sink
              transformers:
                  - name: "rate_of_change"
                    parameters:
                        source:
                            map_from:
                                name: "(disk\\.device|disk)\\.(read|write)\\.(bytes|requests)"
                                unit: "(B|request)"
                        target:
                            map_to:
                                name: "\\1.\\2.\\3.rate"
                                unit: "\\1/s"
                            type: "gauge"
              publishers:
                  - https://10.0.0.10:8342/ceilometer/v1/samples/myopenstack?verify_ssl=False
                  - https://10.0.0.12:8342/ceilometer/v1/samples/myopenstack?verify_ssl=False
                  - <some_other_publisher>
            - name: network_sink
              transformers:
                  - name: "rate_of_change"
                    parameters:
                        source:
                           map_from:
                               name: "network\\.(incoming|outgoing)\\.(bytes|packets)"
                               unit: "(B|packet)"
                        target:
                            map_to:
                                name: "network.\\1.\\2.rate"
                                unit: "\\1/s"
                            type: "gauge"
              publishers:
                  - https://10.0.0.10:8342/ceilometer/v1/samples/myopenstack?verify_ssl=False
                  - https://10.0.0.12:8342/ceilometer/v1/samples/myopenstack?verify_ssl=False
                  - <some_other_publisher>

* Make sure you restart ceilometer-notification service whenever you change
  `pipeline.yaml` or `event_pipeline.yaml`.

#### RHOSP Overcloud Configuration from Undercloud (Director)

*   When configuring Overcloud using templates, you need to add the
    following to your environment template:

            ManagePipeline: true
            PipelinePublishers:
              - https://<zenoss_ip>:8342/ceilometer/v1/samples/<zenoss_devicename>?verify_ssl=False
              - <other_pipeline_publishers>
            ManageEventPipeline: true
            EventPipelinePublishers:
              - https://<zenoss_ip>:8342/ceilometer/v1/events/<zenoss_devicename>?verify_ssl=False
              - <other_event_pipeline_publishers>

    For example:

            ManagePipeline: true
            PipelinePublishers:
              - https://10.0.0.10:8342/ceilometer/v1/samples/myopenstack?verify_ssl=False
              - https://10.0.0.12:8342/ceilometer/v1/samples/myopenstack?verify_ssl=False
            ManageEventPipeline: true
            EventPipelinePublishers:
              - https://10.0.0.10:8342/ceilometer/v1/events/myopenstack?verify_ssl=False
              - https://10.0.0.12:8342/ceilometer/v1/events/myopenstack?verify_ssl=False

*   This template must be ***rendered*** into your templates before you initiate a deployment from
    Undercloud.<br>
    For more information on RHOSP template management, see RedHat's
    [Including Environment Files in Overcloud Creation](https://access.redhat.com/documentation/en-us/red_hat_openstack_platform/13/html-single/advanced_overcloud_customization/index#sect-Including_Environment_Files_in_Overcloud_Creation).

*   After deployment is complete, go to the undercloud, SSH into controller and go
    to `/etc/ceilometer` in ceilometer_agent_notification container to check if
    `pipeline.yaml` and `event_pipeline.yaml` file is updated:

            ssh heat-admin@<controller ip>
            sudo su -
            sudo docker exec --user 0 -it ceilometer_agent_notification /bin/bash
            # Ensure your configuration had the right publishers

#### VM State Changes

By default, instance state changes will be captured by Zenoss when
certain events occur, for example, when an instance is shut down, the
state change to SHUTDOWN will be reflected in Zenoss.

However, certain state changes that don't correspond to another defined
event may not be picked up until the next time Zenoss models the
environment.

If you would like to reduce the likelihood of this occurring, you can
configure OpenStack Nova to send an event (through Ceilometer) to Zenoss
whenever any VM state change occurs by adding the following to
/etc/nova/nova.conf on all Nova hosts:

      [notifications]
      notify_on_state_change=vm_and_task_state

      ...

      [oslo_messaging_notifications]
      driver = messagingv2

Save /etc/nova/nova.conf and restart nova services.

Note that notify_on_state_change will cause increased event load,
both on OpenStack and Zenoss, and additional processing within the event
transforms in Zenoss to keep the model consistent. Since most instance
changes will still be caught without this option enabled, it is
recommended to leave notify_on_state_change disabled if your
OpenStack environment is very large.


#### Network Events

The OpenStack Infrastructure ZP pulls neutron events for Networks and Routers. However,
if Neutron is not configured properly to send those events, they cannot be retrieved.
If you are missing events, checks your OpenStack environment's
/etc/neutron/neutron.conf.

It should have the following for traditional deployments:

```
[oslo_messaging_notifications]
driver = messagingv2
topics = notifications
```

#### Notes:

*   Events exposed by Ceilometer are listed in zOpenStackProcessEventTypes.
    By default, this is set to the single *compute.instance.create.error* .

*   Proxy warnings in [ZPS-4689](#known-issues) may be displayed during the
    upgrade to 3.0.0 if you have multiple collectors. These can be safely
    ignored.

*   The Instance metrics for *Disk IO Rate* are deprecated in OpenStack version
    Queens and later. Collection for those metrics will be missing.
    Future OpenStack releases will remove these metrics and graphs completely.

    In the meantime, if you still require these metrics, you can edit the
    OpenStack Ceilometer configuration /etc/ceilometer/polling.yaml and add the
    following to the *meters* section:

            - disk.read.bytes
            - disk.read.requests
            - disk.write.bytes
            - disk.write.requests

    - Ensure the resulting YAML syntax is valid restart the ceilometer-polling service

    Finally note that these metrics ARE deprecated and will be removed in
    future releases of OpenStack itself.

    Note: **There is no known template configuration for this for RHOSP
          templates at this time and are unsupported.**

*   Make sure you restart ceilometer-notification service whenever you change
    `pipeline.yaml` or `event_pipeline.yaml`.

*   For Queens and Rocky devices, make sure to restart ceilometer-polling service
    if you have updated `/etc/ceilometer/polling.yaml`

*   The RabbitMQ-Ceilometer service

    Version 2.4.0 of this zenpack introduces a new service, `RabbitMQ-Ceilometer`.
    This is a dedicated instance of RabbitMQ on each collector which is used solely
    for integration with Ceilometer, rather than using the standard `RabbitMQ`
    service that is used by Zenoss itself. This better distributes any load as
    well as providing better support for distributed collector scenarios where the
    target OpenStack environment might not have network access to the central
    Zenoss servers.

*   Zenoss collectors need direct access to the NovaHost devices in order to
    model them. In some setups like RHOSP's overcloud, where direct
    access to the overcloud network is not accessible by default, this can be a
    challenge. Discussion of how to achieve connectivity to overcloud is
    out of scope.


Zenoss Analytics
----------------

This ZenPack provides additional support for Zenoss Analytics. Perform
the following steps to install extra reporting resources into Zenoss
Analytics after installing the ZenPack.

1.  Copy vsphere-analytics.zip from
    `$ZENHOME/ZenPacks/ZenPacks.zenoss.OpenStackInfrastructure*/ZenPacks/zenoss/OpenStackInfrastructure/analytics/`
    on your Zenoss server.
2.  Navigate to Zenoss Analytics in your browser.
3.  Login as superuser.
4.  Remove any existing *OpenStackInfrastructure ZenPack* folder.
    a.  Choose *Repository* from the *View* menu at the top of the page.
    #.  Expand *Public* in the list of folders.
    #.  Right-click on *OpenStackInfrastructure ZenPack* folder and choose *Delete*.
    #.  Confirm deletion by clicking *OK*.
5.  Add the new *OpenStackInfrastructure ZenPack* folder.
    a.  Choose *Server Settings* from the ''Manage' menu at the top of
        the page.
    #.  Choose *Import* in the left page.
    #.  Remove checks from all check boxes.
    #.  Click *Choose File* to import a data file.
    #.  Choose the OpenStackInfrastructure-analytics.zip file copied from your Zenoss
        server.
    #.  Click *Import*.

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

+-------------------------------------------------+---------------------------------------------------------------------------------+
| [![][impact_instance.png]][impact_instance.png] | [![][impact_ports.png]][impact_ports.png]                                       |
|                                                 |                                                                                 |
| Impact (Instance)                               | Impact (Network)                                                                |
+-------------------------------------------------+---------------------------------------------------------------------------------+
| [![][impact_region.png]][impact_region.png]     | [![][impact_tenant.png]][impact_tenant.png]                                     |
|                                                 |                                                                                 |
| Impact (Region)                                 | Impact (Tenant)                                                                 |
+-------------------------------------------------+---------------------------------------------------------------------------------+


Integration with other ZenPacks
-------------------------------

In some cases, the underlying network or storage technology is monitored
by a different zenpack.  The OpenStackInfrastructure zenpack is able
to integrate with the following ZenPacks to provide component-level linkage
and impact model integration:

* Neutron OpenvSwitch ml2 plugin <-> [OpenvSwitch](https://www.zenoss.com/product/zenpacks/openvswitch) ZenPack
* Neutron APIC ml2 plugin <-> [Cisco APIC](https://www.zenoss.com/product/zenpacks/cisco-apic) ZenPack
* Neutron NSX ml2 plugin <-> [VMWare NSX](https://www.zenoss.com/product/zenpacks/vmware-nsx) ZenPack
* Cinder LVM  logical volumes <-> [Linux Monitor](https://www.zenoss.com/product/zenpacks/linux-monitor) ZenPack (>= 2.0.0)
* Ceph RBD volumes <-> [Ceph](https://www.zenoss.com/product/zenpacks/ceph) ZenPack

Known Issues
------------

-   [ZEN-17905](https://jira.zenoss.com/browse/ZEN-17905): Nova APIs component:
    Grey icons for Enabled and State after model/monitor.

    *   OpenStack nova service API does not provide information about Nova-API,
        so its status is, in fact, unknown.

-   [ZPS-1762](https://jira.zenoss.com/browse/ZPS-1762): When using OpenvSwitch
     integration, the Linux devices must be added to the system first (normally
     through automatic discovery by the OpenStackInfrastructure ZenPack) before the
     corresponding OpenvSwitch devices are registered.  This is because the two
     devices use the same management IP address, and a special exclusion is in
     place for OpenvSwitch devices, allowing them to be added after the Linux
     device, but not the other way around.

-   [ZPS-2004](https://jira.zenoss.com/browse/ZPS-2004): When adding an OSI
    device, if the same host is already added as a generic device (such as
    /SSH/Linux), the host device's device class will be changed, and an error
    generated, preventing modeling.  As a workaround, remove the Linux device
    before adding the OSI device.

-   [ZPS-4742](https://jira.zenoss.com/browse/ZPS-4742): Networking functions
    through SR-IOV and OVS-DPDK used in NFV like setups are not supported.
    Ceilometer is not able to collect monitoring data for these interfaces and
    hence Zenoss doesn't have any insight into these interfaces.
    This is because legacy Ceilometer only supports traditional OpenvSwitch
    networking, where a TAP interface is created through libvirt.

-   [ZPS-5468](https://jira.zenoss.com/browse/ZPS-5468): Newly deployed
    RabbitMQ-Ceilometer service can fail to start, with an error
    `badmatch,{error,{no_such_vhost,<<"/">>}}`. When this occurs, all health
    checks for the service will fail.

    If this error is encountered, the simplest fix seems to be to
    attach to the affected container, then run:

            rm -rf /var/lib/rabbitmq/mnesia*/rabbit@rbt-ceil0 

    and restart the service.


-   [ZPS-4689](https://jira.zenoss.com/browse/ZPS-4689): During upgrades you can
    see an error like:

            ERRO[0000] Could not update proxy

    You can safely ignore this error, which should stop after the upgrade is
    completed.



Changes
-------

3.0.0

- Add support for Keystone Domains (ZPS-3850)
  As of version 3.0.0 support for domains was added. Before the only domain supported
  was the default domain. To use domain specify the domain of your user in the
  zOpenStackUserDomainName property and the domain of your chosen project in
  zOpenStackProjectDomainName. The domain does not limit the components modeled. If
  the user has access to the resource it will be modeled.
- Add support for Pike, Rocky, Queens, RHOSP 13-14 versions of OpenStack
- Add support for multiple Zenoss instances (ZPS-1598)
- Add support for  restricted (non-administrator) users limited modeling ability (ZPS-3851)
- Add support for  restricted (non-administrator) users limited monitoring ability (ZPS-5043)
- Exclude erroneous 'hostgroup' host components (ZPS-4914)
- Fix KeyError in PerfAMQPDataSource vNIC discovery (ZPS-4661)
- Fix vNIC detection in zenopenstack (ZPS-5232)
- Guard against missing tenant quota. (ZPS-4627)
- Refactor Ceilometer introducing zenopenstack service to simplify collection
- Allow temporary legacy metrics for 'Disk IO Rate' and 'Disk Requests' (ZPS-5205)
- The HeartBeat datasource was removed as heartbeats are no longer supported by OpenStack (ZPS-1984)

2.4.2

- Avoid nameconfict for proxy devices and be more flexible in linking to existing devices when appropriate (ZPS-3991)
- Prevent modeling invalid host components for Ceph storage backend and API endpoints (ZPS-3751, ZPS-3971, ZPS-4183)
- When mapping hostnames, treat all host references in case-insensitive manner (ZPS-3989)
- Fix hostfqdn modeler plugin for systems where the 'dnsdomainname' command is not available (ZPS-4083)
- expected_ceilometer_heartbeats includes additional possible names for a host, based on hostmap, proxy device, and the host's local 'hostname' (ZPS-4082)
- Fix for "OpenStack Component View" option missing in left-hand nav (ZPS-3927)
- Corrected URL escaping in modeler plugin to avoid receiving 400 error when a proxy is in front of nova-api services (ZPS-3894)
- Tested with Zenoss Resource Manager 6.2.0, Zenoss Resource Manager 5.3.3 and Service Impact 5.3.1

2.4.1

- Disallow spaces in device IDs in the 'Add OpenStack Endpoint' dialog (ZPS-2583)
- Remove certain warnings related to port update events (ZPS-2606)
- Eliminate warnings when running tests under 6.x (ZPS-2574)
- Support for self-signed certificates which include an IP address as a subjectAltName (ZPS-2056)
- Fix situation where certain errors are reported as TimeoutError instead of the actual error message (ZPS-2039)
- Fix for errors when modeling when the hosts already exist in a different device class (ZPS-2004)

2.4.0

- Added support for Newton and Ocata
- Added support for Keystone v3 authentication
- Model API endpoints (currently only the public keystone API endpoint).
  Allow user to specify additional ones via zOpenStackExtraApiEndpoints.
  Supported API services are included in the provided ApiEndpoint monitoring
  template.
- Removed zOpenStackCeilometerUrl zProperty, which was unused
- Added descriptions for OpenStack configuration properties (ZPS-1590)
- Tested with Zenoss Resource Manager 5.2.6, Zenoss Resource Manager 4.2.5 RPS 743 and Service Impact 5.1.5

2.3.3
- Fix error in modeler when neutron agent extension is not available (ZPS-1243)
- Fix certain problems modeling OpenStack environments where hosts have .localdomain names (ZPS-1244)

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



[impact.png]: ../docs/images/impact.png "Impact Diagram"

[availabilityzones.png]: ../docs/images/availabilityzones.png "Availability Zones" {.gallerythumbnail}
[devicegraphs.png]: ../docs/images/devicegraphs.png "Device Graphs" {.gallerythumbnail}
[floatingips.png]: ../docs/images/floatingips.png "Floating IP" {.gallerythumbnail}
[hosts.png]: ../docs/images/hosts.png "Host" {.gallerythumbnail}
[hypervisors.png]: ../docs/images/hypervisors.png "Hypervisor" {.gallerythumbnail}
[images.png]: ../docs/images/images.png "Image" {.gallerythumbnail}
[impact_instance.png]: ../docs/images/impact_instance.png "Impact Instance" {.gallerythumbnail}
[impact_ports.png]: ../docs/images/impact_ports.png "Impact Network Ports" {.gallerythumbnail}
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
