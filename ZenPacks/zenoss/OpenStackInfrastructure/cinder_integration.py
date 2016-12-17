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

from zope.interface import implements
import zope.component
from zope.event import notify
from Products.Zuul.catalog.events import IndexingEvent


from .catalogs import get_cinder_implementation_catalog, get_cinder_core_catalog
from .interfaces import ICinderImplementationPlugin, ICinderImplementationComponent
from .CinderIntegrationComponent import all_cinder_core_components


# Split a comma-separated list, as returned from an ini file, into a list type.
# This is useful in the ini_process method.
def split_list(s):
    if s is None:
        return []
    else:
        return [y for y in [x.strip() for x in s.split(',')] if len(y)]


def reindex_core_components(dmd):
    log.info("Reindexing all cinder core components")
    for obj in all_cinder_core_components(dmd):
        obj.index_object()
        notify(IndexingEvent(obj))


def reindex_implementation_components(dmd):
    for plugin_name, plugin in zope.component.getUtilitiesFor(ICinderImplementationPlugin):
        log.info("Asking implementation plugin %s to reindex its components" % plugin_name)
        plugin.reindex_implementation_components(dmd)


def index_implementation_object(obj):
    catalog = get_cinder_implementation_catalog(obj.dmd)
    catalog.catalog_object(obj, obj.getPrimaryId())


def unindex_implementation_object(obj):
    catalog = get_cinder_implementation_catalog(obj.dmd)
    catalog.uncatalog_object(obj.getPrimaryId())


def get_cinder_components(obj):
    """
    Returns the cinder (core) components for an implementation object
    """

    keys = obj.getCinderIntegrationKeys()
    if not keys:
        return []

    catalog = get_cinder_core_catalog(obj.dmd)
    cinder_components = []
    for brain in catalog(getCinderIntegrationKeys=keys):
        try:
            obj = brain.getObject()
        except Exception:
            # ignore a stale entry
            pass
        else:
            cinder_components.append(obj)
    return cinder_components


# Base class for cinder integration plugins which implement ICinderImplementationPlugin
class BaseCinderImplementationPlugin(object):
    implements(ICinderImplementationPlugin)

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
    def reindex_cinder_implementation_components(cls):
        pass

    def getPoolIntegrationKeys(self, pool):
        return []

    def getVolumeIntegrationKeys(self, volume):
        return []

    def getSnapshotIntegrationKeys(self, snapshot):
        return []

    def getBackupIntegrationKeys(self, backup):
        return []


# Note: This is provided as an example. In practice, you probably do not want
# to use this class, since inheriting from it will make installation of
# the OpenStackInfrastructure zenpack mandatory.
class BaseCinderImplementationComponent(object):
    implements(ICinderImplementationComponent)

    cinder_plugin_name = None

    def getCinderIntegrationKeys(self):
        return []

    def index_cinder_object(self, idxs=None):
        if self.cinder_plugin_name is None:
            raise ValueError("cinder_plugin_name must be set in subclass %s" % self.__class__)

        index_implementation_object(self)

    def unindex_cinder_object(self):
        if self.cinder_plugin_name is None:
            raise ValueError("cinder_plugin_name must be set in subclass %s" % self.__class__)

        unindex_implementation_object(self)
