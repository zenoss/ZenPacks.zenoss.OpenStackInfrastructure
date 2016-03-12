Introduction
------------

Since Cinder can configure a variety of underlying block storage topologies,
which would be modeled using different ZenPacks, we provide a generic mechanism
for these zenpacks to provide a mapping between cinder components like volumes
and snapshots, and the underlying zenpack's components, such as LVM and Ceph
RBDs.

These mappings are many-to-many, to support a variety of implementation
strategies.

Throughout this file, the term "implementation" refers to components modeled
in a different zenpack, and "core" to those cinder components modeled
by OpenStackInfrastructure.


Integration Keys
----------------

The key function of a Cinder Implementation plugin is to provide a mapping
of cinder objects and the underlying "Implementation Components"
(that is, components within other zenpacks that correspond to configuration
that is done by a cinder volume driver)

This is accomplished by defining functions that take these components
as input and return opaque "integration key" values, such that when the two
keys match, that cinder component correspond to that implementation
component.

This mapping is many-to-many and can map any cinder component to any
component which implements the ICinderImplementationComponent
interface.

The integration key is a string of any format as long as the same value
can be generated on both sides (cinder and implementation) and is
appropriately unique to identify a specific component.

Plain text is generally preferred over a MD5 sum or other opaque value,
simply for ease of debugging, but any value is acceptable.

NOTE:  Integration keys must always be prefixed with the plugin name,
       followed by a ':'.  For example:

       "cinder.myblockstorage:10.0.0.1|storage|mystorage-e63ab524-736f-4dd9-a712-97228862d0ea"


Cinder Implementation Plugin
-----------------------------


You must also supply a cinder implementation adapter, for example, in a file
called openstack_cinder.py, in your zenpack:


from zope.interface import implements
from zope.event import notify

from Products.Zuul.catalog.events import IndexingEvent
from Products.Zuul.interfaces import ICatalogTool
from ZenPacks.zenoss.OpenStackInfrastructure.interfaces import \
    ICinderImplementationPlugin
from ZenPacks.zenoss.OpenStackInfrastructure.cinder_integration import \
    BaseCinderImplementationPlugin, split_list


class MyBlockStorageCinderImplementationPlugin(BaseCinderImplementationPlugin):
    implements(ICinderImplementationPlugin)

    def getVolumeIntegrationKeys(self, osi_volume):
        # osi_volume.id: volume-366fc7b1-4c11-4ae6-9ec2-d096df0194e0
        # this matches the volume name on implementation side
        return ['cinder.myblockstorage:volume|' + osi_volume.id]

    @classmethod
    def reindex_implementation_components(cls, dmd):
        results = ICatalogTool(dmd).search(
            ('ZenPacks.zenoss.myblockstorage.Volume.lVolume')
        )

        for brain in results:
            obj = brain.getObject()
            obj.index_object()
            notify(IndexingEvent(obj))


Make sure in OpenStackInfrastructure's meta.zcml has an entry for Cinder integration:
    <!-- OpenStack Integration features -->
    <provides feature="openstack_cinder_integration" />

Register your plugin in the zenpack's configure.zcml file as follows:

    <!-- OpenStack Cinder integration -->
    <configure zcml:condition="installed ZenPacks.zenoss.OpenStackInfrastructure.interfaces">
        <!-- Guard Against Older OSI that lacks Cinder -->
        <configure zcml:condition="have openstack_cinder_integration">
            <utility
                name="cinder.myblockstorage"
                factory=".openstack_cinder.MyBlockStorageCinderImplementationPlugin"
                provides="ZenPacks.zenoss.OpenStackInfrastructure.interfaces.ICinderImplementationPlugin"
                />
        </configure>
    </configure>


Note that the name specified must be of one of the two forms:
    * cinder volume driver name
    * cinder.<cinder volume backend name>

This same name must also be used as a prefix in all integration keys returned
by the plugin get*IntegrationKeys and component getCinderIntegrationKeys
methods.


Implementation Components
-------------------------

For components that implement an openstack cinder components:

Each component class to implement ICinderImplementationPlugin when the
OpenStackInfrastructure zenpack is installed:


from zope.interface import implements

try:
    from ZenPacks.zenoss.OpenStackInfrastructure.interfaces import \
        ICinderImplementationComponent
    from ZenPacks.zenoss.OpenStackInfrastructure.cinder_integration import \
        index_implementation_object, unindex_implementation_object
    openstack = True
except ImportError:
    openstack = False


class Volume(DeviceComponent):
    if openstack:
        implements(ICinderImplementationComponent)

    # The "integration key(s)" for this component must be made up of
    # a set of values that uniquely identify this resource and are
    # known to both this zenpack and the openstack zenpack.  They may
    # involve modeled properties, zProperties, and values from the cinder
    # configuration files on the openstack host.
    def getCinderIntegrationKeys(self):
        # normally Ceph volume name would not have UUID in it. But when
        # OpenStack creates a volume against a Ceph image, OpenStack
        # will generate a UUID for the volume and passes it on to Ceph,
        # and the volume in Ceph will have a UUID attach to it

        # self.name(): volume-366fc7b1-4c11-4ae6-9ec2-d096df0194e0

        return ['cinder.myblockstorage:volume|%s' % (self.name())]

    def index_object(self, idxs=None):
        super(Volume, self).index_object(idxs=idxs)
        if openstack:
            index_implementation_object(self)

    def unindex_object(self):
        super(Volume, self).unindex_object()
        if openstack:
            unindex_implementation_object(self)


Indexing Concerns
-----------------

The indexes used to map between cinder core and implementation components
are maintained in the usual way, with index_object. However, if the
integration key is derived from values stored elsewhere (so that the key should
change even though the component did not), you must ensure that index_object is
called explicitly.

This is handled for ini values on the core components automatically, but if your
plugin refers to other values which could change and are not either properties
of that component or ini values, you may find that the catalog is not updated
when it should be.

If this is unavoidable, it may be required to modify the OpenStackInfrastructure
zenpack to support your use case.


Impact Support
--------------

The impacts_by relationship from the implementation component to the core
component is provided automatically, but it is your responsibility to
provide the impacts relationship from the other zenpack into openstack.

To do this, your impact adapter should call the function 'get_cinder_components'
from ZenPacks.zenoss.OpenStackInfrastructure.cinder_integration.
