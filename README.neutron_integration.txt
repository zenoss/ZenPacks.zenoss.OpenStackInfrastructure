
Introduction
------------

Since Neutron, mostly through its ML2 plugin, can configure a variety of
underlying network topologies, which would be modeled using different
ZenPacks, we provide a generic mechanism for these zenpacks to provide
a mapping between neutron components like networks and ports and the underlying
zenpack's components, such as bridge groups and interfaces.

These mappings are many-to-many, to support a variety of implementation
strategies.

Throughout this file, the term "implementation" refers to components modeled
in a different zenpack, and "core" to those neutron components modeled
by OpenStackInfrastructure.


Integration Keys
----------------

The key function of an Neutron Implementation plugin is to provide a mapping
of neutron objects and the underlying "Implementation Components"
(that is, components within other zenpacks that correspond to configuration
that is done by a neutron core or ML2 mechanism driver)

This is accomplished by defining functions that take these components
as input and return opaque "integration key" values, such that when the two
keys match, that neutron component correspond to that implementation
component.

This mapping is many-to-many and can map any neutron component to any
component which implements the INeutronImplementationComponent
interface.

The integration key is a string of any format as long as the same value
can be generated on both sides (neutron and implementation) and is
appropriately unique to identify a specific component.

Plain text is generally preferred over a MD5 sum or other opaque value,
simply for ease of debugging, but any value is acceptable.

NOTE:  Integration keys must always be prefixed with the plugin name,
       followed by a ':'.  For example:

       "ml2.myswitch:10.0.0.1|network|mynetwork-e63ab524-736f-4dd9-a712-97228862d0ea"


Neutron Implementation Plugin
-----------------------------


You must also supply a neutron implementation adapter, for example, in a file called openstack_neutron.py, in your zenpack:


from zope.interface import implements

from Products.Zuul.interfaces import ICatalogTool
from ZenPacks.zenoss.OpenStackInfrastructure.interfaces import INeutronImplementationPlugin
from ZenPacks.zenoss.OpenStackInfrastructure.neutron_integration import BaseNeutronImplementationPlugin, split_list


class MySwitchNeutronImplementationPlugin(BaseNeutronImplementationPlugin):
    implements(INeutronImplementationPlugin)

    @classmethod
    def ini_required(cls):
        return [('plugins/ml2/ml2_conf.ini', 'ml2_myswitch', 'management_server_ips')]

    @classmethod
    def ini_process(cls, filename, section_name, option_name, value):
        # The management server IPs are specified as a comma-separated list.
        # we transform this to an actual list so that we can refer to it that
        # way elsewhere.
        if option_name == 'management_server_ips':
            return split_list(value)

        return value

    # So in this example, the IP address comes from an INI file, and the "netId"
    # on the neutron network is expected to match the "title" on the implementation zenpack's
    # Network component
    def getNetworkIntegrationKeys(self, network):
        ip_addresses = self.ini_get(('plugins/ml2/ml2_conf.ini', 'ml2_myswitch', 'management_server_ip'))
        keys = []

        # in this example, there can be multiple management servers, and the
        # same network is expected to appear on any or all of them.  So
        # we return multiple integration keys, one for each possible
        # server:

        for ip_address in ip_addresses:
            keyvalues = (
                ip_address,
                'network',
                self.netId,
            )
            keys.append('ml2.myswitch:' + |'.join(keyvalues))

        return keys

    @classmethod
    def reindex_implementation_components(cls, dmd):
        device_class = dmd.Devices.getOrganizer('/Devices/MySwitch')
        results = ICatalogTool(device_class).search(
            ('ZenPacks.zenoss.MySwitch.Network.Network',)
        )
        for brain in results:
            obj = brain.getObject()
            obj.index_object()


Register your plugin in the zenpack's configure.zcml file as follows:

    <configure zcml:condition="installed ZenPacks.zenoss.OpenStackInfrastructure">
        <utility
            name="ml2.myswitch"
            factory=".openstack_neutron.MySwitchNeutronImplementationPlugin"
            provides="ZenPacks.zenoss.OpenStackInfrastructure.interfaces.INeutronImplementationPlugin"
            />
    </configure>


Note that the name specified must be of one of the two forms:
    * neutron core plugin name
    * ml2.<neutron ml2 mechanism name>

This same name must also be used as a prefix in all integration keys returned
by the plugin get*IntegrationKeys and component getNeutronIntegrationKeys
methods.


Implementation Components
-------------------------

For components that implement an openstack neutron components:

Each component class to implement INeutronImplementationPlugin when the
OpenStackInfrastructure zenpack is installed:


try:
    from ZenPacks.zenoss.OpenStackInfrastructure.interfaces import INeutronImplementationComponent
    from ZenPacks.zenoss.OpenStackInfrastructure.neutron_integration import index_implementation_object, unindex_implementation_object
    openstack = True
except ImportError:
    openstack = False


class Network(DeviceComponent):
    if openstack:
        implements(INeutronImplementationComponent)

    # The "integration key(s)" for this component must be made up of
    # a set of values that uniquely identify this resource and are
    # known to both this zenpack and the openstack zenpack.  They may
    # involve modeled properties, zProperties, and values from the neutron
    # configuration files on the openstack host.
    def getNeutronIntegrationKeys(self):
        keyvalues = (
            self.device().zMyNetworkManagerIpAddress,
            'network',
            self.title
        )

        return ['ml2.myswitch' + '|'.join(keyvalues)]

    def index_object(self, idxs=None):
        super(Network, self).index_object(idxs=idxs)
        if openstack:
            index_implementation_object(self)

    def unindex_object(self):
        super(Network, self).unindex_object()
        if openstack:
            unindex_implementation_object(self)


Indexing Concerns
-----------------

The indexes used to map between neutron core and implementation components
are maintained in the usual way, with index_object.   However, if the
integration key is derived from values stored elsewhere (so that the key should
change even though the component did not), you must ensure that index_object is
called explicitly.

This is handled for ini values on the core components automatically, but if your
plugin refers to other values which could change and are not either properties
of that component or ini values, you may find that the catalog is not updated
when it should be.

If this is unavoidable, it may be required to modify the OpenStackInfrastructure
zenpack to support your use case.
