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

from zope.interface import implements
import zope.component

from .catalogs import get_neutron_implementation_catalog, get_neutron_core_catalog
from .interfaces import INeutronImplementationPlugin, INeutronImplementationComponent
from .NeutronIntegrationComponent import all_core_components


# Split a comma-separated list, as returned from an ini file, into a list type.
# This is useful in the ini_process method.
def split_list(s):
    if s is None:
        return []
    else:
        return [y for y in [x.strip() for x in s.split(',')] if len(y)]


def reindex_core_components(dmd):
    log.info("Reindexing all core neutron components")
    for obj in all_core_components(dmd):
        obj.index_object()


def reindex_implementation_components(dmd):
    for plugin_name, plugin in zope.component.getUtilitiesFor(INeutronImplementationPlugin):
        log.info("Asking implementation plugin %s to reindex its components" % plugin_name)
        plugin.reindex_implementation_components(dmd)


def index_implementation_object(obj):
    catalog = get_neutron_implementation_catalog(obj.dmd)
    catalog.catalog_object(obj, obj.getPrimaryId())


def unindex_implementation_object(obj):
    catalog = get_neutron_implementation_catalog(obj.dmd)
    catalog.uncatalog_object(obj.getPrimaryId())


def get_neutron_components(obj):
    """
    Returns the neutron (core) components for an implementation object
    """

    keys = obj.getNeutronIntegrationKeys()
    if not keys:
        return []

    catalog = get_neutron_core_catalog(obj.dmd)
    return [brain.getObject() for brain in catalog(getNeutronIntegrationKeys=keys)]


# Base class for neutron integration plugins which implement INeutronImplementationPlugin
class BaseNeutronImplementationPlugin(object):
    implements(INeutronImplementationPlugin)

    @classmethod
    def ini_required(cls):
        return []

    @classmethod
    def ini_optional(cls):
        return []

    @classmethod
    def ini_process(cls, filename, section_name, option_name, value):
        return value

    @classmethod
    def reindex_implementation_components(cls):
        pass

    def getTenantIntegrationKeys(self, tenant):
        return []

    def getPortIntegrationKeys(self, port):
        return []

    def getNetworkIntegrationKeys(self, network):
        return []

    def getExternalNetworkIntegrationKeys(self, network):
        return []

    def getSubnetIntegrationKeys(self, subnet):
        return []

    def getRouterIntegrationKeys(self, router):
        return []

    def getFloatingIpIntegrationKeys(self, floatingip):
        return []


# Note: This is provided as an example. In practice, you probably do not want
# to use this class, since inheriting from it will make installation of
# the OpenStackInfrastructure zenpack mandatory.
class BaseNeutronImplementationComponent(object):
    implements(INeutronImplementationComponent)

    neutron_plugin_name = None

    def getNeutronIntegrationKeys(self):
        return []

    def index_object(self, **kwargs):
        if self.neutron_plugin_name is None:
            raise ValueError("neutron_plugin_name must be set in subclass %s" % self.__class__)

        index_implementation_object(self)

    def unindex_object(self):
        if self.neutron_plugin_name is None:
            raise ValueError("neutron_plugin_name must be set in subclass %s" % self.__class__)

        unindex_implementation_object(self)
