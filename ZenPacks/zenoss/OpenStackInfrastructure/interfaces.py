##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from zope.component.interfaces import Interface


class INeutronImplementationPlugin(Interface):
    """
    Neutron Implementation Plugin.  To be implemented by zenpacks which support
    the backend device for a specfic ML2 mechanism.  Given access to neutron
    configuration and modeled objects, this plugin maps the neutron components
    from the OpenStackInfrastructure zenpack to underlying "implementation"
    components within the device-specific zenpack.
    """

    def ini_required(cls):
        """
        Return a list of tuples describing the values to collect from the neutron
        configuration files, in the format:
            [
                (filename, section_name, option_name),
                ...
            ]

        Filenames must be relative to the neutron configuration base directory
        (/etc/neutron by default)

        If the value can not be found (file not found, or option not found within
        the file), an event will be raised.
        """

    def ini_optional(cls):
        """
        Return a list of tuples describing the values to collect from the neutron
        configuration files, in the format:
            [
                (filename, section_name, option_name),
                ...
            ]

        Filenames must be relative to the neutron configuration base directory
        (/etc/neutron by default)
        """

    def ini_process(cls, filename, section_name, option_name, value):
        """
        Post-process the collected values from the ini file.  Default behavior
        should be to return the value unmodified, but can be used to convert
        strings into lists, for multi-valued parameters, for example.
        """

    def reindex_implementation_components(cls, dmd):
        """
        Implementation should iterate over all objects in the classes that
        implement the INeutronImplementationComponent interface for this
        plugin and cause them to index themselves in the integration catalog.

        For properly implemented objects, this should simply be calling
        index_object upon them.

        This method will be used to initially populate the catalog, during
        OpenStackInfrastructure ZenPack installation (when the zenpack
        providing this plugin has already been installed and modeled
        the implementation components)
        """

    """
    The functions below must, given a core object, return one or more
    integration keys.  An integration key is a string of any format as
    long as the same value can be generated on both sides (neutron and
    implementation) and is sufficient to identify corresponding components.

    For guidelines and an example, see "README.neutron_integration.txt"

    Note: For the functions below, if you need information which was collected
    from the .ini files, it may be accessed by calling the ini_get
    method on the openstack objects.
    """

    def getTenantIntegrationKeys(self, tenant):
        """
        Returns a list of one or more integration keys for
        the supplied openstack (keystone) tenant/project.
        """

    def getPortIntegrationKeys(self, port):
        """
        Returns a list of one or more integration keys for
        the supplied neutron port.
        """

    def getNetworkIntegrationKeys(self, network):
        """
        Returns a list of one or more integration keys for
        the supplied neutron network (non-external).
        """

    def getExternalNetworkIntegrationKeys(self, network):
        """
        Returns a list of one or more integration keys for
        the supplied neutron network (external).
        """

    def getSubnetIntegrationKeys(self, subnet):
        """
        Returns a list of one or more integration keys for
        the supplied neutron subnet.
        """

    def getRouterIntegrationKeys(self, router):
        """
        Returns a list of one or more integration keys for
        the supplied neutron router.
        """

    def getFloatingIpIntegrationKeys(self, floatingip):
        """
        Returns a list of one or more integration keys for
        the supplied neutron floatingip.
        """


class INeutronImplementationComponent(Interface):

    def getNeutronIntegrationKeys(self):
        """
        Returns a list of one or more integration keys for this component.

        This key must match one of the keys defined above, if this
        component is the implementation backing one (or more) of the neutron
        objects.
        """

    """
    Objects that implement this interface must also invoke
    the "index_implementation_object" and "unindex_implementation_object"
    functions provided in ZenPacks.zenoss.OpenStackInfrastructure.neutron_integration
    from their index_object and unindex_object methods, respectively.

    An example may be found in "README.neutron_integration.txt"
    """
