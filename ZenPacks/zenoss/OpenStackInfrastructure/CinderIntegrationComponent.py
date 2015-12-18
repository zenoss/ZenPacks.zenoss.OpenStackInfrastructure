##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.cinder_integration')

import zope.component


from Products.Zuul.interfaces import ICatalogTool

from ZenPacks.zenoss.OpenStackInfrastructure.catalogs import (
    get_cinder_implementation_catalog,
    get_cinder_core_catalog
)

from ZenPacks.zenoss.OpenStackInfrastructure.interfaces import (
    ICinderImplementationPlugin
)


def all_cinder_core_components(dmd):
    device_class = dmd.Devices.getOrganizer('/Devices/OpenStack/Infrastructure')
    results = ICatalogTool(device_class).search(
        ('ZenPacks.zenoss.OpenStackInfrastructure.Pool.Pool',
         'ZenPacks.zenoss.OpenStackInfrastructure.Volume.Volume',
         'ZenPacks.zenoss.OpenStackInfrastructure.Snapshot.Snapshot',
         'ZenPacks.zenoss.OpenStackInfrastructure.Backup.Backup',
         )
    )
    for brain in results:
        yield brain.getObject()


class CinderIntegrationComponent(object):

    """Mixin for model classes that have Cinder integrations."""

    def getCinderIntegrationKeys(self):
        methodname = {
            'OpenStackInfrastructurePool':         'getPoolIntegrationKeys',
            'OpenStackInfrastructureVolume':       'getVolumeIntegrationKeys',
            'OpenStackInfrastructureSnapshot':     'getSnapshotIntegrationKeys',
            'OpenStackInfrastructureBackup':       'getBackupIntegrationKeys'
        }.get(self.meta_type, None)

        # Nothing to index here..
        if not methodname:
            return []

        keys = []
        for plugin_name, plugin in zope.component.getUtilitiesFor(ICinderImplementationPlugin):
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
        keys = self.getCinderIntegrationKeys()
        if not keys:
            return []

        catalog = get_cinder_implementation_catalog(self.dmd)
        return [brain.getObject() for brain in catalog(getCinderIntegrationKeys=keys)]

    def index_cinder_object(self, idxs=None):
        from .OpenstackComponent import OpenstackComponent
        super(OpenstackComponent, self).index_object(idxs=idxs)

        catalog = get_cinder_core_catalog(self.dmd)
        catalog.catalog_object(self, self.getPrimaryId())

    def unindex_cinder_object(self):
        from .OpenstackComponent import OpenstackComponent
        super(OpenstackComponent, self).unindex_object()

        catalog = get_cinder_core_catalog(self.dmd)
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
