##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.catalogs')

import zope.component

from Products.ZCatalog.Catalog import CatalogError
from Products.ZCatalog.ZCatalog import manage_addZCatalog
from Products.ZenUtils.Search import makeKeywordIndex

from ZenPacks.zenoss.OpenStackInfrastructure.interfaces import INeutronImplementationPlugin

def get_neutron_implementation_catalog(dmd):
    device_class = dmd.Devices.getOrganizer('/Devices/OpenStack/Infrastructure')
    catalog_name = 'neutron_implementation'

    try:
        catalog = getattr(device_class, catalog_name)
    except AttributeError:
        if not hasattr(device_class, catalog_name):
            log.info("Creating neutron integration catalog '%s'", catalog_name)
            manage_addZCatalog(device_class, catalog_name, catalog_name)

        zcatalog = device_class._getOb(catalog_name)
        catalog = zcatalog._catalog

        try:
            log.info('Adding integration key index to %s', catalog_name)
            index = makeKeywordIndex('getNeutronIntegrationKeys')

            # Make the index explicitly case sensitive.
            index.PrenormalizeTerm = ''

            catalog.addIndex('getNeutronIntegrationKeys', index)

        except CatalogError:
            # Index already exists.
            pass

        else:
            # index everything.
            for plugin_name, plugin in zope.component.getUtilitiesFor(INeutronImplementationPlugin):
                plugin.reindex_implementation_components(dmd)

    return catalog


def get_neutron_core_catalog(dmd):
    device_class = dmd.Devices.getOrganizer('/Devices/OpenStack/Infrastructure')
    catalog_name = 'neutron_core'

    try:
        catalog = getattr(device_class, catalog_name)
    except AttributeError:
        if not hasattr(device_class, catalog_name):
            log.info("Creating neutron core catalog '%s'", catalog_name)
            manage_addZCatalog(device_class, catalog_name, catalog_name)

        zcatalog = device_class._getOb(catalog_name)
        catalog = zcatalog._catalog

        try:
            log.info('Adding integration key index to %s', catalog_name)
            index = makeKeywordIndex('getNeutronIntegrationKeys')

            # Make the index explicitly case sensitive.
            index.PrenormalizeTerm = ''

            catalog.addIndex('getNeutronIntegrationKeys', index)

        except CatalogError:
            # Index already exists.
            pass

        else:
            from ZenPacks.zenoss.OpenStackInfrastructure.neutron_implementation import all_core_components

            for obj in all_core_components(dmd):
                catalog.catalog_object(obj, obj.getPrimaryId())

    return catalog
