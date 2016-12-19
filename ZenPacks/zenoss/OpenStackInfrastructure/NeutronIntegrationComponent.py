##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.neutron_integration')

import zope.component


from Products.Zuul.interfaces import ICatalogTool

from ZenPacks.zenoss.OpenStackInfrastructure.catalogs import (
    get_neutron_implementation_catalog,
    get_neutron_core_catalog
)

from ZenPacks.zenoss.OpenStackInfrastructure.interfaces import (
    INeutronImplementationPlugin
)


def all_core_components(dmd):
    device_class = dmd.Devices.getOrganizer('/Devices/OpenStack/Infrastructure')
    results = ICatalogTool(device_class).search(
        ('ZenPacks.zenoss.OpenStackInfrastructure.Tenant.Tenant',
         'ZenPacks.zenoss.OpenStackInfrastructure.Port.Port',
         'ZenPacks.zenoss.OpenStackInfrastructure.Network.Network',
         'ZenPacks.zenoss.OpenStackInfrastructure.Subnet.Subnet',
         'ZenPacks.zenoss.OpenStackInfrastructure.Router.Router',
         'ZenPacks.zenoss.OpenStackInfrastructure.FloatingIp.FloatingIp',
         )
    )
    for brain in results:
        try:
            yield brain.getObject()
        except Exception:
            # ignore a stale entry
            pass


class NeutronIntegrationComponent(object):

    """Mixin for model classes that have Neutron integrations."""

    def getNeutronIntegrationKeys(self):
        methodname = {
            'OpenStackInfrastructureTenant':     'getTenantIntegrationKeys',
            'OpenStackInfrastructurePort':       'getPortIntegrationKeys',
            'OpenStackInfrastructureNetwork':    'getNetworkIntegrationKeys',
            'OpenStackInfrastructureSubnet':     'getSubnetIntegrationKeys',
            'OpenStackInfrastructureRouter':     'getRouterIntegrationKeys',
            'OpenStackInfrastructureFloatingIp': 'getFloatingIpIntegrationKeys'
        }.get(self.meta_type, None)

        # Nothing to index here..
        if not methodname:
            return []

        keys = []
        for plugin_name, plugin in zope.component.getUtilitiesFor(INeutronImplementationPlugin):
            getKeys = getattr(plugin, methodname)
            try:
                for key in getKeys(self):
                    if not key.startswith(plugin_name + ":"):
                        log.error("Key '%s' for plugin %s does not contain the proper prefix, and is being ignored.",
                                  key, plugin_name)
                    else:
                        keys.append(key)

            except Exception:
                # I am not sure where these exceptions go, otherwise.
                log.exception("Exception in %s" % getKeys)
                raise

        return keys

    def implementation_components(self):
        keys = self.getNeutronIntegrationKeys()
        if not keys:
            return []

        catalog = get_neutron_implementation_catalog(self.dmd)
        implementationcomponents = []
        for brain in catalog(getNeutronIntegrationKeys=keys):
            try:
                obj = brain.getObject()
            except Exception:
                # ignore a stale entry
                pass
            else:
                implementationcomponents.append(obj)

        return implementationcomponents

    def index_object(self, idxs=None):
        from .OpenstackComponent import OpenstackComponent
        super(OpenstackComponent, self).index_object(idxs=idxs)

        catalog = get_neutron_core_catalog(self.dmd)
        catalog.catalog_object(self, self.getPrimaryId())

    def unindex_object(self):
        from .OpenstackComponent import OpenstackComponent
        super(OpenstackComponent, self).unindex_object()

        catalog = get_neutron_core_catalog(self.dmd)
        catalog.uncatalog_object(self.getPrimaryId())

    def getDefaultGraphDefs(self, drange=None):
        """
        Return graph definitions for this component along with all graphs
        from the implementation components
        """
        from .OpenstackComponent import OpenstackComponent
        graphs = super(OpenstackComponent, self).getDefaultGraphDefs(drange=drange)
        for component in self.implementation_components():
            for graphdef in component.getDefaultGraphDefs(drange=drange):
                graphs.append(graphdef)

        return graphs

    def getGraphObjects(self, drange=None):
        """
        Return graph definitions for this software comoponent, along with
        any graphs from the associated implementation components.
        This method is for 5.x compatibility
        """
        from .OpenstackComponent import OpenstackComponent
        graphs = super(OpenstackComponent, self).getGraphObjects()
        for component in self.implementation_components():
            graphs.extend(component.getGraphObjects())
        return graphs
