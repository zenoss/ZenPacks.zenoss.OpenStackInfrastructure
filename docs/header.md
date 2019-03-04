OpenStack (Provider View) ZenPack
=================================

This ZenPack provides monitoring of OpenStack from a service provider
perspective. In addition to the user-oriented components (instances, flavors, images),
the underlying OpenStack servers and software are monitored.

Features
--------

-   Monitors overall OpenStack state, including all tenants.
-   Monitors Nova, Neutron and Cinder health
-   Models and monitors Nova Services and components
-   Models and monitors Neutron Agents and components
-   Models and monitors Cinder Services and components
-   Impact and Root-Cause (Requires Zenoss Service Dynamics)

Support
-------

This is an Open Source ZenPack developed by Zenoss, Inc.  Enterprise support for
this ZenPack is available to commercial customers with an active subscription.

OpenStackInfrstructure 3.0.0 supports only Pike, Queens, and Rocky releases of OpenStack.
<br>OpenStack releases, prior to the Pike release, are not verified to
work with the OpenStackInfrastrucure 3.0.0 ZenPack.
<br>Although the 3.0.0 ZenPack will work with the older AMQP based Ceilometer integration, those versions of
Ceilometer are not supported by Zenoss.
