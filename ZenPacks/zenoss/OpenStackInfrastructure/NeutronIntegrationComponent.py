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

from . import zenpacklib

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
        yield brain.getObject()


class NeutronIntegrationComponent(object):

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
        return [brain.getObject() for brain in catalog(getNeutronIntegrationKeys=keys)]

    def index_object(self, **kwargs):
        zenpacklib.CatalogBase.index_object(self)

        catalog = get_neutron_core_catalog(self.dmd)
        catalog.catalog_object(self, self.getPrimaryId())

    def unindex_object(self):
        zenpacklib.CatalogBase.unindex_object(self)

        catalog = get_neutron_core_catalog(self.dmd)
        catalog.uncatalog_object(self.getPrimaryId())
