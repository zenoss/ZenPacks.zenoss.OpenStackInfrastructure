#!/usr/bin/env python

##############################################################################
# This program is part of zenpacklib, the ZenPack API.
# Copyright (C) 2013-2015  Zenoss, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
##############################################################################

"""zenpacklib - ZenPack API.

This module provides a single integration point for common ZenPacks.

"""

# PEP-396 version. (https://www.python.org/dev/peps/pep-0396/)
__version__ = "1.0.9"


import logging
LOG = logging.getLogger('zen.zenpacklib')

# Suppresses "No handlers could be found for logger" errors if logging
# hasn't been configured.
LOG.addHandler(logging.NullHandler())

import collections
import imp
import importlib
import inspect
import json
import operator
import os
import re
import sys
import math
import types

from lxml import etree

if __name__ == '__main__':
    import Globals
    from Products.ZenUtils.Utils import unused
    unused(Globals)

from zope.browser.interfaces import IBrowserView
from zope.component import adapts, getGlobalSiteManager
from zope.event import notify
from zope.interface import classImplements, implements
from zope.interface.interface import InterfaceClass
from Acquisition import aq_base

from Products.AdvancedQuery import Eq, Or
from Products.AdvancedQuery.AdvancedQuery import _BaseQuery as BaseQuery
from Products.Five import zcml

from Products.ZenModel.Device import Device as BaseDevice
from Products.ZenModel.DeviceComponent import DeviceComponent as BaseDeviceComponent
from Products.ZenModel.HWComponent import HWComponent as BaseHWComponent
from Products.ZenModel.ManagedEntity import ManagedEntity as BaseManagedEntity
from Products.ZenModel.ZenossSecurity import ZEN_CHANGE_DEVICE
from Products.ZenModel.ZenPack import ZenPack as ZenPackBase
from Products.ZenModel.CommentGraphPoint import CommentGraphPoint
from Products.ZenModel.ComplexGraphPoint import ComplexGraphPoint
from Products.ZenModel.ThresholdGraphPoint import ThresholdGraphPoint
from Products.ZenModel.GraphPoint import GraphPoint
from Products.ZenModel.DataPointGraphPoint import DataPointGraphPoint
from Products.ZenRelations.Exceptions import ZenSchemaError
from Products.ZenRelations.RelSchema import ToMany, ToManyCont, ToOne
from Products.ZenRelations.ToManyContRelationship import ToManyContRelationship
from Products.ZenRelations.ToManyRelationship import ToManyRelationship
from Products.ZenRelations.ToOneRelationship import ToOneRelationship
from Products.ZenRelations.zPropertyCategory import setzPropertyCategory
from Products.ZenUI3.browser.interfaces import IMainSnippetManager
from Products.ZenUI3.utils.javascript import JavaScriptSnippet
from Products.ZenUtils.guid.interfaces import IGlobalIdentifier
from Products.ZenUtils.Search import makeFieldIndex, makeKeywordIndex
from Products.ZenUtils.Utils import monkeypatch, importClass

from Products import Zuul
from Products.Zuul.catalog.events import IndexingEvent
from Products.Zuul.catalog.global_catalog import ComponentWrapper as BaseComponentWrapper
from Products.Zuul.catalog.global_catalog import DeviceWrapper as BaseDeviceWrapper
from Products.Zuul.catalog.interfaces import IIndexableWrapper, IPathReporter
from Products.Zuul.catalog.paths import DefaultPathReporter, relPath
from Products.Zuul.decorators import info, memoize
from Products.Zuul.form import schema
from Products.Zuul.form.interfaces import IFormBuilder
from Products.Zuul.infos import InfoBase, ProxyProperty
from Products.Zuul.infos.component import ComponentInfo as BaseComponentInfo
from Products.Zuul.infos.component import ComponentFormBuilder as BaseComponentFormBuilder
from Products.Zuul.infos.device import DeviceInfo as BaseDeviceInfo
from Products.Zuul.interfaces import IInfo
from Products.Zuul.interfaces.component import IComponentInfo as IBaseComponentInfo
from Products.Zuul.interfaces.device import IDeviceInfo as IBaseDeviceInfo
from Products.Zuul.routers.device import DeviceRouter
from Products.Zuul.utils import ZuulMessageFactory as _t

from zope.publisher.interfaces.browser import IDefaultBrowserLayer
from zope.viewlet.interfaces import IViewlet

try:
    import yaml
    import yaml.constructor
    YAML_INSTALLED = True
except ImportError:
    YAML_INSTALLED = False

OrderedDict = None

try:
    # included in standard lib from Python 2.7
    from collections import OrderedDict
except ImportError:
    # try importing the backported drop-in replacement
    # it's available on PyPI
    try:
        from ordereddict import OrderedDict
    except ImportError:
        OrderedDict = None

# Exported symbols. These are the only symbols imported by wildcard.
__all__ = (
    # Classes
    'Device',
    'Component',
    'HardwareComponent',

    'TestCase',

    'ZenPackSpec',

    # Functions.
    'enableTesting',
    'ucfirst',
    'relname_from_classname',
    'relationships_from_yuml',
    'catalog_search',
    )

# Must defer definition of TestCase. Otherwise it imports
# BaseTestCase which puts Zope into testing mode.
TestCase = None

# Required for registering ZCSA adapters.
GSM = getGlobalSiteManager()


# Public Classes ############################################################

class ZenPack(ZenPackBase):
    """
    ZenPack loader that handles custom installation and removal tasks.
    """

    def __init__(self, *args, **kwargs):
        super(ZenPack, self).__init__(*args, **kwargs)

        # Emable logging to stderr if the user sets the ZPL_LOG_ENABLE environment
        # variable to this zenpack's name.   (defaults to 'DEBUG', but
        # user may choose a different level with ZPL_LOG_LEVEL.
        if self.id in os.environ.get('ZPL_LOG_ENABLE', ''):
            levelName = os.environ.get('ZPL_LOG_LEVEL', 'DEBUG').upper()
            logLevel = getattr(logging, levelName)

            if logLevel:
                # Reconfigure the logger to ensure it goes to stderr for the
                # selected level or above.
                LOG.propagate = False
                LOG.setLevel(logLevel)
                h = logging.StreamHandler(sys.stderr)
                h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
                LOG.addHandler(h)
            else:
                LOG.error("Unrecognized ZPL_LOG_LEVEL '%s'" %
                          os.environ.get('ZPL_LOG_LEVEL'))

    # NEW_COMPONENT_TYPES AND NEW_RELATIONS will be monkeypatched in
    # via zenpacklib when this class is instantiated.

    def _buildDeviceRelations(self):
        for d in self.dmd.Devices.getSubDevicesGen():
            d.buildRelations()

    def install(self, app):
        # create device classes and set zProperties on them
        for dcname, dcspec in self.device_classes.iteritems():
            if dcspec.create:
                try:
                    self.dmd.Devices.getOrganizer(dcspec.path)
                except KeyError:
                    LOG.info('Creating DeviceClass %s' % dcspec.path)
                    app.dmd.Devices.createOrganizer(dcspec.path)

            dcObject = self.dmd.Devices.getOrganizer(dcspec.path)
            for zprop, value in dcspec.zProperties.iteritems():
                LOG.info('Setting zProperty %s on %s' % (zprop, dcspec.path))
                dcObject.setZenProperty(zprop, value)

        # Load objects.xml now
        super(ZenPack, self).install(app)
        if self.NEW_COMPONENT_TYPES:
            LOG.info('Adding %s relationships to existing devices' % self.id)
            self._buildDeviceRelations()

        # load monitoring templates
        for dcname, dcspec in self.device_classes.iteritems():
            for mtname, mtspec in dcspec.templates.iteritems():
                mtspec.create(self.dmd)

    def remove(self, app, leaveObjects=False):
        if self._v_specparams is None:
            return

        from Products.Zuul.interfaces import ICatalogTool
        if leaveObjects:
            # Check whether the ZPL-managed monitoring templates have
            # been modified by the user.  If so, those changes will
            # be lost during the upgrade.
            #
            # Ideally, I would inspect self.packables() to find these
            # objects, but we do not have access to that relationship
            # at this point in the process.
            for dcname, dcspec in self._v_specparams.device_classes.iteritems():
                try:
                    deviceclass = self.dmd.Devices.getOrganizer(dcname)
                except KeyError:
                    # DeviceClass.getOrganizer() can raise a KeyError if the
                    # organizer doesn't exist.
                    deviceclass = None

                if deviceclass is None:
                    LOG.warning(
                        "DeviceClass %s has been removed at some point "
                        "after the %s ZenPack was installed.  It will be "
                        "reinstated if this ZenPack is upgraded or reinstalled",
                        dcname, self.id)
                    continue

                for orig_mtname, orig_mtspec in dcspec.templates.iteritems():
                    try:
                        template = deviceclass.rrdTemplates._getOb(orig_mtname)
                    except AttributeError:
                        template = None

                    if template is None:
                        LOG.warning(
                            "Monitoring template %s/%s has been removed at some point "
                            "after the %s ZenPack was installed.  It will be "
                            "reinstated if this ZenPack is upgraded or reinstalled",
                            dcname, orig_mtname, self.id)
                        continue

                    installed = RRDTemplateSpecParams.fromObject(template)

                    if installed != orig_mtspec:
                        import time
                        import difflib

                        lines_installed = [x + '\n' for x in yaml.dump(installed, Dumper=Dumper).split('\n')]
                        lines_orig_mtspec = [x + '\n' for x in yaml.dump(orig_mtspec, Dumper=Dumper).split('\n')]
                        diff = ''.join(difflib.unified_diff(lines_orig_mtspec, lines_installed))

                        # installed is not going to have cycletime in it, because it's the default.

                        newname = "{}-upgrade-{}".format(orig_mtname, int(time.time()))
                        LOG.error(
                            "Monitoring template %s/%s has been modified "
                            "since the %s ZenPack was installed.  These local "
                            "changes will be lost as this ZenPack is upgraded "
                            "or reinstalled.   Existing template will be "
                            "renamed to '%s'.  Please review and reconcile "
                            "local changes:\n%s",
                            dcname, orig_mtname, self.id, newname, diff)

                        deviceclass.rrdTemplates.manage_renameObject(template.id, newname)

        else:
            dc = app.Devices
            for catalog in self.GLOBAL_CATALOGS:
                catObj = getattr(dc, catalog, None)
                if catObj:
                    LOG.info('Removing Catalog %s' % catalog)
                    dc._delObject(catalog)

            if self.NEW_COMPONENT_TYPES:
                LOG.info('Removing %s components' % self.id)
                cat = ICatalogTool(app.zport.dmd)
                for brain in cat.search(types=self.NEW_COMPONENT_TYPES):
                    component = brain.getObject()
                    component.getPrimaryParent()._delObject(component.id)

                # Remove our Device relations additions.
                from Products.ZenUtils.Utils import importClass
                for device_module_id in self.NEW_RELATIONS:
                    Device = importClass(device_module_id)
                    Device._relations = tuple([x for x in Device._relations
                                               if x[0] not in self.NEW_RELATIONS[device_module_id]])

                LOG.info('Removing %s relationships from existing devices.' % self.id)
                self._buildDeviceRelations()

            for dcname, dcspec in self.device_classes.iteritems():
                if dcspec.remove:
                    organizerPath = '/Devices/' + dcspec.path.lstrip('/')
                    try:
                        app.dmd.Devices.getOrganizer(organizerPath)
                    except KeyError:
                        LOG.warning('Unable to remove DeviceClass %s (not found)' % dcspec.path)
                        continue

                    LOG.info('Removing DeviceClass %s' % dcspec.path)
                    app.dmd.Devices.manage_deleteOrganizer(organizerPath)

        super(ZenPack, self).remove(app, leaveObjects=leaveObjects)

    def manage_exportPack(self, download="no", REQUEST=None):
        """Export ZenPack to $ZENHOME/export directory.

        Postprocess the generated xml files to remove references to ZPL-managed
        objects.
        """
        from Products.ZenModel.ZenPackLoader import findFiles

        result = super(ZenPack, self).manage_exportPack(
            download=download,
            REQUEST=REQUEST)

        for filename in findFiles(self, 'objects', lambda f: f.endswith('.xml')):
            self.filter_xml(filename)

        return result

    def filter_xml(self, filename):
        pruned = 0
        try:
            tree = etree.parse(filename)

            path = []
            context = etree.iterwalk(tree, events=('start', 'end'))
            for action, elem in context:
                if elem.tag == 'object':
                    if action == 'start':
                        path.append(elem.attrib.get('id'))

                    elif action == 'end':
                        obj_path = '/'.join(path)
                        try:
                            obj = self.dmd.getObjByPath(obj_path)
                            if getattr(obj, 'zpl_managed', False):
                                LOG.debug("Removing %s from %s", obj_path, filename)
                                pruned += 1

                                # if there's a comment before it with the
                                # primary path of the object, remove that first.
                                prev = elem.getprevious()
                                if '<!-- ' + repr(tuple('/'.join(path).split('/'))) + ' -->' == repr(prev):
                                    elem.getparent().remove(prev)

                                # Remove the ZPL-managed object
                                elem.getparent().remove(elem)

                        except Exception:
                            LOG.warning("Unable to postprocess %s in %s", obj_path, filename)

                        path.pop()

                if elem.tag == 'tomanycont':
                    if action == 'start':
                        path.append(elem.attrib.get('id'))
                    elif action == 'end':
                        path.pop()

            if len(tree.getroot()) == 0:
                LOG.info("Removing %s", filename)
                os.remove(filename)
            elif pruned:
                LOG.info("Pruning %d objects from %s", pruned, filename)
                with open(filename, 'w') as f:
                    f.write(etree.tostring(tree))
            else:
                LOG.debug("Leaving %s unchanged", filename)

        except Exception, e:
            LOG.error("Unable to postprocess %s: %s", filename, e)


class CatalogBase(object):
    """Base class that implements cataloging a property"""

    # By Default there is no default catalog created.
    _catalogs = {}

    def search(self, name, *args, **kwargs):
        """
        Return iterable of matching brains in named catalog.
        'name' is the catalog name (typically the name of a class)
        """
        return catalog_search(self, name, *args, **kwargs)

    @classmethod
    def class_search(cls, dmd, name, *args, **kwargs):
        """
        Return iterable of matching brains in named catalog.
        'name' is the catalog name (typically the name of a class)
        """

        name = cls.__module__.replace('.', '_')
        return catalog_search(dmd.Devices, name, *args, **kwargs)

    @classmethod
    def get_catalog_name(cls, name, scope):
        if scope == 'device':
            return '{}Search'.format(name)
        else:
            name = cls.__module__.replace('.', '_')
            return '{}Search'.format(name)

    @classmethod
    def class_get_catalog(cls, dmd, name, scope, create=True):
        """Return catalog by name."""
        spec = cls._get_catalog_spec(name)
        if not spec:
            return

        if scope == 'device':
            raise ValueError("device scoped catalogs are only available from device or component objects, not classes")
        else:
            try:
                return getattr(dmd.Devices, cls.get_catalog_name(name, scope))
            except AttributeError:
                if create:
                    return cls._class_create_catalog(dmd, name, 'global')
        return

    def get_catalog(self, name, scope, create=True):
        """Return catalog by name."""

        spec = self._get_catalog_spec(name)
        if not spec:
            return

        if scope == 'device':
            try:
                return getattr(self.device(), self.get_catalog_name(name, scope))
            except AttributeError:
                if create:
                    return self._create_catalog(name, 'device')
        else:
            try:
                return getattr(self.dmd.Devices, self.get_catalog_name(name, scope))
            except AttributeError:
                if create:
                    return self._create_catalog(name, 'global')
        return

    @classmethod
    def get_catalog_scopes(cls, name):
        """Return catalog scopes by name."""
        spec = cls._get_catalog_spec(name)
        if not spec:
            []

        scopes = [spec['indexes'][x].get('scope', 'device') for x in spec['indexes']]
        if 'both' in scopes:
            scopes = [x for x in scopes if x != 'both']
            scopes.append('device')
            scopes.append('global')
        return set(scopes)

    @classmethod
    def class_get_catalogs(cls, dmd, whiteList=None):
        """Return all catalogs for this class."""

        catalogs = []
        for name in cls._catalogs:
            for scope in cls.get_catalog_scopes(name):
                if scope == 'device':
                    # device scoped catalogs are not available at the class level
                    continue

                if not whiteList:
                    catalogs.append(cls.class_get_catalog(dmd, name, scope))
                else:
                    if scope in whiteList:
                        catalogs.append(cls.class_get_catalog(dmd, name, scope, create=False))
        return catalogs

    def get_catalogs(self, whiteList=None):
        """Return all catalogs for this class."""
        catalogs = []
        for name in self._catalogs:
            for scope in self.get_catalog_scopes(name):
                if not whiteList:
                    catalogs.append(self.get_catalog(name, scope))
                else:
                    if scope in whiteList:
                        catalogs.append(self.get_catalog(name, scope, create=False))
        return catalogs

    @classmethod
    def _get_catalog_spec(cls, name):
        if not hasattr(cls, '_catalogs'):
            LOG.error("%s has no catalogs defined", cls)
            return

        spec = cls._catalogs.get(name)
        if not spec:
            LOG.error("%s catalog definition is missing", name)
            return

        if not isinstance(spec, dict):
            LOG.error("%s catalog definition is not a dict", name)
            return

        if not spec.get('indexes'):
            LOG.error("%s catalog definition has no indexes", name)
            return

        return spec

    @classmethod
    def _class_create_catalog(cls, dmd, name, scope='device'):
        """Create and return catalog defined by name."""
        from Products.ZCatalog.ZCatalog import manage_addZCatalog

        spec = cls._get_catalog_spec(name)
        if not spec:
            return

        if scope == 'device':
            raise ValueError("device scoped catalogs may only be created from the device or component object, not classes")
        else:
            catalog_name = cls.get_catalog_name(name, scope)
            deviceClass = dmd.Devices

            if not hasattr(deviceClass, catalog_name):
                manage_addZCatalog(deviceClass, catalog_name, catalog_name)

            zcatalog = deviceClass._getOb(catalog_name)

        cls._create_indexes(zcatalog, spec)
        return zcatalog

    def _create_catalog(self, name, scope='device'):
        """Create and return catalog defined by name."""
        from Products.ZCatalog.ZCatalog import manage_addZCatalog

        spec = self._get_catalog_spec(name)
        if not spec:
            return

        if scope == 'device':
            catalog_name = self.get_catalog_name(name, scope)

            device = self.device()
            if not hasattr(device, catalog_name):
                manage_addZCatalog(device, catalog_name, catalog_name)

            zcatalog = device._getOb(catalog_name)
        else:
            catalog_name = self.get_catalog_name(name, scope)
            deviceClass = self.dmd.Devices

            if not hasattr(deviceClass, catalog_name):
                manage_addZCatalog(deviceClass, catalog_name, catalog_name)

            zcatalog = deviceClass._getOb(catalog_name)

        self._create_indexes(zcatalog, spec)
        return zcatalog

    @classmethod
    def _create_indexes(cls, zcatalog, spec):
        from Products.ZCatalog.Catalog import CatalogError
        from Products.Zuul.interfaces import ICatalogTool
        catalog = zcatalog._catalog

        classname = spec.get(
            'class', 'Products.ZenModel.DeviceComponent.DeviceComponent')

        for propname, propdata in spec['indexes'].items():
            index_type = propdata.get('type')
            if not index_type:
                LOG.error("%s index has no type", propname)
                return

            index_factory = {
                'field': makeFieldIndex,
                'keyword': makeKeywordIndex,
                }.get(index_type.lower())

            if not index_factory:
                LOG.error("%s is not a valid index type", index_type)
                return

            try:
                catalog.addIndex(propname, index_factory(propname))
                catalog.addColumn(propname)
            except CatalogError:
                # Index already exists.
                pass
            else:
                # the device if it's a device scoped catalog, or dmd.Devices
                # if it's a global scoped catalog.
                context = zcatalog.getParentNode()

                # reindex all objects of this type so they are added to the
                # catalog.
                results = ICatalogTool(context).search(types=(classname,))
                for result in results:
                    if hasattr(result.getObject(), 'index_object'):
                        result.getObject().index_object()

    def index_object(self, idxs=None):
        """Index in all configured catalogs."""
        for catalog in self.get_catalogs():
            if catalog:
                catalog.catalog_object(self, self.getPrimaryId())

    def unindex_object(self):
        """Unindex from all configured catalogs."""
        for catalog in self.get_catalogs():
            if catalog:
                catalog.uncatalog_object(self.getPrimaryId())


class ModelBase(CatalogBase):

    """Base class for ZenPack model classes."""

    def getIconPath(self):
        """Return relative URL path for class' icon."""
        return getattr(self, 'icon_url', '/zport/dmd/img/icons/noicon.png')


class DeviceBase(ModelBase):

    """First superclass for zenpacklib types created by DeviceTypeFactory.

    Contains attributes that should be standard on all ZenPack Device
    types.

    """


class ComponentBase(ModelBase):

    """First superclass for zenpacklib types created by ComponentTypeFactory.

    Contains attributes that should be standard on all ZenPack Component
    types.

    """

    factory_type_information = ({
        'actions': ({
            'id': 'perfConf',
            'name': 'Template',
            'action': 'objTemplates',
            'permissions': (ZEN_CHANGE_DEVICE,),
            },),
        },)

    _catalogs = {
        'ComponentBase': {
            'indexes': {
                'id': {'type': 'field'},
                }
            }
        }

    def device(self):
        """Return device under which this component/device is contained."""
        obj = self

        for i in xrange(200):
            if isinstance(obj, BaseDevice):
                return obj

            try:
                obj = obj.getPrimaryParent()
            except AttributeError:
                # While it is generally not normal to have devicecomponents
                # that are not part of a device, it CAN occur in certain
                # non-error situations, such as when it is in the process of
                # being deleted.  In that case, the DeviceComponentProtobuf
                # (Products.ZenMessaging.queuemessaging.adapters) implementation
                # expects device() to return None, not to throw an exception.
                return None

    def getStatus(self, statClass='/Status'):
        """Return the status number for this component.

        Overridden to default statClass to /Status instead of
        /Status/<self.meta_type>. Current practices do not include using
        a separate event class for each component meta_type. The event
        class plus component field already convey this level of
        information.

        """
        return BaseDeviceComponent.getStatus(self, statClass=statClass)

    def getIdForRelationship(self, relationship):
        """Return id in ToOne relationship or None."""
        obj = relationship()
        if obj:
            return obj.id

    def setIdForRelationship(self, relationship, id_):
        """Update ToOne relationship given relationship and id."""
        old_obj = relationship()

        # Return with no action if the relationship is already correct.
        if (old_obj and old_obj.id == id_) or (not old_obj and not id_):
            return

        # Remove current object from relationship.
        if old_obj:
            relationship.removeRelation()

            # Index old object. It might have a custom path reporter.
            notify(IndexingEvent(old_obj.primaryAq(), 'path', False))

        # If there is no new ID to add, we're done.
        if id_ is None:
            return

        # Find and add new object to relationship.
        for result in catalog_search(self.device(), 'ComponentBase', id=id_):
            new_obj = result.getObject()
            relationship.addRelation(new_obj)

            # Index remote object. It might have a custom path reporter.
            notify(IndexingEvent(new_obj.primaryAq(), 'path', False))

            # For componentSearch. Would be nice if we could target
            # idxs=['getAllPaths'], but there's a chance that it won't exist
            # yet.
            new_obj.index_object()
            return

        LOG.error("setIdForRelationship (%s): No target found matching id=%s", relationship, id_)

    def getIdsInRelationship(self, relationship):
        """Return a list of object ids in relationship.

        relationship must be of type ToManyContRelationship or
        ToManyRelationship. Raises ValueError for any other type.

        """
        if isinstance(relationship, ToManyContRelationship):
            return relationship.objectIds()
        elif isinstance(relationship, ToManyRelationship):
            return [x.id for x in relationship.objectValuesGen()]

        try:
            type_name = type(relationship.aq_self).__name__
        except AttributeError:
            type_name = type(relationship).__name__

        raise ValueError(
            "invalid type '%s' for getIdsInRelationship()" % type_name)

    def setIdsInRelationship(self, relationship, ids):
        """Update ToMany relationship given relationship and ids."""
        new_ids = set(ids)
        current_ids = set(o.id for o in relationship.objectValuesGen())
        changed_ids = new_ids.symmetric_difference(current_ids)

        query = Or(*[Eq('id', x) for x in changed_ids])

        obj_map = {}
        for result in catalog_search(self.device(), 'ComponentBase', query):
            obj_map[result.id] = result.getObject()

        for id_ in new_ids.symmetric_difference(current_ids):
            obj = obj_map.get(id_)
            if not obj:
                LOG.error(
                    "setIdsInRelationship (%s): No targets found matching "
                    "id=%s", relationship, id_)

                continue

            if id_ in new_ids:
                LOG.debug("Adding %s to %s" % (obj, relationship))
                relationship.addRelation(obj)

                # Index remote object. It might have a custom path reporter.
                notify(IndexingEvent(obj, 'path', False))
            else:
                LOG.debug("Removing %s from %s" % (obj, relationship))
                relationship.removeRelation(obj)

                # If the object was not deleted altogether..
                if not isinstance(relationship, ToManyContRelationship):
                    # Index remote object. It might have a custom path reporter.
                    notify(IndexingEvent(obj, 'path', False))

            # For componentSearch. Would be nice if we could target
            # idxs=['getAllPaths'], but there's a chance that it won't exist
            # yet.
            obj.index_object()

    @property
    def containing_relname(self):
        """Return name of containing relationship."""
        return self.get_containing_relname()

    @memoize
    def get_containing_relname(self):
        """Return name of containing relationship."""
        for relname, relschema in self._relations:
            if issubclass(relschema.remoteType, ToManyCont):
                return relname
        raise ZenSchemaError("%s (%s) has no containing relationship" % (self.__class__.__name__, self))

    @property
    def faceting_relnames(self):
        """Return non-containing relationship names for faceting."""
        return self.get_faceting_relnames()

    @memoize
    def get_faceting_relnames(self):
        """Return non-containing relationship names for faceting."""
        faceting_relnames = []

        for relname, relschema in self._relations:
            if relname in FACET_BLACKLIST:
                continue

            if issubclass(relschema.remoteType, ToMany):
                faceting_relnames.append(relname)

        return faceting_relnames

    def get_facets(self, root=None, streams=None, seen=None, path=None, recurse_all=False):
        """Generate non-containing related objects for faceting."""
        if seen is None:
            seen = set()

        if path is None:
            path = []

        if root is None:
            root = self

        if streams is None:
            streams = getattr(self, '_v_path_pattern_streams', [])

        for relname in self.get_faceting_relnames():
            rel = getattr(self, relname, None)
            if not rel or not callable(rel):
                continue

            relobjs = rel()
            if not relobjs:
                continue

            if isinstance(rel, ToOneRelationship):
                # This is really a single object.
                relobjs = [relobjs]

            relpath = "/".join(path + [relname])

            # Always include directly-related objects.
            for obj in relobjs:
                if obj in seen:
                    continue

                yield obj
                seen.add(obj)

            # If 'all' mode, just include indirectly-related objects as well, in
            # an unfiltered manner.
            if recurse_all:
                for facet in obj.get_facets(root=root, seen=seen, path=path + [relname], recurse_all=True):
                    yield facet
                return

            # Otherwise, look at extra_path defined path pattern streams
            for stream in streams:
                recurse = any([pattern.match(relpath) for pattern in stream])

                LOG.log(9, "[%s] matching %s against %s: %s" % (root.meta_type, relpath, [x.pattern for x in stream], recurse))

                if not recurse:
                    continue

                for obj in relobjs:
                    for facet in obj.get_facets(root=root, seen=seen, streams=[stream], path=path + [relname]):
                        if facet in seen:
                            continue

                        yield facet
                        seen.add(facet)

    def rrdPath(self):
        """Return filesystem path for RRD files for this component.

        Overrides RRDView to flatten component RRD files into a single
        subdirectory per-component per-device. This allows for the
        possibility of a component changing its contained path within
        the device without losing historical performance data.

        This requires that each component have a unique id within the
        device's namespace.

        """
        original = super(ComponentBase, self).rrdPath()

        try:
            # Zenoss 5 returns a JSONified dict from rrdPath.
            json.loads(original)
        except ValueError:
            # Zenoss 4 and earlier return a string that starts with "Devices/"
            return os.path.join('Devices', self.device().id, self.id)
        else:
            return original

    def getRRDTemplateName(self):
        """Return name of primary template to bind to this component."""
        if self._templates:
            return self._templates[0]

        return ''

    def getRRDTemplates(self):
        """Return list of templates to bind to this component.

        Enhances RRDView.getRRDTemplates by supporting both acquisition
        and inhertence template binding. Additionally supports user-
        defined *-replacement and *-addition monitoring templates that
        can replace or augment the standard templates respectively.

        """
        templates = []

        for template_name in self._templates:
            replacement = self.getRRDTemplateByName(
                '{}-replacement'.format(template_name))

            if replacement:
                templates.append(replacement)
            else:
                template = self.getRRDTemplateByName(template_name)
                if template:
                    templates.append(template)

            addition = self.getRRDTemplateByName(
                '{}-addition'.format(template_name))

            if addition:
                templates.append(addition)

        return templates


class DeviceIndexableWrapper(BaseDeviceWrapper):

    """Indexing wrapper for ZenPack devices.

    This is required to make sure that key classes are returned by
    objectImplements even if their depth within the inheritence tree
    would otherwise exclude them. Certain searches in Zenoss expect
    objectImplements to contain Device.

    """

    implements(IIndexableWrapper)
    adapts(DeviceBase)

    def objectImplements(self):
        """Return list of implemented interfaces and classes.

        Extends DeviceWrapper by ensuring that Device will always be
        part of the returned list.

        """
        dottednames = super(DeviceIndexableWrapper, self).objectImplements()

        return list(set(dottednames).union([
            'Products.ZenModel.Device.Device',
            ]))


GSM.registerAdapter(DeviceIndexableWrapper, (DeviceBase,), IIndexableWrapper)


class ComponentIndexableWrapper(BaseComponentWrapper):

    """Indexing wrapper for ZenPack components.

    This is required to make sure that key classes are returned by
    objectImplements even if their depth within the inheritence tree
    would otherwise exclude them. Certain searches in Zenoss expect
    objectImplements to contain DeviceComponent and ManagedEntity where
    applicable.

    """

    implements(IIndexableWrapper)
    adapts(ComponentBase)

    def objectImplements(self):
        """Return list of implemented interfaces and classes.

        Extends ComponentWrapper by ensuring that DeviceComponent will
        always be part of the returned list.

        """
        dottednames = super(ComponentIndexableWrapper, self).objectImplements()

        return list(set(dottednames).union([
            'Products.ZenModel.DeviceComponent.DeviceComponent',
            ]))


GSM.registerAdapter(ComponentIndexableWrapper, (ComponentBase,), IIndexableWrapper)


class ComponentPathReporter(DefaultPathReporter):

    """Global catalog path reporter adapter factory for components."""

    implements(IPathReporter)
    adapts(ComponentBase)

    def getPaths(self):
        paths = super(ComponentPathReporter, self).getPaths()

        for facet in self.context.get_facets():
            rp = relPath(facet, facet.containing_relname)
            paths.extend(rp)

        return paths

GSM.registerAdapter(ComponentPathReporter, (ComponentBase,), IPathReporter)


class ComponentFormBuilder(BaseComponentFormBuilder):

    """Base class for all custom FormBuilders.

    Adds support for renderers in the Component Details form.

    """

    implements(IFormBuilder)
    adapts(IInfo)

    def render(self, **kwargs):
        rendered = super(ComponentFormBuilder, self).render(kwargs)
        self.zpl_decorate(rendered)
        return rendered

    def zpl_decorate(self, item):
        if 'items' in item:
            for item in item['items']:
                self.zpl_decorate(item)
            return

        if 'xtype' in item and 'name' in item and item['xtype'] != 'linkfield':
            if item['name'] in self.renderer:
                renderer = self.renderer[item['name']]

                if renderer:
                    item['xtype'] = 'ZPL_{zenpack_id_prefix}_RenderableDisplayField'.format(
                        zenpack_id_prefix=self.zenpack_id_prefix)
                    item['renderer'] = renderer


class ClassProperty(property):

    """Decorator that works like @property for class methods.

    The @property decorator doesn't work for class methods. This
    @ClassProperty decorator does, but only for getters.

    """
    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()


def ModelTypeFactory(name, bases):
    """Return a "ZenPackified" model class given name and bases tuple."""

    @ClassProperty
    @classmethod
    def _relations(cls):
        """Return _relations property

        This is implemented as a property method to deal with cases
        where ZenPacks loaded after ours in easy-install.pth monkeypatch
        _relations on one of our base classes.

        """

        relations = OrderedDict()
        for base in cls.__bases__:
            base_relations = getattr(base, '_relations', [])
            for base_name, base_schema in base_relations:
                # In the case of multiple bases having relationships
                # by the same name, we want to use the first one.
                # This is consistent with Python method resolution
                # order.
                relations.setdefault(base_name, base_schema)

        if hasattr(cls, '_v_local_relations'):
            for local_name, local_schema in cls._v_local_relations:
                # In the case of a local relationship having a
                # relationship by the same name as one of the bases, we
                # use the local relationship.
                relations[local_name] = local_schema

        return tuple(relations.items())

    def index_object(self, idxs=None):
        for base in bases:
            if hasattr(base, 'index_object'):
                try:
                    base.index_object(self, idxs=idxs)
                except TypeError:
                    base.index_object(self)

    def unindex_object(self):
        for base in bases:
            if hasattr(base, 'unindex_object'):
                base.unindex_object(self)

    attributes = {
        '_relations': _relations,
        'index_object': index_object,
        'unindex_object': unindex_object,
        }

    return type(name, bases, attributes)


def DeviceTypeFactory(name, bases):
    """Return a "ZenPackified" device class given bases tuple."""
    all_bases = (DeviceBase,) + bases

    device_type = ModelTypeFactory(name, all_bases)

    def index_object(self, idxs=None, noips=False):
        for base in all_bases:
            if hasattr(base, 'index_object'):
                try:
                    base.index_object(self, idxs=idxs, noips=noips)
                except TypeError:
                    base.index_object(self)

    device_type.index_object = index_object

    return device_type


Device = DeviceTypeFactory(
    'Device', (BaseDevice,))


def ComponentTypeFactory(name, bases):
    """Return a "ZenPackified" component class given bases tuple."""
    return ModelTypeFactory(name, (ComponentBase,) + bases)


Component = ComponentTypeFactory(
    'Component', (BaseDeviceComponent, BaseManagedEntity))

HardwareComponent = ComponentTypeFactory(
    'HardwareComponent', (BaseHWComponent,))


class IHardwareComponentInfo(IBaseComponentInfo):

    """Info interface for ZenPackHardwareComponent.

    This exists because Zuul has no HWComponent info interface.
    """

    manufacturer = schema.Entity(title=u'Manufacturer')
    product = schema.Entity(title=u'Model')


class HardwareComponentInfo(BaseComponentInfo):

    """Info adapter factory for ZenPackHardwareComponent.

    This exists because Zuul has no HWComponent info adapter.
    """

    implements(IHardwareComponentInfo)
    adapts(HardwareComponent)

    @property
    @info
    def manufacturer(self):
        """Return Info for hardware product class' manufacturer."""
        product_class = self._object.productClass()
        if product_class:
            return product_class.manufacturer()

    @property
    @info
    def product(self):
        """Return Info for hardware product class."""
        return self._object.productClass()


# ZenPack Configuration #####################################################

FACET_BLACKLIST = (
    'dependencies',
    'dependents',
    'maintenanceWindows',
    'pack',
    'productClass',
    )


class Spec(object):
    """Abstract base class for specifications."""

    source_location = None
    speclog = None

    def __init__(self, _source_location=None):

        class LogAdapter(logging.LoggerAdapter):
            def process(self, msg, kwargs):
                return '%s %s' % (self.extra['context'], msg), kwargs

        self.source_location = _source_location
        self.speclog = LogAdapter(LOG, {'context': self})

    def __str__(self):
        parts = []

        if self.source_location:
            parts.append(self.source_location)
        if hasattr(self, 'name') and self.name:
            if callable(self.name):
                parts.append(self.name())
            else:
                parts.append(self.name)
        else:
            parts.append(super(Spec, self).__str__())

        return "%s(%s)" % (self.__class__.__name__, ' - '.join(parts))

    def specs_from_param(self, spec_type, param_name, param_dict, apply_defaults=True, leave_defaults=False):
        """Return a normalized dictionary of spec_type instances."""
        if param_dict is None:
            param_dict = {}
        elif not isinstance(param_dict, dict):
            raise TypeError(
                "{!r} argument must be dict or None, not {!r}"
                .format(
                    '{}.{}'.format(spec_type.__name__, param_name),
                    type(param_dict).__name__))
        else:
            if apply_defaults:
                _apply_defaults = globals()['apply_defaults']
                _apply_defaults(param_dict, leave_defaults=leave_defaults)

        specs = OrderedDict()
        for k, v in param_dict.iteritems():
            specs[k] = spec_type(self, k, **(fix_kwargs(v)))

        return specs

    @classmethod
    def init_params(cls):
        """Return a dictionary describing the parameters accepted by __init__"""

        argspec = inspect.getargspec(cls.__init__)
        if argspec.defaults:
            defaults = dict(zip(argspec.args[-len(argspec.defaults):], argspec.defaults))
        else:
            defaults = {}

        params = OrderedDict()
        for op, param, value in re.findall(
            "^\s*:(type|param|yaml_param|yaml_block_style)\s+(\S+):\s*(.*)$",
            cls.__init__.__doc__,
            flags=re.MULTILINE
        ):
            if param not in params:
                params[param] = {'description': None,
                                 'type': None,
                                 'yaml_param': param,
                                 'yaml_block_style': False}
                if param in defaults:
                    params[param]['default'] = defaults[param]

            if op == 'type':
                params[param]['type'] = value

                if 'default' not in params[param] or \
                   params[param]['default'] is None:
                    # For certain types, we know that None doesn't really mean
                    # None.
                    if params[param]['type'].startswith("dict"):
                        params[param]['default'] = {}
                    elif params[param]['type'].startswith("list"):
                        params[param]['default'] = []
                    elif params[param]['type'].startswith("SpecsParameter("):
                        params[param]['default'] = {}
            elif op == 'yaml_param':
                params[param]['yaml_param'] = value
            elif op == 'yaml_block_style':
                params[param]['yaml_block_style'] = bool(value)
            else:
                params[param]['description'] = value

        return params

    def __eq__(self, other, ignore_params=[]):
        if type(self) != type(other):
            return False

        params = self.init_params()
        for p in params:
            if p in ignore_params:
                continue

            default_p = '_%s_defaultvalue' % p
            self_val = getattr(self, p)
            other_val = getattr(other, p)
            self_val_or_default = self_val or getattr(self, default_p, None)
            other_val_or_default = other_val or getattr(other, default_p, None)

            # Order doesn't matter, for purposes of comparison.  Cast it away.
            if isinstance(self_val, collections.OrderedDict):
                self_val = dict(self_val)

            if isinstance(other_val, collections.OrderedDict):
                other_val = dict(other_val)

            if isinstance(self_val_or_default, collections.OrderedDict):
                self_val_or_default = dict(self_val_or_default)

            if isinstance(other_val_or_default, collections.OrderedDict):
                other_val_or_default = dict(other_val_or_default)

            if self_val == other_val:
                continue

            if self_val_or_default != other_val_or_default:
                LOG.debug("Comparing %s to %s, parameter %s does not match (%s != %s)",
                          self, other, p, self_val_or_default, other_val_or_default)
                return False

        return True

    def __ne__(self, other):
        return not self.__eq__(other)


class ZenPackSpec(Spec):

    """Representation of a ZenPack's desired configuration.

    Intended to be used to build a ZenPack declaratively as in the
    following example in a ZenPack's __init__.py:

        from . import zenpacklib

        CFG = zenpacklib.ZenPackSpec(
            name=__name__,

            zProperties={
                'zCiscoAPICHost': {
                    'category': 'Cisco APIC',
                    'type': 'string',
                },
                'zCiscoAPICPort': {
                    'category': 'Cisco APIC',
                    'default': '80',
                },
            },

            classes={
                'APIC': {
                    'base': zenpacklib.Device,
                },
                'FabricPod': {
                    'meta_type': 'Cisco APIC Fabric Pod',
                    'base': zenpacklib.Component,
                },
                'FvTenant': {
                    'meta_type': 'Cisco APIC Tenant',
                    'base': zenpacklib.Component,
                },
            },

            class_relationships=zenpacklib.relationships_from_yuml((
                "[APIC]++-[FabricPod]",
                "[APIC]++-[FvTenant]",
            ))
        )

        CFG.create()

    """

    def __init__(
            self,
            name,
            zProperties=None,
            classes=None,
            class_relationships=None,
            device_classes=None,
            _source_location=None):
        """
            Create a ZenPack Specification

            :param name: Full name of the ZenPack (ZenPacks.zenoss.MyZenPack)
            :type name: str
            :param zProperties: zProperty Specs
            :type zProperties: SpecsParameter(ZPropertySpec)
            :param class_relationships: Class Relationship Specs
            :type class_relationships: list(RelationshipSchemaSpec)
            :yaml_block_style class_relationships: True
            :param device_classes: DeviceClass Specs
            :type device_classes: SpecsParameter(DeviceClassSpec)
            :param classes: Class Specs
            :type classes: SpecsParameter(ClassSpec)
        """
        super(ZenPackSpec, self).__init__(_source_location=_source_location)

        # The parameters from which this zenpackspec was originally
        # instantiated.
        self.specparams = ZenPackSpecParams(
            name,
            zProperties=zProperties,
            classes=classes,
            class_relationships=class_relationships,
            device_classes=device_classes)

        self.name = name
        self.id_prefix = name.replace(".", "_")

        self.NEW_COMPONENT_TYPES = []
        self.NEW_RELATIONS = collections.defaultdict(list)

        # zProperties
        self.zProperties = self.specs_from_param(
            ZPropertySpec, 'zProperties', zProperties)

        # Class Relationship Schema
        self.class_relationships = []
        if class_relationships:
            if not isinstance(class_relationships, list):
                raise ValueError("class_relationships must be a list, not a %s" % type(class_relationships))

            for rel in class_relationships:
                self.class_relationships.append(RelationshipSchemaSpec(self, **rel))

        # Classes
        self.classes = self.specs_from_param(ClassSpec, 'classes', classes)
        self.imported_classes = {}

        # Import any external classes referred to in the schema
        for rel in self.class_relationships:
            for relschema in (rel.left_schema, rel.right_schema):
                className = relschema.remoteClass
                if '.' in className and className.split('.')[-1] not in self.classes:
                    module = ".".join(className.split('.')[0:-1])
                    try:
                        kls = importClass(module)
                        self.imported_classes[className] = kls
                    except ImportError:
                        pass

        # Class Relationships
        if classes:
            for classname, classdata in classes.iteritems():
                if 'relationships' not in classdata:
                    classdata['relationships'] = []

                relationships = classdata['relationships']
                for relationship in relationships:
                        # We do not allow the schema to be specified directly.
                        if 'schema' in relationships[relationship]:
                            raise ValueError("Class '%s': 'schema' may not be defined or modified in an individual class's relationship.  Use the zenpack's class_relationships instead." % classname)

        for class_ in self.classes.values():

            # Link the appropriate predefined (class_relationships) schema into place on this class's relationships list.
            for rel in self.class_relationships:
                if class_.name == rel.left_class:
                    if rel.left_relname not in class_.relationships:
                        class_.relationships[rel.left_relname] = ClassRelationshipSpec(class_, rel.left_relname)
                    class_.relationships[rel.left_relname].schema = rel.left_schema

                if class_.name == rel.right_class:
                    if rel.right_relname not in class_.relationships:
                        class_.relationships[rel.right_relname] = ClassRelationshipSpec(class_, rel.right_relname)
                    class_.relationships[rel.right_relname].schema = rel.right_schema

            # Plumb _relations
            for relname, relationship in class_.relationships.iteritems():
                if not relationship.schema:
                    LOG.error("Class '%s': no relationship schema has been defined for relationship '%s'" % (class_.name, relname))
                    continue

                if relationship.schema.remoteClass in self.imported_classes.keys():
                    remoteClass = relationship.schema.remoteClass  # Products.ZenModel.Device.Device
                    relname = relationship.schema.remoteName  # coolingFans
                    modname = relationship.class_.model_class.__module__  # ZenPacks.zenoss.HP.Proliant.CoolingFan
                    className = relationship.class_.model_class.__name__  # CoolingFan
                    remoteClassObj = self.imported_classes[remoteClass]  # Device_obj
                    remoteType = relationship.schema.remoteType  # ToManyCont
                    localType = relationship.schema.__class__  # ToOne
                    remote_relname = relationship.zenrelations_tuple[0]  # products_zenmodel_device_device

                    if relname not in (x[0] for x in remoteClassObj._relations):
                        remoteClassObj._relations += ((relname, remoteType(localType, modname, remote_relname)),)

                    remote_module_id = remoteClassObj.__module__
                    if relname not in self.NEW_RELATIONS[remote_module_id]:
                        self.NEW_RELATIONS[remote_module_id].append(relname)

                    component_type = '.'.join((modname, className))
                    if component_type not in self.NEW_COMPONENT_TYPES:
                        self.NEW_COMPONENT_TYPES.append(component_type)

        # Device Classes
        self.device_classes = self.specs_from_param(
            DeviceClassSpec, 'device_classes', device_classes)

    @property
    def ordered_classes(self):
        """Return ordered list of ClassSpec instances."""
        return sorted(self.classes.values(), key=operator.attrgetter('order'))

    def create(self):
        """Implement specification."""
        self.create_zenpack_class()

        for spec in self.zProperties.itervalues():
            spec.create()

        for spec in self.classes.itervalues():
            spec.create()

        self.create_product_names()
        self.create_ordered_component_tree()
        self.create_global_js_snippet()
        self.create_device_js_snippet()
        self.register_browser_resources()
        self.apply_platform_patches()

    def create_product_names(self):
        """Add all classes to ZenPack's productNames list.

        This allows zenchkschema to verify the relationship schemas
        created by create().

        """
        productNames = getattr(self.zenpack_module, 'productNames', [])
        self.zenpack_module.productNames = list(
            set(list(self.classes.iterkeys()) + list(productNames)))

    def create_ordered_component_tree(self):
        """Monkeypatch DeviceRouter.getComponentTree to order components."""
        device_meta_types = {
            x.meta_type
            for x in self.classes.itervalues()
            if x.is_device}

        order = {
            x.meta_type: float(x.order)
            for x in self.classes.itervalues()}

        def getComponentTree(self, uid=None, id=None, **kwargs):
            # We do our own sorting.
            kwargs.pop('sorting_dict', None)

            # original is injected by monkeypatch.
            result = original(self, uid=uid, id=id, **kwargs)

            # Only change the order for custom device types.
            meta_type = self._getFacade().getInfo(uid=uid).meta_type
            if meta_type not in device_meta_types:
                return result

            return sorted(result, key=lambda x: order.get(x['id'], 100.0))

        monkeypatch(DeviceRouter)(getComponentTree)

    def register_browser_resources(self):
        """Register browser resources if they exist."""
        zenpack_path = get_zenpack_path(self.name)
        if not zenpack_path:
            return

        resource_path = os.path.join(zenpack_path, 'resources')
        if not os.path.isdir(resource_path):
            return

        directives = []
        directives.append(
            '<resourceDirectory name="{name}" directory="{directory}"/>'
            .format(
                name=self.name,
                directory=resource_path))

        def get_directive(name, for_, weight):
            path = os.path.join(resource_path, '{}.js'.format(name))
            if not os.path.isfile(path):
                return

            return (
                '<viewlet'
                '    name="js-{zenpack_name}-{name}"'
                '    paths="/++resource++{zenpack_name}/{name}.js"'
                '    for="{for_}"'
                '    weight="{weight}"'
                '    manager="Products.ZenUI3.browser.interfaces.IJavaScriptSrcManager"'
                '    class="Products.ZenUI3.browser.javascript.JavaScriptSrcBundleViewlet"'
                '    permission="zope.Public"'
                '    />'
                .format(
                    name=name,
                    for_=for_,
                    weight=weight,
                    zenpack_name=self.name))

        directives.append(get_directive('global', '*', 20))

        for spec in self.ordered_classes:
            if spec.is_device:
                for_ = get_symbol_name(self.name, spec.name, spec.name)

                directives.append(get_directive('device', for_, 21))
                directives.append(get_directive(spec.name, for_, 22))

        # Eliminate None items from list of directives.
        directives = tuple(x for x in directives if x)

        if directives:
            zcml.load_string(
                '<configure xmlns="http://namespaces.zope.org/browser">'
                '<include package="Products.Five" file="meta.zcml"/>'
                '<include package="Products.Five.viewlet" file="meta.zcml"/>'
                '{directives}'
                '</configure>'
                .format(
                    name=self.name,
                    directory=resource_path,
                    directives=''.join(directives)))

    def apply_platform_patches(self):
        """Apply necessary patches to platform code."""
        self.apply_zen21467_patch()

    def apply_zen21467_patch(self):
        """Patch cause of ZEN-21467 issue.

        The problem is that zenpacklib sets string property values to unicode
        strings instead of regular strings. There's a platform bug that
        prevents unicode values from being serialized to be used by zenjmx.
        This means that JMX datasources won't work without this patch.

        """
        try:
            from Products.ZenHub.XmlRpcService import XmlRpcService
            if types.UnicodeType not in XmlRpcService.PRIMITIVES:
                XmlRpcService.PRIMITIVES.append(types.UnicodeType)
        except Exception:
            # The above may become wrong in future platform versions.
            pass

    def create_js_snippet(self, name, snippet, classes=None):
        """Create, register and return JavaScript snippet for given classes."""
        if isinstance(classes, (list, tuple)):
            classes = tuple(classes)
        else:
            classes = (classes,)

        def snippet_method(self):
            return snippet

        attributes = {
            '__allow_access_to_unprotected_subobjects__': True,
            'weight': 20,
            'snippet': snippet_method,
            }

        snippet_class = create_class(
            get_symbol_name(self.name),
            get_symbol_name(self.name, 'schema'),
            name,
            (JavaScriptSnippet,),
            attributes)

        try:
            target_name = 'global' if classes[0] is None else 'device'
        except Exception:
            target_name = 'global'

        for klass in classes:
            GSM.registerAdapter(
                snippet_class,
                (klass,) + (IDefaultBrowserLayer, IBrowserView, IMainSnippetManager),
                IViewlet,
                'js-snippet-{name}-{target_name}'
                .format(
                    name=self.name,
                    target_name=target_name))

        return snippet_class

    def create_global_js_snippet(self):
        """Create and register global JavaScript snippet."""
        snippets = []
        for spec in self.ordered_classes:
            snippets.append(spec.global_js_snippet)

        snippet = (
            "(function(){{\n"
            "var ZC = Ext.ns('Zenoss.component');\n"
            "{snippets}"
            "}})();\n"
            .format(
                snippets=''.join(snippets)))

        return self.create_js_snippet('global', snippet)

    def create_device_js_snippet(self):
        """Register device JavaScript snippet."""
        snippets = []
        for spec in self.ordered_classes:
            snippets.append(spec.device_js_snippet)

        # Don't register the snippet if there's nothing in it.
        if not [x for x in snippets if x]:
            return

        link_code = JS_LINK_FROM_GRID.replace('{zenpack_id_prefix}', self.id_prefix)
        snippet = (
            "(function(){{\n"
            "var ZC = Ext.ns('Zenoss.component');\n"
            "{link_code}\n"
            "{snippets}"
            "}})();\n"
            .format(
                link_code=link_code,
                snippets=''.join(snippets)))

        device_classes = [
            x.model_class
            for x in self.classes.itervalues()
            if Device in x.resolved_bases]

        # Add imported device objects
        for kls in self.imported_classes.itervalues():
            if 'deviceClass' in [x[0] for x in kls._relations]:
                device_classes.append(kls)

        return self.create_js_snippet(
            'device', snippet, classes=device_classes)

    @property
    def zenpack_module(self):
        """Return ZenPack module."""
        return importlib.import_module(self.name)

    @property
    def zenpack_class(self):
        """Return ZenPack class."""
        return self.create_zenpack_class()

    @memoize
    def create_zenpack_class(self):
        """Create ZenPack class."""
        packZProperties = [
            x.packZProperties for x in self.zProperties.itervalues()]

        attributes = {
            'packZProperties': packZProperties
            }

        attributes['device_classes'] = self.device_classes
        attributes['_v_specparams'] = self.specparams
        attributes['NEW_COMPONENT_TYPES'] = self.NEW_COMPONENT_TYPES
        attributes['NEW_RELATIONS'] = self.NEW_RELATIONS
        attributes['GLOBAL_CATALOGS'] = []
        global_catalog_classes = {}
        for (class_, class_spec) in self.classes.items():
            for (p, property_spec) in class_spec.properties.items():
                if property_spec.index_scope in ('both', 'global'):
                    global_catalog_classes[class_] = True
                    continue
        for class_ in global_catalog_classes:
            catalog = ".".join([self.name, class_]).replace(".", "_")
            attributes['GLOBAL_CATALOGS'].append('{}Search'.format(catalog))

        return create_class(get_symbol_name(self.name),
                            get_symbol_name(self.name, 'schema'),
                            'ZenPack',
                            (ZenPack,),
                            attributes)

    def test_setup(self):
        """Execute from a test suite's afterSetUp method.

        Our test layer appears to wipe out adapter registrations. We
        call this again after the layer has been setup so that
        programatically-registered adapters are in place for testing.

        """
        for spec in self.classes.itervalues():
            spec.test_setup()

        self.create_global_js_snippet()
        self.create_device_js_snippet()


class DeviceClassSpec(Spec):

    """Initialize a DeviceClass via Python at install time."""

    def __init__(
            self,
            zenpack_spec,
            path,
            create=True,
            zProperties=None,
            remove=False,
            templates=None,
            _source_location=None):
        """
            Create a DeviceClass Specification

            :param create: Create the DeviceClass with ZenPack installation, if it does not exist?
            :type create: bool
            :param remove: Remove the DeviceClass when ZenPack is removed?
            :type remove: bool
            :param zProperties: zProperty values to set upon this DeviceClass
            :type zProperties: dict(str)
            :param templates: TODO
            :type templates: SpecsParameter(RRDTemplateSpec)
        """
        super(DeviceClassSpec, self).__init__(_source_location=_source_location)

        self.zenpack_spec = zenpack_spec
        self.path = path.lstrip('/')
        self.create = bool(create)
        self.remove = bool(remove)

        if zProperties is None:
            self.zProperties = {}
        else:
            self.zProperties = zProperties

        self.templates = self.specs_from_param(
            RRDTemplateSpec, 'templates', templates)


class ZPropertySpec(Spec):

    """TODO."""

    def __init__(
            self,
            zenpack_spec,
            name,
            type_='string',
            default=None,
            category=None,
            _source_location=None
            ):
        """
            Create a ZProperty Specification

            :param type_: ZProperty Type (boolean, int, float, string, password, or lines)
            :yaml_param type_: type
            :type type_: str
            :param default: Default Value
            :type default: ZPropertyDefaultValue
            :param category: ZProperty Category.  This is used for display/sorting purposes.
            :type category: str
        """
        super(ZPropertySpec, self).__init__(_source_location=_source_location)

        self.zenpack_spec = zenpack_spec
        self.name = name
        self.type_ = type_
        self.category = category

        if default is None:
            self.default = {
                'string': '',
                'password': '',
                'lines': [],
                'boolean': False,
                }.get(self.type_, None)
        else:
            self.default = default

    def create(self):
        """Implement specification."""
        if self.category:
            setzPropertyCategory(self.name, self.category)

    @property
    def packZProperties(self):
        """Return packZProperties tuple for this zProperty."""
        return (self.name, self.default, self.type_)


class ClassSpec(Spec):

    """TODO.


    'impacts' and 'impacted_by' will cause impact adapters to be registered, so the
    relationship is shown in impact, but not in dynamicview. If you would like to
    use dynamicview, you should change:

        'MyComponent': {
            'impacted_by': ['someRelationship']
            'impacts': ['someThingElse']
        }

    To:

        'MyComponent': {
            'dynamicview_views': ['service_view'],
            'dynamicview_relations': {
                'impacted_by': ['someRelationship']
                'impacts': ['someThingElse']
            }
        }

    This will cause your impact relationship to show in both dynamicview and impact.

    There is one important exception though.  Until ZEN-14579 is fixed, if your
    relationship/method returns an object that is not itself part of service_view,
    the dynamicview -> impact export will not include that object.

    To fix this, you must use impacts/impact_by for such relationships:

        'MyComponent': {
            'dynamicview_views': ['service_view'],
            'dynamicview_relations': {
                'impacted_by': ['someRelationship']
                'impacts': ['someThingElse']
            }
            impacted_by': ['someRelationToANonServiceViewThing']
        }

    If you need the object to appear in both DV and impact, include it in both lists.  If
    it would already be exported to impact, because it is in service_view, only use
    dynamicview_relations -> impacts/impacted_by, to avoid slowing down performance due
    to double adapters doing the same thing.
    """

    def __init__(
            self,
            zenpack,
            name,
            base=Component,
            meta_type=None,
            label=None,
            plural_label=None,
            short_label=None,
            plural_short_label=None,
            auto_expand_column='name',
            label_width=80,
            plural_label_width=None,
            content_width=None,
            icon=None,
            order=None,
            properties=None,
            relationships=None,
            impacts=None,
            impacted_by=None,
            monitoring_templates=None,
            filter_display=True,
            filter_hide_from=None,
            dynamicview_views=None,
            dynamicview_group=None,
            dynamicview_relations=None,
            extra_paths=None,
            _source_location=None
            ):
        """
            Create a Class Specification

            :param base: Base Class (defaults to Component)
            :type base: list(class)
            :param meta_type: meta_type (defaults to class name)
            :type meta_type: str
            :param label: Label to use when describing this class in the
                   UI.  If not specified, the default is to use the class name.
            :type label: str
            :param plural_label: Plural form of the label (default is to use the
                  "pluralize" function on the label)
            :type plural_label: str
            :param short_label: If specified, this is a shorter version of the
                   label.
            :type short_label: str
            :param plural_short_label:  If specified, this is a shorter version
                   of the short_label.
            :type plural_short_label: str
            :param auto_expand_column: The name of the column to expand to fill
                   available space in the grid display.  Defaults to the first
                   column ('name').
            :type auto_expand_column: str
            :param label_width: Optionally overrides ZPL's label width
                   calculation with a higher value.
            :type label_width: int
            :param plural_label_width: Optionally overrides ZPL's label width
                   calculation with a higher value.
            :type plural_label_width: int
            :param content_width: Optionally overrides ZPL's content width
                   calculation with a higher value.
            :type content_width: int
            :param icon: Filename (of a file within the zenpack's 'resources/icon'
                   directory).  Default is the {class name}.png
            :type icon: str
            :param order: TODO
            :type order: float
            :param properties: TODO
            :type properties: SpecsParameter(ClassPropertySpec)
            :param relationships: TODO
            :type relationships: SpecsParameter(ClassRelationshipSpec)
            :param impacts: TODO
            :type impacts: list(str)
            :param impacted_by: TODO
            :type impacted_by: list(str)
            :param monitoring_templates: TODO
            :type monitoring_templates: list(str)
            :param filter_display: Should this class show in any other filter dropdowns?
            :type filter_display: bool
            :param filter_hide_from: Classes for which this class should not show in the filter dropdown.
            :type filter_hide_from: list(class)
            :param dynamicview_views: TODO
            :type dynamicview_views: list(str)
            :param dynamicview_group: TODO
            :type dynamicview_group: str
            :param dynamicview_relations: TODO
            :type dynamicview_relations: dict
            :param extra_paths: TODO
            :type extra_paths: list(ExtraPath)

        """
        super(ClassSpec, self).__init__(_source_location=_source_location)

        self.zenpack = zenpack
        self.name = name

        # Verify that bases is a tuple of base types.
        if isinstance(base, (tuple, list, set)):
            bases = tuple(base)
        else:
            bases = (base,)

        self.bases = bases
        self.base = self.bases

        self.meta_type = meta_type or self.name
        self.label = label or self.meta_type
        self.plural_label = plural_label or pluralize(self.label)

        if short_label:
            self.short_label = short_label
            self.plural_short_label = plural_short_label or pluralize(self.short_label)
        else:
            self.short_label = self.label
            self.plural_short_label = plural_short_label or self.plural_label

        self.auto_expand_column = auto_expand_column

        self.label_width = int(label_width)
        self.plural_label_width = plural_label_width or self.label_width + 7
        self.content_width = content_width or label_width

        self.icon = icon

        # Force properties into the 5.0 - 5.9 order range.
        if not order:
            self.order = 5.5
        else:
            self.order = 5 + (max(0, min(100, order)) / 100.0)

        # Properties.
        self.properties = self.specs_from_param(
            ClassPropertySpec, 'properties', properties)

        # Relationships.
        self.relationships = self.specs_from_param(
            ClassRelationshipSpec, 'relationships', relationships)

        # Impact.
        self.impacts = impacts
        self.impacted_by = impacted_by

        # Monitoring Templates.
        if monitoring_templates is None:
            self.monitoring_templates = [self.label.replace(' ', '')]
        elif isinstance(monitoring_templates, basestring):
            self.monitoring_templates = [monitoring_templates]
        else:
            self.monitoring_templates = list(monitoring_templates)

        self.filter_display = filter_display
        self.filter_hide_from = filter_hide_from

        # Dynamicview Views and Group
        if dynamicview_views is None:
            self.dynamicview_views = ['service_view']
        elif isinstance(dynamicview_views, basestring):
            self.dynamicview_views = [dynamicview_views]
        else:
            self.dynamicview_views = list(dynamicview_views)

        if dynamicview_group is None:
            self.dynamicview_group = self.plural_short_label
        else:
            self.dynamicview_group = dynamicview_group

        # additional relationships to add, beyond IMPACTS and IMPACTED_BY.
        if dynamicview_relations is None:
            self.dynamicview_relations = {}
        else:
            # TAG_NAME: ['relationship', 'or_method']
            self.dynamicview_relations = dict(dynamicview_relations)

        # Paths
        self.path_pattern_streams = []
        if extra_paths is not None:
            self.extra_paths = extra_paths
            for pattern_tuple in extra_paths:
                # Each item in extra_paths is expressed as a tuple of
                # regular expression patterns that are matched
                # in order against the actual relationship path structure
                # as it is traversed and built up get_facets.
                #
                # To facilitate matching, we construct a compiled set of
                # regular expressions that can be matched against the
                # entire path string, from root to leaf.
                #
                # So:
                #
                #   ('orgComponent', '(parentOrg)+')
                # is transformed into a "pattern stream", which is a list
                # of regexps that can be applied incrementally as we traverse
                # the possible paths:
                #   (re.compile(^orgComponent),
                #    re.compile(^orgComponent/(parentOrg)+),
                #    re.compile(^orgComponent/(parentOrg)+/?$')
                #
                # Once traversal embarks upon a stream, these patterns are
                # matched in order as the traversal proceeds, with the
                # first one to fail causing recursion to stop.
                # When the final one is matched, then the objects on that
                # relation are matched.  Note that the final one may
                # match multiple times if recursive relationships are
                # in play.

                pattern_stream = []
                for i, _ in enumerate(pattern_tuple, start=1):
                    pattern = "^" + "/".join(pattern_tuple[0:i])
                    # If we match these patterns, keep going.
                    pattern_stream.append(re.compile(pattern))
                if pattern_stream:
                    # indicate that we've hit the end of the path.
                    pattern_stream.append(re.compile("/?$"))

                self.path_pattern_streams.append(pattern_stream)
        else:
            self.extra_paths = []

    def create(self):
        """Implement specification."""
        self.create_model_schema_class()
        self.create_iinfo_schema_class()
        self.create_info_schema_class()

        self.create_model_class()
        self.create_iinfo_class()
        self.create_info_class()

        if self.is_component or self.is_hardware_component:
            self.create_formbuilder_class()

        self.register_dynamicview_adapters()
        self.register_impact_adapters()

    @property
    @memoize
    def resolved_bases(self):
        """Return tuple of base classes.

        This is different than ClassSpec.bases in that all elements of
        the tuple will be type instances. ClassSpec.bases may contain
        string representations of types.
        """
        resolved_bases = []
        for base in self.bases:
            if isinstance(base, type):
                resolved_bases.append(base)
            elif base not in self.zenpack.classes:
                raise ValueError("Unrecognized base class name '%s'" % base)
            else:
                base_spec = self.zenpack.classes[base]
                resolved_bases.append(base_spec.model_class)

        return tuple(resolved_bases)

    def base_class_specs(self, recursive=False):
        """Return tuple of base ClassSpecs.

        Iterates over ClassSpec.bases (possibly recursively) and returns
        instances of the ClassSpec objects for them.
        """
        base_specs = []
        for base in self.bases:
            if isinstance(base, type):
                # bases will contain classes rather than class names when referring
                # to a class outside of this zenpack specification.  Ignore
                # these.
                continue

            class_spec = self.zenpack.classes[base]
            base_specs.append(class_spec)

            if recursive:
                base_specs.extend(class_spec.base_class_specs())

        return tuple(base_specs)

    def subclass_specs(self):
        subclass_specs = []
        for class_spec in self.zenpack.classes.values():
            if self in class_spec.base_class_specs(recursive=True):
                subclass_specs.append(class_spec)

        return subclass_specs

    @property
    def filter_hide_from_class_specs(self):
        specs = []
        if self.filter_hide_from is None:
            return specs

        for classname in self.filter_hide_from:
            if classname not in self.zenpack.classes:
                raise ValueError("Unrecognized filter_hide_from class name '%s'" % classname)
            class_spec = self.zenpack.classes[classname]
            specs.append(class_spec)

        return specs

    def inherited_properties(self):
        properties = {}
        for base in self.bases:
            if not isinstance(base, type):
                class_spec = self.zenpack.classes[base]
                properties.update(class_spec.inherited_properties())

        properties.update(self.properties)

        return properties

    def inherited_relationships(self):
        relationships = {}
        for base in self.bases:
            if not isinstance(base, type):
                class_spec = self.zenpack.classes[base]
                relationships.update(class_spec.inherited_relationships())

        relationships.update(self.relationships)

        return relationships

    def is_a(self, type_):
        """Return True if this class is a subclass of type_."""
        return issubclass(self.model_schema_class, type_)

    @property
    def is_device(self):
        """Return True if this class is a Device."""
        return self.is_a(Device)

    @property
    def is_component(self):
        """Return True if this class is a Component."""
        return self.is_a(Component)

    @property
    def is_hardware_component(self):
        """Return True if this class is a HardwareComponent."""
        return self.is_a(HardwareComponent)

    @property
    def icon_url(self):
        """Return relative URL to icon."""
        icon_filename = self.icon or '{}.png'.format(self.name)

        icon_path = os.path.join(
            get_zenpack_path(self.zenpack.name),
            'resources',
            'icon',
            icon_filename)

        if os.path.isfile(icon_path):
            return '/++resource++{zenpack_name}/icon/{filename}'.format(
                zenpack_name=self.zenpack.name,
                filename=icon_filename)

        return '/zport/dmd/img/icons/noicon.png'

    @property
    def model_schema_class(self):
        """Return model schema class."""
        return self.create_model_schema_class()

    def create_model_schema_class(self):
        """Create and return model schema class."""
        attributes = {
            'zenpack_name': self.zenpack.name,
            'meta_type': self.meta_type,
            'portal_type': self.meta_type,
            'icon_url': self.icon_url,
            'class_label': self.label,
            'class_plural_label': self.plural_label,
            'class_short_label': self.short_label,
            'class_plural_short_label': self.plural_short_label,
            'class_dynamicview_group': self.dynamicview_group,
            }

        properties = []
        relations = []
        templates = []
        catalogs = {}

        # First inherit from bases.
        for base in self.resolved_bases:
            if hasattr(base, '_properties'):
                properties.extend(base._properties)
            if hasattr(base, '_templates'):
                templates.extend(base._templates)
            if hasattr(base, '_catalogs'):
                catalogs.update(base._catalogs)

        # Add local properties and catalog indexes.
        for name, spec in self.properties.iteritems():
            if spec.api_backendtype == 'property':
                # for normal properties (not methods or datapoints, apply default value)
                attributes[name] = spec.default  # defaults to None

            elif spec.datapoint:
                # Provide a method to look up the datapoint and get the value from rrd
                def datapoint_method(self, default=spec.datapoint_default, cached=spec.datapoint_cached, datapoint=spec.datapoint):
                    if cached:
                        r = self.cacheRRDValue(datapoint, default=default)
                    else:
                        r = self.getRRDValue(datapoint, default=default)

                    if r is not None:
                        if not math.isnan(float(r)):
                            return r
                    return default

                attributes[name] = datapoint_method

            else:
                # api backendtype is 'method', and it is assumed that this
                # pre-existing method is being inherited from a parent class
                # or will be provided by the developer.  In any case, we want
                # to omit it from the generated schema class, so that we don't
                # shadow an existing method with a property with a default
                # value of 'None.'
                pass

            if spec.ofs_dict:
                properties.append(spec.ofs_dict)

            pindexes = spec.catalog_indexes
            if pindexes:
                if self.name not in catalogs:
                    catalogs[self.name] = {
                        'indexes': {
                            'id': {'type': 'field'},
                        }
                    }
                catalogs[self.name]['indexes'].update(pindexes)

        # Add local relations.
        for name, spec in self.relationships.iteritems():
            relations.append(spec.zenrelations_tuple)

            # Add getter and setter to allow modeling. Only for local
            # relationships because base classes will provide methods
            # for their relationships.
            attributes['get_{}'.format(name)] = RelationshipGetter(name)
            attributes['set_{}'.format(name)] = RelationshipSetter(name)

        # Add local templates.
        templates.extend(self.monitoring_templates)

        attributes['_properties'] = tuple(properties)
        attributes['_v_local_relations'] = tuple(relations)
        attributes['_templates'] = tuple(templates)
        attributes['_catalogs'] = catalogs

        # Add Impact stuff.
        attributes['impacts'] = self.impacts
        attributes['impacted_by'] = self.impacted_by
        attributes['dynamicview_relations'] = self.dynamicview_relations

        # And facet patterns.
        if self.path_pattern_streams:
            attributes['_v_path_pattern_streams'] = self.path_pattern_streams

        return create_schema_class(
            get_symbol_name(self.zenpack.name, 'schema'),
            self.name,
            self.resolved_bases,
            attributes)

    @property
    def model_class(self):
        """Return model class."""
        return self.create_model_class()

    def create_model_class(self):
        """Create and return model class."""
        return create_stub_class(
            get_symbol_name(self.zenpack.name, self.name),
            self.model_schema_class,
            self.name)

    @property
    def iinfo_schema_class(self):
        """Return I<name>Info schema class."""
        return self.create_iinfo_schema_class()

    def create_iinfo_schema_class(self):
        """Create and return I<name>Info schema class."""
        bases = []
        for base_classname in self.zenpack.classes[self.name].bases:
            if base_classname in self.zenpack.classes:
                bases.append(self.zenpack.classes[base_classname].iinfo_class)

        if not bases:
            if self.is_device:
                bases = [IBaseDeviceInfo]
            elif self.is_component:
                bases = [IBaseComponentInfo]
            elif self.is_hardware_component:
                bases = [IHardwareComponentInfo]
            else:
                bases = [IInfo]

        attributes = {}

        for spec in self.inherited_properties().itervalues():
            attributes.update(spec.iinfo_schemas)

        for i, spec in enumerate(self.containing_components):
            attr = relname_from_classname(spec.name)
            attributes[attr] = schema.Entity(
                title=_t(spec.label),
                group="Relationships",
                order=3 + i / 100.0)

        for spec in self.inherited_relationships().itervalues():
            attributes.update(spec.iinfo_schemas)

        return create_schema_class(
            get_symbol_name(self.zenpack.name, 'schema'),
            'I{}Info'.format(self.name),
            tuple(bases),
            attributes)

    @property
    def iinfo_class(self):
        """Return I<name>Info class."""
        return self.create_iinfo_class()

    def create_iinfo_class(self):
        """Create and return I<Info>Info class."""
        return create_stub_class(
            get_symbol_name(self.zenpack.name, self.name),
            self.iinfo_schema_class,
            'I{}Info'.format(self.name))

    @property
    def info_schema_class(self):
        """Return <name>Info schema class."""
        return self.create_info_schema_class()

    def create_info_schema_class(self):
        """Create and return <name>Info schema class."""
        bases = []
        for base_classname in self.zenpack.classes[self.name].bases:
            if base_classname in self.zenpack.classes:
                bases.append(self.zenpack.classes[base_classname].info_class)

        if not bases:
            if self.is_device:
                bases = [BaseDeviceInfo]
            elif self.is_component:
                bases = [BaseComponentInfo]
            elif self.is_hardware_component:
                bases = [HardwareComponentInfo]
            else:
                bases = [InfoBase]

        attributes = {}
        attributes.update({
            'class_label': ProxyProperty('class_label'),
            'class_plural_label': ProxyProperty('class_plural_label'),
            'class_short_label': ProxyProperty('class_short_label'),
            'class_plural_short_label': ProxyProperty('class_plural_short_label')
        })

        for spec in self.containing_components:
            attr = None
            for rel, spec in self.relationships.items():
                if spec.remote_classname == spec.name:
                    attr = rel
                    continue

            if not attr:
                attr = relname_from_classname(spec.name)

            attributes[attr] = RelationshipInfoProperty(attr)

        for spec in self.inherited_properties().itervalues():
            attributes.update(spec.info_properties)

        for spec in self.inherited_relationships().itervalues():
            attributes.update(spec.info_properties)

        return create_schema_class(
            get_symbol_name(self.zenpack.name, 'schema'),
            '{}Info'.format(self.name),
            tuple(bases),
            attributes)

    @property
    def info_class(self):
        """Return Info subclass."""
        return self.create_info_class()

    def create_info_class(self):
        """Create and return Info subclass."""
        info_class = create_stub_class(
            get_symbol_name(self.zenpack.name, self.name),
            self.info_schema_class,
            '{}Info'.format(self.name))

        classImplements(info_class, self.iinfo_class)
        GSM.registerAdapter(info_class, (self.model_class,), self.iinfo_class)

        return info_class

    @property
    def formbuilder_class(self):
        """Return FormBuilder subclass."""
        return self.create_formbuilder_class()

    def create_formbuilder_class(self):
        """Create and return FormBuilder subclass.

        Includes rendering hints for ComponentFormBuilder.

        """
        bases = (ComponentFormBuilder,)
        attributes = {}
        renderer = {}

        # Find renderers for our properties:
        for propname, spec in self.properties.iteritems():
            renderer[propname] = spec.renderer

        # Find renderers for inherited properties
        for class_spec in self.base_class_specs(recursive=True):
            for propname, spec in class_spec.properties.iteritems():
                renderer[propname] = spec.renderer

        attributes['renderer'] = renderer
        attributes['zenpack_id_prefix'] = self.zenpack.id_prefix

        formbuilder = create_class(
            get_symbol_name(self.zenpack.name, self.name),
            get_symbol_name(self.zenpack.name, 'schema'),
            '{}FormBuilder'.format(self.name),
            tuple(bases),
            attributes)

        classImplements(formbuilder, IFormBuilder)
        GSM.registerAdapter(formbuilder, (self.info_class,), IFormBuilder)

        return formbuilder

    def register_dynamicview_adapters(self):
        if not DYNAMICVIEW_INSTALLED:
            return

        if not self.dynamicview_views:
            return

        GSM.registerAdapter(
            DynamicViewRelatable,
            (self.model_class,),
            IRelatable)

        GSM.registerSubscriptionAdapter(
            DynamicViewRelationsProvider,
            required=(self.model_class,),
            provided=IRelationsProvider)

        dvm = DynamicViewMappings()

        groupName = self.model_class.class_dynamicview_group
        weight = 1000 + (self.order * 100)
        icon_url = getattr(self, 'icon_url', '/zport/dmd/img/icons/noicon.png')

        # Make sure the named utility is also registered.  It seems that
        # during unit tests, it may not be, even if the mapping is still
        # present.
        group = GSM.queryUtility(IGroup, groupName)
        if not group:
            group = BaseGroup(groupName, weight, None, icon_url)
            GSM.registerUtility(group, IGroup, groupName)

        for viewName in self.dynamicview_views:
            if groupName not in dvm.getGroupNames(viewName):
                dvm.addMapping(
                    viewName=viewName,
                    groupName=group.name,
                    weight=group.weight,
                    icon=group.icon)

    def register_impact_adapters(self):
        """Register Impact adapters."""

        if not IMPACT_INSTALLED:
            return

        if self.impacts or self.impacted_by:
            GSM.registerSubscriptionAdapter(
                ImpactRelationshipDataProvider,
                required=(self.model_class,),
                provided=IRelationshipDataProvider)

    @property
    def containing_components(self):
        """Return iterable of containing component ClassSpec instances.

        Instances will be sorted shallow to deep.

        """
        containing_specs = []

        for relname, relschema in self.model_schema_class._relations:
            if not issubclass(relschema.remoteType, ToManyCont):
                continue

            remote_classname = relschema.remoteClass.split('.')[-1]
            remote_spec = self.zenpack.classes.get(remote_classname)
            if not remote_spec or remote_spec.is_device:
                continue

            containing_specs.extend(remote_spec.containing_components)
            containing_specs.append(remote_spec)

        return containing_specs

    @property
    def faceting_components(self):
        """Return iterable of faceting component ClassSpec instances."""
        faceting_specs = []

        for relname, relschema in self.model_class._relations:
            if relname in FACET_BLACKLIST:
                continue

            if not issubclass(relschema.remoteType, ToMany):
                continue

            remote_classname = relschema.remoteClass.split('.')[-1]
            remote_spec = self.zenpack.classes.get(remote_classname)
            if remote_spec:
                for class_spec in [remote_spec] + remote_spec.subclass_specs():
                    if class_spec and not class_spec.is_device:
                        faceting_specs.append(class_spec)

        return faceting_specs

    @property
    def filterable_by(self):
        """Return meta_types by which this class can be filtered."""
        if not self.filter_display:
            return []

        containing = {x.meta_type for x in self.containing_components}
        faceting = {x.meta_type for x in self.faceting_components}
        hidden = {x.meta_type for x in self.filter_hide_from_class_specs}

        return list(containing | faceting - hidden)

    @property
    def containing_js_fields(self):
        """Return list of JavaScript fields for containing components."""
        fields = []

        if self.is_device:
            return fields

        filtered_relationships = {}
        for r in self.relationships.values():
            if r.grid_display is False:
                filtered_relationships[r.remote_classname] = r

        for spec in self.containing_components:
            # grid_display=False
            if spec.name in filtered_relationships:
                continue
            fields.append(
                "{{name: '{}'}}"
                .format(
                    relname_from_classname(spec.name)))

        return fields

    @property
    def containing_js_columns(self):
        """Return list of JavaScript columns for containing components."""
        columns = []

        if self.is_device:
            return columns

        filtered_relationships = {}
        for r in self.relationships.values():
            if r.grid_display is False:
                filtered_relationships[r.remote_classname] = r

        for spec in self.containing_components:
            # grid_display=False
            if spec.name in filtered_relationships:
                continue

            width = max(spec.content_width + 14, spec.label_width + 20)
            renderer = 'Zenoss.render.zenpacklib_{zenpack_id_prefix}_entityLinkFromGrid'.format(
                zenpack_id_prefix=self.zenpack.id_prefix)

            column_fields = [
                "id: '{}'".format(spec.name),
                "dataIndex: '{}'".format(relname_from_classname(spec.name)),
                "header: _t('{}')".format(spec.short_label),
                "width: {}".format(width),
                "renderer: {}".format(renderer),
                ]

            columns.append('{{{}}}'.format(','.join(column_fields)))

        return columns

    @property
    def global_js_snippet(self):
        """Return global JavaScript snippet."""
        return (
            "ZC.registerName("
            "'{meta_type}', _t('{label}'), _t('{plural_label}')"
            ");\n"
            .format(
                meta_type=self.meta_type,
                label=self.label,
                plural_label=self.plural_label))

    @property
    def component_grid_panel_js_snippet(self):
        """Return ComponentGridPanel JavaScript snippet."""
        if self.is_device:
            return ''

        default_fields = [
            "{{name: '{}'}}".format(x) for x in (
                'uid', 'name', 'meta_type', 'class_label', 'status', 'severity',
                'usesMonitorAttribute', 'monitored', 'locking',
                )]

        default_left_columns = [(
            "{"
            "id: 'severity',"
            "dataIndex: 'severity',"
            "header: _t('Events'),"
            "renderer: Zenoss.render.severity,"
            "width: 50"
            "}"
        ), (
            "{"
            "id: 'name',"
            "dataIndex: 'name',"
            "header: _t('Name'),"
            "renderer: Zenoss.render.zenpacklib_" + self.zenpack.id_prefix + "_entityLinkFromGrid"
            "}"
        )]

        default_right_columns = [(
            "{"
            "id: 'monitored',"
            "dataIndex: 'monitored',"
            "header: _t('Monitored'),"
            "renderer: Zenoss.render.checkbox,"
            "width: 70"
            "}"
        ), (
            "{"
            "id: 'locking',"
            "dataIndex: 'locking',"
            "header: _t('Locking'),"
            "renderer: Zenoss.render.locking_icons,"
            "width: 65"
            "}"
        )]

        fields = []
        ordered_columns = []

        # Keep track of pixel width of custom fields. Exceeding a
        # certain width causes horizontal scrolling of the component
        # grid panel.
        width = 0

        for spec in self.inherited_properties().itervalues():
            fields.extend(spec.js_fields)
            ordered_columns.extend(spec.js_columns)
            width += spec.js_columns_width

        for spec in self.inherited_relationships().itervalues():
            fields.extend(spec.js_fields)
            ordered_columns.extend(spec.js_columns)
            width += spec.js_columns_width

        if width > 750:
            LOG.warning(
                "%s: %s custom columns exceed 750 pixels (%s)",
                self.zenpack.name, self.name, width)

        return (
            "ZC.{meta_type}Panel = Ext.extend(ZC.ZPL_{zenpack_id_prefix}_ComponentGridPanel, {{"
            "    constructor: function(config) {{\n"
            "        config = Ext.applyIf(config||{{}}, {{\n"
            "            componentType: '{meta_type}',\n"
            "            autoExpandColumn: '{auto_expand_column}',\n"
            "            fields: [{fields}],\n"
            "            columns: [{columns}]\n"
            "        }});\n"
            "        ZC.{meta_type}Panel.superclass.constructor.call(this, config);\n"
            "    }}\n"
            "}});\n"
            "\n"
            "Ext.reg('{meta_type}Panel', ZC.{meta_type}Panel);\n"
            .format(
                meta_type=self.meta_type,
                zenpack_id_prefix=self.zenpack.id_prefix,
                auto_expand_column=self.auto_expand_column,
                fields=','.join(
                    default_fields +
                    self.containing_js_fields +
                    fields),
                columns=','.join(
                    default_left_columns +
                    self.containing_js_columns +
                    ordered_values(ordered_columns) +
                    default_right_columns)))

    @property
    def subcomponent_nav_js_snippet(self):
        """Return subcomponent navigation JavaScript snippet."""
        cases = []
        for meta_type in self.filterable_by:
            cases.append("case '{}': return true;".format(meta_type))

        if not cases:
            return ''

        return (
            "Zenoss.nav.appendTo('Component', [{{\n"
            "    id: 'component_{meta_type}',\n"
            "    text: _t('{plural_label}'),\n"
            "    xtype: '{meta_type}Panel',\n"
            "    subComponentGridPanel: true,\n"
            "    filterNav: function(navpanel) {{\n"
            "        switch (navpanel.refOwner.componentType) {{\n"
            "            {cases}\n"
            "            default: return false;\n"
            "        }}\n"
            "    }},\n"
            "    setContext: function(uid) {{\n"
            "        ZC.{meta_type}Panel.superclass.setContext.apply(this, [uid]);\n"
            "    }}\n"
            "}}]);\n"
            .format(
                meta_type=self.meta_type,
                plural_label=self.plural_short_label,
                cases=' '.join(cases)))

    @property
    def dynamicview_nav_js_snippet(self):
        if DYNAMICVIEW_INSTALLED:
            return (
                "Zenoss.nav.appendTo('Component', [{\n"
                "    id: 'subcomponent_view',\n"
                "    text: _t('Dynamic View'),\n"
                "    xtype: 'dynamicview',\n"
                "    relationshipFilter: 'impacted_by',\n"
                "    viewName: 'service_view'\n"
                "}]);\n"
                )
        else:
            return ""

    @property
    def device_js_snippet(self):
        """Return device JavaScript snippet."""
        return ''.join((
            self.component_grid_panel_js_snippet,
            self.subcomponent_nav_js_snippet,
            self.dynamicview_nav_js_snippet,
            ))

    def test_setup(self):
        """Execute from a test suite's afterSetUp method.

        Our test layer appears to wipe out adapter registrations. We
        call this again after the layer has been setup so that
        programatically-registered adapters are in place for testing.

        """
        self.create_iinfo_class()
        self.create_info_class()
        self.register_dynamicview_adapters()
        self.register_impact_adapters()


class ClassPropertySpec(Spec):

    """TODO."""

    def __init__(
            self,
            class_spec,
            name,
            type_='string',
            label=None,
            short_label=None,
            index_type=None,
            label_width=80,
            default=None,
            content_width=None,
            display=True,
            details_display=True,
            grid_display=True,
            renderer=None,
            order=None,
            editable=False,
            api_only=False,
            api_backendtype='property',
            enum=None,
            datapoint=None,
            datapoint_default=None,
            datapoint_cached=True,
            index_scope='device',
            _source_location=None
            ):
        """
        Create a Class Property Specification

            :param type_: Property Data Type (TODO (enum))
            :yaml_param type_: type
            :type type_: str
            :param label: Label to use when describing this property in the
                   UI.  If not specified, the default is to use the name of the
                   property.
            :type label: str
            :param short_label: If specified, this is a shorter version of the
                   label, used, for example, in grid table headings.
            :type short_label: str
            :param index_type: TODO (enum)
            :type index_type: str
            :param label_width: Optionally overrides ZPL's label width
                   calculation with a higher value.
            :type label_width: int
            :param default: Default Value
            :type default: ZPropertyDefaultValue
            :param content_width: Optionally overrides ZPL's content width
                   calculation with a higher value.
            :type content_width: int
            :param display: If this is set to False, this property will be
                   hidden from the UI completely.
            :type display: bool
            :param details_display: If this is set to False, this property
                   will be hidden from the "details" portion of the UI.
            :type details_display: bool
            :param grid_display: If this is set to False, this property
                   will be hidden from the "grid" portion of the UI.
            :type grid_display: bool
            :param renderer: Optional name of a javascript renderer to apply
                   to this property, rather than passing the text through
                   unformatted.
            :type renderer: str
            :param order: TODO
            :type order: float
            :param editable: TODO
            :type editable: bool
            :param api_only: TODO
            :type api_only: bool
            :param api_backendtype: TODO (enum)
            :type api_backendtype: str
            :param enum: TODO
            :type enum: dict
            :param datapoint: TODO (validate datapoint name)
            :type datapoint: str
            :param datapoint_default: TODO  - DEPRECATE (use default instead)
            :type datapoint_default: str
            :param datapoint_cached: TODO
            :type datapoint_cached: bool
            :param index_scope: TODO (enum)
            :type index_scope: str

        """
        super(ClassPropertySpec, self).__init__(_source_location=_source_location)

        self.class_spec = class_spec
        self.name = name
        self.default = default
        self.type_ = type_
        self.label = label or self.name
        self.short_label = short_label or self.label
        self.index_type = index_type
        self.index_scope = index_scope
        self.label_width = label_width
        self.content_width = content_width or label_width
        self.display = display
        self.details_display = details_display
        self.grid_display = grid_display
        self.renderer = renderer

        # pick an appropriate default renderer for this property.
        if type_ == 'entity' and not self.renderer:
            self.renderer = 'Zenoss.render.zenpacklib_{zenpack_id_prefix}_entityLinkFromGrid'.format(
                zenpack_id_prefix=self.class_spec.zenpack.id_prefix)

        self.editable = bool(editable)
        self.api_only = bool(api_only)
        self.api_backendtype = api_backendtype
        if isinstance(enum, (set, list, tuple)):
            enum = dict(enumerate(enum))
        self.enum = enum
        self.datapoint = datapoint
        self.datapoint_default = datapoint_default
        self.datapoint_cached = bool(datapoint_cached)
        # Force api mode when a datapoint is supplied
        if self.datapoint:
            self.api_only = True
            self.api_backendtype = 'method'

        if self.api_backendtype not in ('property', 'method'):
            raise TypeError(
                "Property '%s': api_backendtype must be 'property' or 'method', not '%s'"
                % (name, self.api_backendtype))

        if self.index_scope not in ('device', 'global', 'both'):
            raise TypeError(
                "Property '%s': index_scope must be 'device', 'global', or 'both', not '%s'"
                % (name, self.index_scope))

        # Force properties into the 4.0 - 4.9 order range.
        if not order:
            self.order = 4.5
        else:
            self.order = 4 + (max(0, min(100, order)) / 100.0)

    @property
    def ofs_dict(self):
        """Return OFS _properties dictionary."""
        if self.api_only:
            return None

        return {
            'id': self.name,
            'label': self.label,
            'type': self.type_,
            }

    @property
    def catalog_indexes(self):
        """Return catalog indexes dictionary."""
        if not self.index_type:
            return {}

        return {
            self.name: {'type': self.index_type,
                        'scope': self.index_scope},
            }

    @property
    def iinfo_schemas(self):
        """Return IInfo attribute schema dict.

        Return None if type has no known schema.

        """
        schema_map = {
            'boolean': schema.Bool,
            'int': schema.Int,
            'float': schema.Float,
            'lines': schema.Text,
            'string': schema.TextLine,
            'password': schema.Password,
            'entity': schema.Entity
            }

        if self.type_ not in schema_map:
            return {}

        if self.details_display is False:
            return {}

        return {
            self.name: schema_map[self.type_](
                title=_t(self.label),
                alwaysEditable=self.editable,
                order=self.order)
            }

    @property
    def info_properties(self):
        """Return Info properties dict."""
        if self.api_backendtype == 'method':
            return {
                self.name: MethodInfoProperty(self.name),
                }
        else:
            if not self.enum:
                return {self.name: ProxyProperty(self.name), }
            else:
                return {self.name: EnumInfoProperty(self.name, self.enum), }

    @property
    def js_fields(self):
        """Return list of JavaScript fields."""
        if self.grid_display is False:
            return []
        else:
            return ["{{name: '{}'}}".format(self.name)]

    @property
    def js_columns_width(self):
        """Return integer pixel width of JavaScript columns."""
        if self.grid_display:
            return max(self.content_width + 14, self.label_width + 20)
        else:
            return 0

    @property
    def js_columns(self):
        """Return list of JavaScript columns."""

        if self.grid_display is False:
            return []

        column_fields = [
            "id: '{}'".format(self.name),
            "dataIndex: '{}'".format(self.name),
            "header: _t('{}')".format(self.short_label),
            "width: {}".format(self.js_columns_width),
            ]

        if self.renderer:
            column_fields.append("renderer: {}".format(self.renderer))
        else:
            if self.type_ == 'boolean':
                column_fields.append("renderer: Zenoss.render.checkbox")

        return [
            OrderAndValue(
                order=self.order,
                value='{{{}}}'.format(','.join(column_fields))),
            ]


class RelationshipSchemaSpec(Spec):
    """TODO."""

    def __init__(
        self,
        zenpack_spec=None,
        left_class=None,
        left_relname=None,
        left_type=None,
        right_type=None,
        right_class=None,
        right_relname=None,
        _source_location=None
    ):
        """
            Create a Relationship Schema specification.  This describes both sides
            of a relationship (left and right).

            :param left_class: TODO
            :type left_class: class
            :param left_relname: TODO
            :type left_relname: str
            :param left_type: TODO
            :type left_type: reltype
            :param right_type: TODO
            :type right_type: reltype
            :param right_class: TODO
            :type right_class: class
            :param right_relname: TODO
            :type right_relname: str

        """
        super(RelationshipSchemaSpec, self).__init__(_source_location=_source_location)

        if not RelationshipSchemaSpec.valid_orientation(left_type, right_type):
            raise ZenSchemaError("In %s(%s) - (%s)%s, invalid orientation- left and right may be reversed." % (left_class, left_relname, right_relname, right_class))

        self.zenpack_spec = zenpack_spec
        self.left_class = left_class
        self.left_relname = left_relname
        self.left_schema = self.make_schema(left_type, right_type, right_class, right_relname)
        self.right_class = right_class
        self.right_relname = right_relname
        self.right_schema = self.make_schema(right_type, left_type, left_class, left_relname)

    @classmethod
    def valid_orientation(cls, left_type, right_type):
        # The objects in a relationship are always ordered left to right
        # so that they can be easily compared and consistently represented.
        #
        # The valid combinations are:

        # 1:1 - One To One
        if right_type == 'ToOne' and left_type == 'ToOne':
            return True

        # 1:M - One To Many
        if right_type == 'ToOne' and left_type == 'ToMany':
            return True

        # 1:MC - One To Many (Containing)
        if right_type == 'ToOne' and left_type == 'ToManyCont':
            return True

        # M:M - Many To Many
        if right_type == 'ToMany' and left_type == 'ToMany':
            return True

        return False

    _relTypeCardinality = {
        ToOne: '1',
        ToMany: 'M',
        ToManyCont: 'MC'
    }

    _relTypeClasses = {
        "ToOne": ToOne,
        "ToMany": ToMany,
        "ToManyCont": ToManyCont
    }

    _relTypeNames = {
        ToOne: "ToOne",
        ToMany: "ToMany",
        ToManyCont: "ToManyCont"
    }

    @property
    def left_type(self):
        return self._relTypeNames.get(self.right_schema.__class__)

    @property
    def right_type(self):
        return self._relTypeNames.get(self.left_schema.__class__)

    @property
    def left_cardinality(self):
        return self._relTypeCardinality.get(self.right_schema.__class__)

    @property
    def right_cardinality(self):
        return self._relTypeCardinality.get(self.left_schema.__class__)

    @property
    def default_left_relname(self):
        return relname_from_classname(self.right_class, plural=self.right_cardinality != '1')

    @property
    def default_right_relname(self):
        return relname_from_classname(self.left_class, plural=self.left_cardinality != '1')

    @property
    def cardinality(self):
        return '%s:%s' % (self.left_cardinality, self.right_cardinality)

    def make_schema(self, relTypeName, remoteRelTypeName, remoteClass, remoteName):
        relType = self._relTypeClasses.get(relTypeName, None)
        if not relType:
            raise ValueError("Unrecognized Relationship Type '%s'" % relTypeName)

        remoteRelType = self._relTypeClasses.get(remoteRelTypeName, None)
        if not remoteRelType:
            raise ValueError("Unrecognized Relationship Type '%s'" % remoteRelTypeName)

        schema = relType(remoteRelType, remoteClass, remoteName)

        # Qualify unqualified classnames.
        if '.' not in schema.remoteClass:
            schema.remoteClass = '{}.{}'.format(
                self.zenpack_spec.name, schema.remoteClass)

        return schema


class ClassRelationshipSpec(Spec):

    """TODO."""

    def __init__(
            self,
            class_,
            name,
            schema=None,
            label=None,
            short_label=None,
            label_width=None,
            content_width=None,
            display=True,
            details_display=True,
            grid_display=True,
            renderer=None,
            render_with_type=False,
            order=None,
            _source_location=None
            ):
        """
        Create a Class Relationship Specification

            :param label: Label to use when describing this relationship in the
                   UI.  If not specified, the default is to use the name of the
                   relationship's target class.
            :type label: str
            :param short_label: If specified, this is a shorter version of the
                   label, used, for example, in grid table headings.
            :type short_label: str
            :param label_width: Optionally overrides ZPL's label width
                   calculation with a higher value.
            :type label_width: int
            :param content_width:  Optionally overrides ZPL's content width
                   calculation with a higher value.
            :type content_width: int
            :param display: If this is set to False, this relationship will be
                   hidden from the UI completely.
            :type display: bool
            :param details_display: If this is set to False, this relationship
                   will be hidden from the "details" portion of the UI.
            :type details_display: bool
            :param grid_display:  If this is set to False, this relationship
                   will be hidden from the "grid" portion of the UI.
            :type grid_display: bool
            :param renderer: The default javascript renderer for a relationship
                   provides a link with the title of the target object,
                   optionally with the object's type (if render_with_type is
                   set).  If something more specific is required, a javascript
                   renderer function name may be provided.
            :type renderer: str
            :param render_with_type: Indicates that when an object is linked to,
                   it should be shown along with its type.  This is particularly
                   useful when the relationship's target is a base class that
                   may have several subclasses, such that the base class +
                   target object is not sufficiently descriptive on its own.
            :type render_with_type: bool
            :param order: TODO
            :type order: float

        """
        super(ClassRelationshipSpec, self).__init__(_source_location=_source_location)

        self.class_ = class_
        self.name = name
        self.schema = schema
        self.label = label
        self.short_label = short_label
        self.label_width = label_width
        self.content_width = content_width
        self.display = display
        self.details_display = details_display
        self.grid_display = grid_display
        self.renderer = renderer
        self.render_with_type = render_with_type
        self.order = order

        if not self.display:
            self.details_display = False
            self.grid_display = False

        if self.renderer is None:
            self.renderer = 'Zenoss.render.zenpacklib_{zenpack_id_prefix}_entityTypeLinkFromGrid' \
                if self.render_with_type else 'Zenoss.render.zenpacklib_{zenpack_id_prefix}_entityLinkFromGrid'

            self.renderer = self.renderer.format(zenpack_id_prefix=self.class_.zenpack.id_prefix)

    @property
    def zenrelations_tuple(self):
        return (self.name, self.schema)

    @property
    def remote_classname(self):
        return self.schema.remoteClass.split('.')[-1]

    @property
    def iinfo_schemas(self):
        """Return IInfo attribute schema dict."""
        remote_spec = self.class_.zenpack.classes.get(self.remote_classname)
        imported_class = self.class_.zenpack.imported_classes.get(self.schema.remoteClass)
        if not (remote_spec or imported_class):
            return {}

        schemas = {}

        if not self.details_display:
            return {}

        if imported_class:
            remote_spec = imported_class
            remote_spec.label = remote_spec.meta_type

        if isinstance(self.schema, (ToOne)):
            schemas[self.name] = schema.Entity(
                title=_t(self.label or remote_spec.label),
                group="Relationships",
                order=self.order or 3.0)
        else:
            relname_count = '{}_count'.format(self.name)
            schemas[relname_count] = schema.Int(
                title=_t(u'Number of {}'.format(self.label or remote_spec.plural_label)),
                group="Relationships",
                order=self.order or 6.0)

        return schemas

    @property
    def info_properties(self):
        """Return Info properties dict."""
        properties = {}

        if isinstance(self.schema, (ToOne)):
            properties[self.name] = RelationshipInfoProperty(self.name)
        else:
            relname_count = '{}_count'.format(self.name)
            properties[relname_count] = RelationshipLengthProperty(self.name)

        return properties

    @property
    def js_fields(self):
        """Return list of JavaScript fields."""
        remote_spec = self.class_.zenpack.classes.get(self.remote_classname)

        # do not show if grid turned off
        if self.grid_display is False:
            return []

        # No reason to show a column for the device since we're already
        # looking at the device.
        if not remote_spec or remote_spec.is_device:
            return []

        # Don't include containing relationships. They're handled by
        # the class.
        if issubclass(self.schema.remoteType, ToManyCont):
            return []

        if isinstance(self.schema, ToOne):
            fieldname = self.name
        else:
            fieldname = '{}_count'.format(self.name)

        return ["{{name: '{}'}}".format(fieldname)]

    @property
    def js_columns_width(self):
        """Return integer pixel width of JavaScript columns."""
        if not self.grid_display:
            return 0

        remote_spec = self.class_.zenpack.classes.get(self.remote_classname)

        # No reason to show a column for the device since we're already
        # looking at the device.
        if not remote_spec or remote_spec.is_device:
            return 0

        if isinstance(self.schema, ToOne):
            return max(
                (self.content_width or remote_spec.content_width) + 14,
                (self.label_width or remote_spec.label_width) + 20)
        else:
            return (self.label_width or remote_spec.plural_label_width) + 20

    @property
    def js_columns(self):
        """Return list of JavaScript columns."""
        if not self.grid_display:
            return []

        remote_spec = self.class_.zenpack.classes.get(self.remote_classname)

        # No reason to show a column for the device since we're already
        # looking at the device.
        if not remote_spec or remote_spec.is_device:
            return []

        # Don't include containing relationships. They're handled by
        # the class.
        if issubclass(self.schema.remoteType, ToManyCont):
            return []

        if isinstance(self.schema, ToOne):
            fieldname = self.name
            header = self.short_label or self.label or remote_spec.short_label
            renderer = self.renderer
        else:
            fieldname = '{}_count'.format(self.name)
            header = self.short_label or self.label or remote_spec.plural_short_label
            renderer = None

        column_fields = [
            "id: '{}'".format(fieldname),
            "dataIndex: '{}'".format(fieldname),
            "header: _t('{}')".format(header),
            "width: {}".format(self.js_columns_width),
            ]

        if renderer:
            column_fields.append("renderer: {}".format(renderer))

        return [
            OrderAndValue(
                order=self.order or remote_spec.order,
                value='{{{}}}'.format(','.join(column_fields))),
            ]


class RRDTemplateSpec(Spec):

    """TODO."""

    def __init__(
            self,
            deviceclass_spec,
            name,
            description=None,
            targetPythonClass=None,
            thresholds=None,
            datasources=None,
            graphs=None,
            _source_location=None
            ):
        """
        Create an RRDTemplate Specification


            :param description: TODO
            :type description: str
            :param targetPythonClass: TODO
            :type targetPythonClass: str
            :param thresholds: TODO
            :type thresholds: SpecsParameter(RRDThresholdSpec)
            :param datasources: TODO
            :type datasources: SpecsParameter(RRDDatasourceSpec)
            :param graphs: TODO
            :type graphs: SpecsParameter(GraphDefinitionSpec)

        """
        super(RRDTemplateSpec, self).__init__(_source_location=_source_location)

        self.deviceclass_spec = deviceclass_spec
        self.name = name
        self.description = description
        self.targetPythonClass = targetPythonClass

        self.thresholds = self.specs_from_param(
            RRDThresholdSpec, 'thresholds', thresholds)

        self.datasources = self.specs_from_param(
            RRDDatasourceSpec, 'datasources', datasources)

        self.graphs = self.specs_from_param(
            GraphDefinitionSpec, 'graphs', graphs)

    def create(self, dmd):
        device_class = dmd.Devices.createOrganizer(self.deviceclass_spec.path)

        existing_template = device_class.rrdTemplates._getOb(self.name, None)
        if existing_template:
            self.speclog.info("replacing template")
            device_class.rrdTemplates._delObject(self.name)

        device_class.manage_addRRDTemplate(self.name)
        template = device_class.rrdTemplates._getOb(self.name)

        # Flag this as a ZPL managed object, that is, one that should not be
        # exported to objects.xml  (contained objects will also be excluded)
        template.zpl_managed = True

        # Add this RRDTemplate to the zenpack.
        zenpack_name = self.deviceclass_spec.zenpack_spec.name
        template.addToZenPack(pack=zenpack_name)

        if not existing_template:
            self.speclog.info("adding template")

        if self.targetPythonClass is not None:
            template.targetPythonClass = self.targetPythonClass
        if self.description is not None:
            template.description = self.description

        self.speclog.debug("adding {} thresholds".format(len(self.thresholds)))
        for threshold_id, threshold_spec in self.thresholds.items():
            threshold_spec.create(self, template)

        self.speclog.debug("adding {} datasources".format(len(self.datasources)))
        for datasource_id, datasource_spec in self.datasources.items():
            datasource_spec.create(self, template)

        self.speclog.debug("adding {} graphs".format(len(self.graphs)))
        for graph_id, graph_spec in self.graphs.items():
            graph_spec.create(self, template)


class RRDThresholdSpec(Spec):

    """TODO."""

    def __init__(
            self,
            template_spec,
            name,
            type_='MinMaxThreshold',
            dsnames=None,
            eventClass=None,
            severity=None,
            enabled=None,
            extra_params=None,
            _source_location=None
            ):
        """
        Create an RRDThreshold Specification

            :param type_: TODO
            :type type_: str
            :yaml_param type_: type
            :param dsnames: TODO
            :type dsnames: list(str)
            :param eventClass: TODO
            :type eventClass: str
            :param severity: TODO
            :type severity: Severity
            :param enabled: TODO
            :type enabled: bool
            :param extra_params: Additional parameters that may be used by subclasses of RRDDatasource
            :type extra_params: ExtraParams

        """
        super(RRDThresholdSpec, self).__init__(_source_location=_source_location)

        self.name = name
        self.template_spec = template_spec
        self.dsnames = dsnames
        self.eventClass = eventClass
        self.severity = severity
        self.enabled = enabled
        self.type_ = type_
        if extra_params is None:
            self.extra_params = {}
        else:
            self.extra_params = extra_params

    def create(self, templatespec, template):
        if not self.dsnames:
            raise ValueError("%s: threshold has no dsnames attribute", self)

        # Shorthand for datapoints that have the same name as their datasource.
        for i, dsname in enumerate(self.dsnames):
            if '_' not in dsname:
                self.dsnames[i] = '_'.join((dsname, dsname))

        threshold_types = dict((y, x) for x, y in template.getThresholdClasses())
        type_ = threshold_types.get(self.type_)
        if not type_:
            raise ValueError("'%s' is an invalid threshold type. Valid types: %s" %
                             (self.type_, ', '.join(threshold_types)))

        threshold = template.manage_addRRDThreshold(self.name, self.type_)
        self.speclog.debug("adding threshold")

        if self.dsnames is not None:
            threshold.dsnames = self.dsnames
        if self.eventClass is not None:
            threshold.eventClass = self.eventClass
        if self.severity is not None:
            threshold.severity = self.severity
        if self.enabled is not None:
            threshold.enabled = self.enabled
        if self.extra_params:
            for param, value in self.extra_params.iteritems():
                if param in [x['id'] for x in threshold._properties]:
                    setattr(threshold, param, value)
                else:
                    raise ValueError("%s is not a valid property for threshold of type %s" % (param, type_))


class RRDDatasourceSpec(Spec):

    """TODO."""

    def __init__(
            self,
            template_spec,
            name,
            sourcetype=None,
            enabled=True,
            component=None,
            eventClass=None,
            eventKey=None,
            severity=None,
            commandTemplate=None,
            cycletime=None,
            datapoints=None,
            extra_params=None,
            _source_location=None
            ):
        """
        Create an RRDDatasource Specification

            :param sourcetype: TODO
            :type sourcetype: str
            :yaml_param sourcetype: type
            :param enabled: TODO
            :type enabled: bool
            :param component: TODO
            :type component: str
            :param eventClass: TODO
            :type eventClass: str
            :param eventKey: TODO
            :type eventKey: str
            :param severity: TODO
            :type severity: Severity
            :param commandTemplate: TODO
            :type commandTemplate: str
            :param cycletime: TODO
            :type cycletime: int
            :param datapoints: TODO
            :type datapoints: SpecsParameter(RRDDatapointSpec)
            :param extra_params: Additional parameters that may be used by subclasses of RRDDatasource
            :type extra_params: ExtraParams

        """
        super(RRDDatasourceSpec, self).__init__(_source_location=_source_location)

        self.template_spec = template_spec
        self.name = name
        self.sourcetype = sourcetype
        self.enabled = enabled
        self.component = component
        self.eventClass = eventClass
        self.eventKey = eventKey
        self.severity = severity
        self.commandTemplate = commandTemplate
        self.cycletime = cycletime
        if extra_params is None:
            self.extra_params = {}
        else:
            self.extra_params = extra_params

        self.datapoints = self.specs_from_param(
            RRDDatapointSpec, 'datapoints', datapoints)

    def create(self, templatespec, template):
        datasource_types = dict(template.getDataSourceOptions())

        if not self.sourcetype:
            raise ValueError('No type for %s/%s. Valid types: %s' % (
                             template.id, self.name, ', '.join(datasource_types)))

        type_ = datasource_types.get(self.sourcetype)
        if not type_:
            raise ValueError("%s is an invalid datasource type. Valid types: %s" % (
                             self.sourcetype, ', '.join(datasource_types)))

        datasource = template.manage_addRRDDataSource(self.name, type_)
        self.speclog.debug("adding datasource")

        if self.enabled is not None:
            datasource.enabled = self.enabled
        if self.component is not None:
            datasource.component = self.component
        if self.eventClass is not None:
            datasource.eventClass = self.eventClass
        if self.eventKey is not None:
            datasource.eventKey = self.eventKey
        if self.severity is not None:
            datasource.severity = self.severity
        if self.commandTemplate is not None:
            datasource.commandTemplate = self.commandTemplate
        if self.cycletime is not None:
            datasource.cycletime = self.cycletime

        if self.extra_params:
            for param, value in self.extra_params.iteritems():
                if param in [x['id'] for x in datasource._properties]:
                    # handle an ui test error that expects the oid value to be a string
                    # this is to workaround a ui bug known in 4.5 and 5.0.3
                    if type_ == 'BasicDataSource.SNMP' and param == 'oid':
                        setattr(datasource, param, str(value))
                    else:
                        setattr(datasource, param, value)
                else:
                    raise ValueError("%s is not a valid property for datasource of type %s" % (param, type_))

        self.speclog.debug("adding {} datapoints".format(len(self.datapoints)))
        for datapoint_id, datapoint_spec in self.datapoints.items():
            datapoint_spec.create(self, datasource)


class RRDDatapointSpec(Spec):

    """TODO."""

    def __init__(
            self,
            datasource_spec,
            name,
            rrdtype=None,
            createCmd=None,
            isrow=None,
            rrdmin=None,
            rrdmax=None,
            description=None,
            aliases=None,
            shorthand=None,
            extra_params=None,
            _source_location=None
            ):
        """
        Create an RRDDatapoint Specification

        :param rrdtype: TODO
        :type rrdtype: str
        :param createCmd: TODO
        :type createCmd: str
        :param isrow: TODO
        :type isrow: bool
        :param rrdmin: TODO
        :type rrdmin: int
        :param rrdmax: TODO
        :type rrdmax: int
        :param description: TODO
        :type description: str
        :param aliases: TODO
        :type aliases: dict(str)
        :param extra_params: Additional parameters that may be used by subclasses of RRDDatapoint
        :type extra_params: ExtraParams

        """
        super(RRDDatapointSpec, self).__init__(_source_location=_source_location)

        self.datasource_spec = datasource_spec
        self.name = name

        self.rrdtype = rrdtype
        self.createCmd = createCmd
        self.isrow = isrow
        self.rrdmin = rrdmin
        self.rrdmax = rrdmax
        self.description = description
        if extra_params is None:
            self.extra_params = {}
        elif isinstance(extra_params, dict):
            self.extra_params = extra_params

        if aliases is None:
            self.aliases = {}
        elif isinstance(aliases, dict):
            self.aliases = aliases
        else:
            raise ValueError("aliases must be specified as a dict")

        if shorthand:
            if 'DERIVE' in shorthand.upper():
                self.rrdtype = 'DERIVE'

            min_match = re.search(r'MIN_(\d+)', shorthand, re.IGNORECASE)
            if min_match:
                rrdmin = min_match.group(1)
                self.rrdmin = rrdmin

            max_match = re.search(r'MAX_(\d+)', shorthand, re.IGNORECASE)
            if max_match:
                rrdmax = max_match.group(1)
                self.rrdmax = rrdmax

    def __eq__(self, other):
        if self.shorthand:
            # when shorthand syntax is in use, the other values are not relevant
            return super(RRDDatapointSpec, self).__eq__(other, ignore_params=['rrdtype', 'rrdmin', 'rrdmax'])
        else:
            return super(RRDDatapointSpec, self).__eq__(other)

    def create(self, datasource_spec, datasource):
        datapoint = datasource.manage_addRRDDataPoint(self.name)
        type_ = datapoint.__class__.__name__
        self.speclog.debug("adding datapoint of type %s" % type_)

        if self.rrdtype is not None:
            datapoint.rrdtype = self.rrdtype
        if self.createCmd is not None:
            datapoint.createCmd = self.createCmd
        if self.isrow is not None:
            datapoint.isrow = self.isrow
        if self.rrdmin is not None:
            datapoint.rrdmin = str(self.rrdmin)
        if self.rrdmax is not None:
            datapoint.rrdmax = str(self.rrdmax)
        if self.description is not None:
            datapoint.description = self.description
        if self.extra_params:
            for param, value in self.extra_params.iteritems():
                if param in [x['id'] for x in datapoint._properties]:
                    setattr(datapoint, param, value)
                else:
                    raise ValueError("%s is not a valid property for datapoint of type %s" % (param, type_))

        self.speclog.debug("adding {} aliases".format(len(self.aliases)))
        for alias_id, formula in self.aliases.items():
            datapoint.addAlias(alias_id, formula)
            self.speclog.debug("adding alias".format(alias_id))
            self.speclog.debug("formula = {}".format(formula))


class GraphDefinitionSpec(Spec):
    """TODO."""

    def __init__(
            self,
            template_spec,
            name,
            height=None,
            width=None,
            units=None,
            log=None,
            base=None,
            miny=None,
            maxy=None,
            custom=None,
            hasSummary=None,
            graphpoints=None,
            comments=None,
            _source_location=None
            ):
        """
        Create a GraphDefinition Specification

        :param height TODO
        :type height: int
        :param width TODO
        :type width: int
        :param units TODO
        :type units: str
        :param log TODO
        :type log: bool
        :param base TODO
        :type base: bool
        :param miny TODO
        :type miny: int
        :param maxy TODO
        :type maxy: int
        :param custom: TODO
        :type custom: str
        :param hasSummary: TODO
        :type hasSummary: bool
        :param graphpoints: TODO
        :type graphpoints: SpecsParameter(GraphPointSpec)
        :param comments: TODO
        :type comments: list(str)
        """
        super(GraphDefinitionSpec, self).__init__(_source_location=_source_location)

        self.template_spec = template_spec
        self.name = name

        self.height = height
        self.width = width
        self.units = units
        self.log = log
        self.base = base
        self.miny = miny
        self.maxy = maxy
        self.custom = custom
        self.hasSummary = hasSummary
        self.graphpoints = self.specs_from_param(
            GraphPointSpec, 'graphpoints', graphpoints)
        self.comments = comments

        # TODO fix comments parsing - must always be a list.

    def create(self, templatespec, template):
        graph = template.manage_addGraphDefinition(self.name)
        self.speclog.debug("adding graph")

        if self.height is not None:
            graph.height = self.height
        if self.width is not None:
            graph.width = self.width
        if self.units is not None:
            graph.units = self.units
        if self.log is not None:
            graph.log = self.log
        if self.base is not None:
            graph.base = self.base
        if self.miny is not None:
            graph.miny = self.miny
        if self.maxy is not None:
            graph.maxy = self.maxy
        if self.custom is not None:
            graph.custom = self.custom
        if self.hasSummary is not None:
            graph.hasSummary = self.hasSummary

        if self.comments:
            self.speclog.debug("adding {} comments".format(len(self.comments)))
            for i, comment_text in enumerate(self.comments):
                comment = graph.createGraphPoint(
                    CommentGraphPoint,
                    'comment-{}'.format(i))

                comment.text = comment_text

        self.speclog.debug("adding {} graphpoints".format(len(self.graphpoints)))
        for graphpoint_id, graphpoint_spec in self.graphpoints.items():
            graphpoint_spec.create(self, graph)


class GraphPointSpec(Spec):
    """TODO."""

    def __init__(
            self,
            template_spec,
            name=None,
            dpName=None,
            lineType=None,
            lineWidth=None,
            stacked=None,
            format=None,
            legend=None,
            limit=None,
            rpn=None,
            cFunc=None,
            colorindex=None,
            color=None,
            includeThresholds=False,
            _source_location=None
            ):
        """
        Create a GraphPoint Specification

            :param dpName: TODO
            :type dpName: str
            :param lineType: TODO
            :type lineType: str
            :param lineWidth: TODO
            :type lineWidth: int
            :param stacked: TODO
            :type stacked: bool
            :param format: TODO
            :type format: str
            :param legend: TODO
            :type legend: str
            :param limit: TODO
            :type limit: int
            :param rpn: TODO
            :type rpn: str
            :param cFunc: TODO
            :type cFunc: str
            :param color: TODO
            :type color: str
            :param colorindex: TODO
            :type colorindex: int
            :param includeThresholds: TODO
            :type includeThresholds: bool

        """
        super(GraphPointSpec, self).__init__(_source_location=_source_location)

        self.template_spec = template_spec
        self.name = name

        self.lineType = lineType
        self.lineWidth = lineWidth
        self.stacked = stacked
        self.format = format
        self.legend = legend
        self.limit = limit
        self.rpn = rpn
        self.cFunc = cFunc
        self.color = color
        self.includeThresholds = includeThresholds

        # Shorthand for datapoints that have the same name as their datasource.
        if '_' not in dpName:
            self.dpName = '{0}_{0}'.format(dpName)
        else:
            self.dpName = dpName

        # Allow color to be specified by color_index instead of directly. This is
        # useful when you want to keep the normal progression of colors, but need
        # to add some DONTDRAW graphpoints for calculations.
        if colorindex:
            try:
                colorindex = int(colorindex) % len(GraphPoint.colors)
            except (TypeError, ValueError):
                raise ValueError("graphpoint colorindex must be numeric.")

            self.color = GraphPoint.colors[colorindex].lstrip('#')

        # Validate lineType.
        if lineType:
            valid_linetypes = [x[1] for x in ComplexGraphPoint.lineTypeOptions]

            if lineType.upper() in valid_linetypes:
                self.lineType = lineType.upper()
            else:
                raise ValueError("'%s' is not a valid graphpoint lineType. Valid lineTypes: %s" % (
                                 lineType, ', '.join(valid_linetypes)))

    def create(self, graph_spec, graph):
        graphpoint = graph.createGraphPoint(DataPointGraphPoint, self.name)
        self.speclog.debug("adding graphpoint")

        graphpoint.dpName = self.dpName

        if self.lineType is not None:
            graphpoint.lineType = self.lineType
        if self.lineWidth is not None:
            graphpoint.lineWidth = self.lineWidth
        if self.stacked is not None:
            graphpoint.stacked = self.stacked
        if self.format is not None:
            graphpoint.format = self.format
        if self.legend is not None:
            graphpoint.legend = self.legend
        if self.limit is not None:
            graphpoint.limit = self.limit
        if self.rpn is not None:
            graphpoint.rpn = self.rpn
        if self.cFunc is not None:
            graphpoint.cFunc = self.cFunc
        if self.color is not None:
            graphpoint.color = self.color

        if self.includeThresholds:
            graph.addThresholdsForDataPoint(self.dpName)


# SpecParams ################################################################

class SpecParams(object):
    def __init__(self, **kwargs):
        # Initialize with default values
        params = self.__class__.init_params()
        for param in params:
            if 'default' in params[param]:
                setattr(self, param, params[param]['default'])

        # Overlay any named parameters
        self.__dict__.update(kwargs)

    @classmethod
    def init_params(cls):
        # Pull over the params for the underlying Spec class,
        # correcting nested Specs to SpecsParams instead.
        try:
            spec_base = [x for x in cls.__bases__ if issubclass(x, Spec)][0]
        except Exception:
            raise Exception("Spec Base Not Found for %s" % cls.__name__)

        params = spec_base.init_params()
        for p in params:
            params[p]['type'] = params[p]['type'].replace("Spec)", "SpecParams)")

        return params


class ZenPackSpecParams(SpecParams, ZenPackSpec):
    def __init__(self, name, zProperties=None, class_relationships=None, classes=None, device_classes=None, **kwargs):
        SpecParams.__init__(self, **kwargs)
        self.name = name

        self.zProperties = self.specs_from_param(
            ZPropertySpecParams, 'zProperties', zProperties, leave_defaults=True)

        self.class_relationships = []
        if class_relationships:
            if not isinstance(class_relationships, list):
                raise ValueError("class_relationships must be a list, not a %s" % type(class_relationships))

            for rel in class_relationships:
                self.class_relationships.append(RelationshipSchemaSpec(self, **rel))

        self.classes = self.specs_from_param(
            ClassSpecParams, 'classes', classes, leave_defaults=True)

        self.device_classes = self.specs_from_param(
            DeviceClassSpecParams, 'device_classes', device_classes, leave_defaults=True)


class DeviceClassSpecParams(SpecParams, DeviceClassSpec):
    def __init__(self, zenpack_spec, path, zProperties=None, templates=None, **kwargs):
        SpecParams.__init__(self, **kwargs)
        self.path = path
        self.zProperties = zProperties
        self.templates = self.specs_from_param(
            RRDTemplateSpecParams, 'templates', templates)


class ZPropertySpecParams(SpecParams, ZPropertySpec):
    def __init__(self, zenpack_spec, name, **kwargs):
        SpecParams.__init__(self, **kwargs)
        self.name = name


class ClassSpecParams(SpecParams, ClassSpec):
    def __init__(self, zenpack_spec, name, base=None, properties=None, relationships=None, monitoring_templates=[], **kwargs):
        SpecParams.__init__(self, **kwargs)
        self.name = name

        if isinstance(base, (tuple, list, set)):
            self.base = tuple(base)
        else:
            self.base = (base,)

        if isinstance(monitoring_templates, (tuple, list, set)):
            self.monitoring_templates = list(monitoring_templates)
        else:
            self.monitoring_templates = [monitoring_templates]

        self.properties = self.specs_from_param(
            ClassPropertySpecParams, 'properties', properties, leave_defaults=True)

        self.relationships = self.specs_from_param(
            ClassRelationshipSpecParams, 'relationships', relationships, leave_defaults=True)


class ClassPropertySpecParams(SpecParams, ClassPropertySpec):
    def __init__(self, class_spec, name, **kwargs):
        SpecParams.__init__(self, **kwargs)
        self.name = name


class ClassRelationshipSpecParams(SpecParams, ClassRelationshipSpec):
    def __init__(self, class_spec, name, **kwargs):
        SpecParams.__init__(self, **kwargs)
        self.name = name


class RRDTemplateSpecParams(SpecParams, RRDTemplateSpec):
    def __init__(self, deviceclass_spec, name, thresholds=None, datasources=None, graphs=None, **kwargs):
        SpecParams.__init__(self, **kwargs)
        self.name = name

        self.thresholds = self.specs_from_param(
            RRDThresholdSpecParams, 'thresholds', thresholds)

        self.datasources = self.specs_from_param(
            RRDDatasourceSpecParams, 'datasources', datasources)

        self.graphs = self.specs_from_param(
            GraphDefinitionSpecParams, 'graphs', graphs)

    @classmethod
    def fromObject(cls, template):
        self = object.__new__(cls)
        SpecParams.__init__(self)
        template = aq_base(template)

        # Weed out any values that are the same as they would by by default.
        # We do this by instantiating a "blank" template and comparing
        # to it.
        sample_template = template.__class__(template.id)

        for propname in ('targetPythonClass', 'description',):
            if hasattr(sample_template, propname):
                setattr(self, '_%s_defaultvalue' % propname, getattr(sample_template, propname))
            if getattr(template, propname, None) != getattr(sample_template, propname, None):
                setattr(self, propname, getattr(template, propname, None))

        self.thresholds = {x.id: RRDThresholdSpecParams.fromObject(x) for x in template.thresholds()}
        self.datasources = {x.id: RRDDatasourceSpecParams.fromObject(x) for x in template.datasources()}
        self.graphs = {x.id: GraphDefinitionSpecParams.fromObject(x) for x in template.graphDefs()}

        return self


class RRDDatasourceSpecParams(SpecParams, RRDDatasourceSpec):
    def __init__(self, template_spec, name, datapoints=None, **kwargs):
        SpecParams.__init__(self, **kwargs)
        self.name = name

        self.datapoints = self.specs_from_param(
            RRDDatapointSpecParams, 'datapoints', datapoints)

    @classmethod
    def fromObject(cls, datasource):
        self = object.__new__(cls)
        SpecParams.__init__(self)
        datasource = aq_base(datasource)

        # Weed out any values that are the same as they would by by default.
        # We do this by instantiating a "blank" datapoint and comparing
        # to it.
        sample_ds = datasource.__class__(datasource.id)

        self.sourcetype = datasource.sourcetype
        for propname in ('enabled', 'component', 'eventClass', 'eventKey',
                         'severity', 'commandTemplate', 'cycletime',):
            if hasattr(sample_ds, propname):
                setattr(self, '_%s_defaultvalue' % propname, getattr(sample_ds, propname))
            if getattr(datasource, propname, None) != getattr(sample_ds, propname, None):
                setattr(self, propname, getattr(datasource, propname, None))

        self.extra_params = collections.OrderedDict()
        for propname in [x['id'] for x in datasource._properties]:
            if propname not in self.init_params():
                if getattr(datasource, propname, None) != getattr(sample_ds, propname, None):
                    self.extra_params[propname] = getattr(datasource, propname, None)

        self.datapoints = {x.id: RRDDatapointSpecParams.fromObject(x) for x in datasource.datapoints()}

        return self


class RRDThresholdSpecParams(SpecParams, RRDThresholdSpec):
    def __init__(self, template_spec, name, foo=None, **kwargs):
        SpecParams.__init__(self, **kwargs)
        self.name = name

    @classmethod
    def fromObject(cls, threshold):
        self = object.__new__(cls)
        SpecParams.__init__(self)
        threshold = aq_base(threshold)
        sample_th = threshold.__class__(threshold.id)

        for propname in ('dsnames', 'eventClass', 'severity', 'type_'):
            if hasattr(sample_th, propname):
                setattr(self, '_%s_defaultvalue' % propname, getattr(sample_th, propname))
            if getattr(threshold, propname, None) != getattr(sample_th, propname, None):
                setattr(self, propname, getattr(threshold, propname, None))

        self.extra_params = collections.OrderedDict()
        for propname in [x['id'] for x in threshold._properties]:
            if propname not in self.init_params():
                if getattr(threshold, propname, None) != getattr(sample_th, propname, None):
                    self.extra_params[propname] = getattr(threshold, propname, None)

        return self


class RRDDatapointSpecParams(SpecParams, RRDDatapointSpec):
    def __init__(self, datasource_spec, name, shorthand=None, **kwargs):
        SpecParams.__init__(self, **kwargs)
        self.name = name
        self.shorthand = shorthand

    @classmethod
    def fromObject(cls, datapoint):
        self = object.__new__(cls)
        SpecParams.__init__(self)
        datapoint = aq_base(datapoint)
        sample_dp = datapoint.__class__(datapoint.id)

        for propname in ('name', 'rrdtype', 'createCmd', 'isrow', 'rrdmin',
                         'rrdmax', 'description',):
            if hasattr(sample_dp, propname):
                setattr(self, '_%s_defaultvalue' % propname, getattr(sample_dp, propname))
            if getattr(datapoint, propname, None) != getattr(sample_dp, propname, None):
                setattr(self, propname, getattr(datapoint, propname, None))

        if self.rrdmin is not None:
            self.rrdmin = int(self.rrdmin)
        if self.rrdmax is not None:
            self.rrdmax = int(self.rrdmax)

        self.aliases = {x.id: x.formula for x in datapoint.aliases()}

        self.extra_params = collections.OrderedDict()
        for propname in [x['id'] for x in datapoint._properties]:
            if propname not in self.init_params():
                if getattr(datapoint, propname, None) != getattr(sample_dp, propname, None):
                    self.extra_params[propname] = getattr(datapoint, propname, None)

        # Shorthand support.  The use of the shorthand field takes
        # over all other attributes.  So we can only use it when the rest of
        # the attributes have default values.   This gets tricky if
        # RRDDatapoint has been subclassed, since we don't know what
        # the defaults are, necessarily.
        #
        # To do this, we actually instantiate a sample datapoint
        # using only the shorthand values, and see if the result
        # ends up being effectively the same as what we have.

        shorthand_props = {}
        shorthand = []
        self.shorthand = None
        if datapoint.rrdtype in ('GAUGE', 'DERIVE'):
            shorthand.append(datapoint.rrdtype)
            shorthand_props['rrdtype'] = datapoint.rrdtype

            if datapoint.rrdmin:
                shorthand.append('MIN_%d' % int(datapoint.rrdmin))
                shorthand_props['rrdmin'] = datapoint.rrdmin

            if datapoint.rrdmax:
                shorthand.append('MAX_%d' % int(datapoint.rrdmax))
                shorthand_props['rrdmax'] = datapoint.rrdmax

            if shorthand:
                for prop in shorthand_props:
                    setattr(sample_dp, prop, shorthand_props[prop])

                # Compare the current datapoint with the results
                # of constructing one from the shorthand syntax.
                #
                # The comparison is based on the objects.xml-style
                # xml representation, because it seems like that's really
                # the bottom line.  If they end up the same in there, then
                # I am certain that they are equivalent.

                import StringIO
                io = StringIO.StringIO()
                datapoint.exportXml(io)
                dp_xml = io.getvalue()
                io.close()

                io = StringIO.StringIO()
                sample_dp.exportXml(io)
                sample_dp_xml = io.getvalue()
                io.close()

                # Identical, so set the shorthand.  This will cause
                # all other properties to be ignored during
                # serialization to yaml.
                if dp_xml == sample_dp_xml:
                    self.shorthand = '_'.join(shorthand)

        return self


class GraphDefinitionSpecParams(SpecParams, GraphDefinitionSpec):
    def __init__(self, template_spec, name, graphpoints=None, **kwargs):
        SpecParams.__init__(self, **kwargs)
        self.name = name
        self.graphpoints = self.specs_from_param(
            GraphPointSpecParams, 'graphpoints', graphpoints)

    @classmethod
    def fromObject(cls, graphdefinition):
        self = object.__new__(cls)
        SpecParams.__init__(self)
        graphdefinition = aq_base(graphdefinition)
        sample_gd = graphdefinition.__class__(graphdefinition.id)

        for propname in ('height', 'width', 'units', 'log', 'base', 'miny',
                         'maxy', 'custom', 'hasSummary', 'comments'):
            if hasattr(sample_gd, propname):
                setattr(self, '_%s_defaultvalue' % propname, getattr(sample_gd, propname))
            if getattr(graphdefinition, propname, None) != getattr(sample_gd, propname, None):
                setattr(self, propname, getattr(graphdefinition, propname, None))

        datapoint_graphpoints = [x for x in graphdefinition.graphPoints() if isinstance(x, DataPointGraphPoint)]
        self.graphpoints = {x.id: GraphPointSpecParams.fromObject(x, graphdefinition) for x in datapoint_graphpoints}

        comment_graphpoints = [x for x in graphdefinition.graphPoints() if isinstance(x, CommentGraphPoint)]
        if comment_graphpoints:
            self.comments = [y.text for y in sorted(comment_graphpoints, key=lambda x: x.id)]

        return self


class GraphPointSpecParams(SpecParams, GraphPointSpec):
    def __init__(self, template_spec, name, **kwargs):
        SpecParams.__init__(self, **kwargs)
        self.name = name

    @classmethod
    def fromObject(cls, graphpoint, graphdefinition):
        self = object.__new__(cls)
        SpecParams.__init__(self)
        graphpoint = aq_base(graphpoint)
        graphdefinition = aq_base(graphdefinition)
        sample_gp = graphpoint.__class__(graphpoint.id)

        for propname in ('lineType', 'lineWidth', 'stacked', 'format',
                         'legend', 'limit', 'rpn', 'cFunc', 'color', 'dpName'):
            if hasattr(sample_gp, propname):
                setattr(self, '_%s_defaultvalue' % propname, getattr(sample_gp, propname))
            if getattr(graphpoint, propname, None) != getattr(sample_gp, propname, None):
                setattr(self, propname, getattr(graphpoint, propname, None))

        threshold_graphpoints = [x for x in graphdefinition.graphPoints() if isinstance(x, ThresholdGraphPoint)]

        self.includeThresholds = False
        if threshold_graphpoints:
            thresholds = {x.id: x for x in graphpoint.graphDef().rrdTemplate().thresholds()}
            for tgp in threshold_graphpoints:
                threshold = thresholds.get(tgp.threshId, None)
                if threshold:
                    if graphpoint.dpName in threshold.dsnames:
                        self.includeThresholds = True

        return self


# YAML Import/Export ########################################################

if YAML_INSTALLED:
    def relschemaspec_to_str(spec):
        # Omit relation names that are their defaults.
        left_optrelname = "" if spec.left_relname == spec.default_left_relname else "(%s)" % spec.left_relname
        right_optrelname = "" if spec.right_relname == spec.default_right_relname else "(%s)" % spec.right_relname

        return "%s%s %s:%s %s%s" % (
            spec.left_class,
            left_optrelname,
            spec.left_cardinality,
            spec.right_cardinality,
            right_optrelname,
            spec.right_class
        )

    def str_to_relschemaspec(schemastr):
        schema_pattern = re.compile(
            r'^\s*(?P<left>\S+)'
            r'\s+(?P<cardinality>1:1|1:M|1:MC|M:M)'
            r'\s+(?P<right>\S+)\s*$',
        )

        class_rel_pattern = re.compile(
            r'(\((?P<pre_relname>[^\)\s]+)\))?'
            r'(?P<class>[^\(\s]+)'
            r'(\((?P<post_relname>[^\)\s]+)\))?'
        )

        m = schema_pattern.search(schemastr)
        if not m:
            raise ValueError("RelationshipSchemaSpec '%s' is not valid" % schemastr)

        ml = class_rel_pattern.search(m.group('left'))
        if not ml:
            raise ValueError("RelationshipSchemaSpec '%s' left side is not valid" % m.group('left'))

        mr = class_rel_pattern.search(m.group('right'))
        if not mr:
            raise ValueError("RelationshipSchemaSpec '%s' right side is not valid" % m.group('right'))

        reltypes = {
            '1:1': ('ToOne', 'ToOne'),
            '1:M': ('ToMany', 'ToOne'),
            '1:MC': ('ToManyCont', 'ToOne'),
            'M:M': ('ToMany', 'ToMany')
        }

        left_class = ml.group('class')
        right_class = mr.group('class')
        left_type = reltypes.get(m.group('cardinality'))[0]
        right_type = reltypes.get(m.group('cardinality'))[1]

        left_relname = ml.group('pre_relname') or ml.group('post_relname')
        if left_relname is None:
            left_relname = relname_from_classname(right_class, plural=left_type != 'ToOne')

        right_relname = mr.group('pre_relname') or mr.group('post_relname')
        if right_relname is None:
            right_relname = relname_from_classname(left_class, plural=right_type != 'ToOne')

        return dict(
            left_class=left_class,
            left_relname=left_relname,
            left_type=left_type,
            right_type=right_type,
            right_class=right_class,
            right_relname=right_relname
        )

    def class_to_str(class_):
        return class_.__module__ + "." + class_.__name__

    def str_to_class(classstr):

        if classstr == 'object':
            return object

        if "." not in classstr:
            # TODO: Support non qualfied class names, searching zenpack, zenpacklib,
            # and ZenModel namespaces

            # An unqualified class name is assumed to be referring to one in
            # the classes defined in this ZenPackSpec.   We can't validate this,
            # or return a class object for it, if this is the case.  So we
            # return no class object, and the caller will assume that it
            # it refers to a class being defined.
            return None

        modname, classname = classstr.rsplit(".", 1)

        # ensure that 'zenpacklib' refers to *this* zenpacklib, if more than
        # one is loaded in the system.
        if modname == 'zenpacklib':
            modname = __name__

        try:
            class_ = getattr(importlib.import_module(modname), classname)
        except Exception, e:
            raise ValueError("Class '%s' is not valid: %s" % (classstr, e))

        return class_

    def severity_to_str(value):
        '''
        Return string representation for severity given a numeric value.
        '''
        severity = {
            5: 'crit',
            4: 'err',
            3: 'warn',
            2: 'info',
            1: 'debug',
            0: 'clear'
            }.get(value, None)

        if severity is None:
            raise ValueError("'%s' is not a valid value for severity.", value)

        return severity

    def str_to_severity(value):
        '''
        Return numeric severity given a string representation of severity.
        '''
        try:
            severity = int(value)
        except (TypeError, ValueError):
            severity = {
                'crit': 5, 'critical': 5,
                'err': 4, 'error': 4,
                'warn': 3, 'warning': 3,
                'info': 2, 'information': 2, 'informational': 2,
                'debug': 1, 'debugging': 1,
                'clear': 0,
                }.get(value.lower())

        if severity is None:
            raise ValueError("'%s' is not a valid value for severity." % value)

        return severity

    def yaml_error(loader, e, exc_info=None):
        # Given a MarkedYAMLError exception, either log or raise
        # the error, depending on the 'fatal' argument.
        fatal = not getattr(loader, 'warnings', False)
        setattr(loader, 'yaml_errored', True)

        if exc_info:
            # When we're given the original exception (which was wrapped in
            # a MarkedYAMLError), we can provide more context for debugging.

            from traceback import format_exc
            e.note = "\nOriginal exception:\n" + format_exc(exc_info)

        if fatal:
            raise e

        message = []

        mark = e.context_mark or e.problem_mark
        if mark:
            position = "%s:%s:%s" % (mark.name, mark.line+1, mark.column+1)
        else:
            position = "[unknown]"
        if e.context is not None:
            message.append(e.context)

        if e.problem is not None:
            message.append(e.problem)

        if e.note is not None:
            message.append("(note: " + e.note + ")")

        print "%s: %s" % (position, ",".join(message))

    def construct_specsparameters(loader, node, spectype):
        spec_class = {x.__name__: x for x in Spec.__subclasses__()}.get(spectype, None)

        if not spec_class:
            yaml_error(loader, yaml.constructor.ConstructorError(
                None, None,
                "Unrecognized Spec class %s" % spectype,
                node.start_mark))
            return

        if not isinstance(node, yaml.MappingNode):
            yaml_error(loader, yaml.constructor.ConstructorError(
                None, None,
                "expected a mapping node, but found %s" % node.id,
                node.start_mark))
            return

        specs = OrderedDict()
        for spec_key_node, spec_value_node in node.value:
            try:
                spec_key = str(loader.construct_scalar(spec_key_node))
            except yaml.MarkedYAMLError, e:
                yaml_error(loader, e)

            specs[spec_key] = construct_spec(spec_class, loader, spec_value_node)

        return specs

    def represent_relschemaspec(dumper, data):
        return dumper.represent_str(relschemaspec_to_str(data))

    def construct_relschemaspec(loader, node):
        schemastr = str(loader.construct_scalar(node))
        return str_to_relschemaspec(schemastr)

    def represent_spec(dumper, obj, yaml_tag=u'tag:yaml.org,2002:map', defaults=None):
        """
        Generic representer for serializing specs to YAML.  Rather than using
        the default PyYAML representer for python objects, we very carefully
        build up the YAML according to the parameter definitions in the __init__
        of each spec class.  This same format is used by construct_spec (the YAML
        constructor) to ensure that the spec objects are built consistently,
        whether it is done via YAML or the API.
        """

        if isinstance(obj, RRDDatapointSpec) and obj.shorthand:
            # Special case- we allow for a shorthand in specifying datapoints
            # as specs as strings rather than explicitly as a map.
            return dumper.represent_str(str(obj.shorthand))

        mapping = OrderedDict()
        cls = obj.__class__
        param_defs = cls.init_params()
        for param in param_defs:
            type_ = param_defs[param]['type']

            try:
                value = getattr(obj, param)
            except AttributeError:
                raise yaml.representer.RepresenterError(
                    "Unable to serialize %s object: %s, a supported parameter, is not accessible as a property." %
                    (cls.__name__, param))
                continue

            # Figure out what the default value is.  First, consider the default
            # value for this parameter (globally):
            default_value = param_defs[param].get('default', None)

            # Now, we need to handle 'DEFAULTS'.  If we're in a situation
            # where that is supported, and we're outputting a spec that
            # would be affected by it (not DEFAULTS itself, in other words),
            # then we look at the default value for this parameter, in case
            # it has changed the global default for this parameter.
            if hasattr(obj, 'name') and obj.name != 'DEFAULTS' and defaults is not None:
                default_value = getattr(defaults, param, default_value)

            if value == default_value:
                # If the value is a default value, we can omit it from the export.
                continue

            # If the value is null and the type is a list or dictionary, we can
            # assume it was some optional nested data and omit it.
            if value is None and (
               type_.startswith('dict') or
               type_.startswith('list') or
               type_.startswith('SpecsParameter')):
                continue

            if type_ == 'ZPropertyDefaultValue':
                # For zproperties, the actual data type of a default value
                # depends on the defined type of the zProperty.
                try:
                    type_ = {
                        'boolean': "bool",
                        'int': "int",
                        'float': "float",
                        'string': "str",
                        'password': "str",
                        'lines': "list(str)"
                    }.get(obj.type_, 'str')
                except KeyError:
                    type_ = "str"

            yaml_param = dumper.represent_str(param_defs[param]['yaml_param'])
            try:
                if type_ == "bool":
                    mapping[yaml_param] = dumper.represent_bool(value)
                elif type_.startswith("dict"):
                    mapping[yaml_param] = dumper.represent_dict(value)
                elif type_ == "float":
                    mapping[yaml_param] = dumper.represent_float(value)
                elif type_ == "int":
                    mapping[yaml_param] = dumper.represent_int(value)
                elif type_ == "list(class)":
                    # The "class" in this context is either a class reference or
                    # a class name (string) that refers to a class defined in
                    # this ZenPackSpec.
                    classes = [isinstance(x, type) and class_to_str(x) or x for x in value]
                    mapping[yaml_param] = dumper.represent_list(classes)
                elif type_.startswith("list(ExtraPath)"):
                    # Represent this as a list of lists of quoted strings (each on one line).
                    paths = []
                    for path in list(value):
                        # Force the regular expressions to be quoted, so we don't have any issues with that.
                        pathnodes = [dumper.represent_scalar(u'tag:yaml.org,2002:str', x, style="'") for x in path]
                        paths.append(yaml.SequenceNode(u'tag:yaml.org,2002:seq', pathnodes, flow_style=True))
                    mapping[yaml_param] = yaml.SequenceNode(u'tag:yaml.org,2002:seq', paths, flow_style=False)
                elif type_.startswith("list"):
                    mapping[yaml_param] = dumper.represent_list(value)
                elif type_ == "str":
                    mapping[yaml_param] = dumper.represent_str(value)
                elif type_ == 'RelationshipSchemaSpec':
                    mapping[yaml_param] = dumper.represent_str(relschemaspec_to_str(value))
                elif type_ == 'Severity':
                    mapping[yaml_param] = dumper.represent_str(severity_to_str(value))
                elif type_ == 'ExtraParams':
                    # ExtraParams is a special case, where any 'extra'
                    # parameters not otherwise defined in the init_params
                    # definition are tacked into a dictionary with no specific
                    # schema validation.  This is meant to be used in situations
                    # where it is impossible to know what parameters will be
                    # needed ahead of time, such as with a datasource
                    # that has been subclassed and had new properties added.
                    #
                    # Note: the extra parameters are required to have scalar
                    # values only.
                    for extra_param in value:
                        # add any values from an extraparams dict onto the spec's parameter list directly.
                        yaml_extra_param = dumper.represent_str(extra_param)

                        mapping[yaml_extra_param] = dumper.represent_data(value[extra_param])
                else:
                    m = re.match('^SpecsParameter\((.*)\)$', type_)
                    if m:
                        spectype = m.group(1)
                        specmapping = OrderedDict()
                        keys = sorted(value)
                        defaults = None
                        if 'DEFAULTS' in keys:
                            keys.remove('DEFAULTS')
                            keys.insert(0, 'DEFAULTS')
                            defaults = value['DEFAULTS']
                        for key in keys:
                            spec = value[key]
                            if type(spec).__name__ != spectype:
                                raise yaml.representer.RepresenterError(
                                    "Unable to serialize %s object (%s):  Expected an object of type %s" %
                                    (type(spec).__name__, key, spectype))
                            else:
                                specmapping[dumper.represent_str(key)] = represent_spec(dumper, spec, defaults=defaults)

                        specmapping_value = []
                        node = yaml.MappingNode(yaml_tag, specmapping_value)
                        specmapping_value.extend(specmapping.items())
                        mapping[yaml_param] = node
                    else:
                        raise yaml.representer.RepresenterError(
                            "Unable to serialize %s object: %s, a supported parameter, is of an unrecognized type (%s)." %
                            (cls.__name__, param, type_))
            except yaml.representer.RepresenterError:
                raise
            except Exception, e:
                raise yaml.representer.RepresenterError(
                    "Unable to serialize %s object (param %s, type %s, value %s): %s" %
                    (cls.__name__, param, type_, value, e))

            if param in param_defs and param_defs[param]['yaml_block_style']:
                mapping[yaml_param].flow_style = False

        mapping_value = []
        node = yaml.MappingNode(yaml_tag, mapping_value)
        mapping_value.extend(mapping.items())

        # Return a node describing the mapping (dictionary) of the params
        # used to build this spec.
        return node

    def construct_spec(cls, loader, node):
        """
        Generic constructor for deserializing specs from YAML.   Should be
        the opposite of represent_spec, and works in the same manner (with its
        parsing and validation directed by the init_params of each spec class)
        """

        if issubclass(cls, RRDDatapointSpec) and isinstance(node, yaml.ScalarNode):
            # Special case- we allow for a shorthand in specifying datapoint specs.
            return dict(shorthand=loader.construct_scalar(node))

        param_defs = cls.init_params()
        params = {}
        if not isinstance(node, yaml.MappingNode):
            yaml_error(loader, yaml.constructor.ConstructorError(
                None, None,
                "expected a mapping node, but found %s" % node.id,
                node.start_mark))

        params['_source_location'] = "%s: %s-%s" % (
            os.path.basename(node.start_mark.name),
            node.start_mark.line+1,
            node.end_mark.line+1)

        # TODO: When deserializing, we should check if required properties are present.

        param_name_map = {}
        for param in param_defs:
            param_name_map[param_defs[param]['yaml_param']] = param

        extra_params = None
        for key in param_defs:
            if param_defs[key]['type'] == 'ExtraParams':
                if extra_params:
                    yaml_error(loader, yaml.constructor.ConstructorError(
                        None, None,
                        "Only one ExtraParams parameter may be specified.",
                        node.start_mark))
                extra_params = key
                params[extra_params] = {}

        for key_node, value_node in node.value:
            yaml_key = str(loader.construct_scalar(key_node))

            if yaml_key not in param_name_map:
                if extra_params:
                    # If an 'extra_params' parameter is defined for this spec,
                    # we take all unrecognized paramters and stuff them into
                    # a single parameter, which is a dictonary of "extra" parameters.
                    #
                    # Note that the values of these extra parameters need to be
                    # scalars, not nested maps or something like that.
                    params[extra_params][yaml_key] = loader.construct_scalar(value_node)
                    continue
                else:
                    yaml_error(loader, yaml.constructor.ConstructorError(
                        None, None,
                        "Unrecognized parameter '%s' found while processing %s" % (yaml_key, cls.__name__),
                        key_node.start_mark))
                    continue

            key = param_name_map[yaml_key]
            expected_type = param_defs[key]['type']

            if expected_type == 'ZPropertyDefaultValue':
                # For zproperties, the actual data type of a default value
                # depends on the defined type of the zProperty.

                try:
                    zPropType = [x[1].value for x in node.value if x[0].value == 'type'][0]
                except Exception:
                    # type was not specified, so we assume the default (string)
                    zPropType = 'string'

                try:
                    expected_type = {
                        'boolean': "bool",
                        'int': "int",
                        'float': "float",
                        'string': "str",
                        'password': "str",
                        'lines': "list(str)"
                    }.get(zPropType, 'str')
                except KeyError:
                    yaml_error(loader, yaml.constructor.ConstructorError(
                        None, None,
                        "Invalid zProperty type_ '%s' for property %s found while processing %s" % (zPropType, key, cls.__name__),
                        key_node.start_mark))
                    continue

            try:
                if expected_type == "bool":
                    params[key] = loader.construct_yaml_bool(value_node)
                elif expected_type.startswith("dict(SpecsParameter("):
                    m = re.match('^dict\(SpecsParameter\((.*)\)\)$', expected_type)
                    if m:
                        spectype = m.group(1)

                        if not isinstance(node, yaml.MappingNode):
                            yaml_error(loader, yaml.constructor.ConstructorError(
                                None, None,
                                "expected a mapping node, but found %s" % node.id,
                                node.start_mark))
                            continue
                        specs = OrderedDict()
                        for spec_key_node, spec_value_node in value_node.value:
                            spec_key = str(loader.construct_scalar(spec_key_node))

                            specs[spec_key] = construct_specsparameters(loader, spec_value_node, spectype)
                        params[key] = specs
                    else:
                        raise Exception("Unable to determine specs parameter type in '%s'" % expected_type)
                elif expected_type.startswith("dict"):
                    params[key] = loader.construct_mapping(value_node)
                elif expected_type == "float":
                    params[key] = float(loader.construct_scalar(value_node))
                elif expected_type == "int":
                    params[key] = int(loader.construct_scalar(value_node))
                elif expected_type == "list(class)":
                    classnames = loader.construct_sequence(value_node)
                    classes = []
                    for c in classnames:
                        class_ = str_to_class(c)
                        if class_ is None:
                            # local reference to a class being defined in
                            # this zenpack.  (ideally we should verify that
                            # the name is valid, but this is not possible
                            # in a one-pass parsing of the yaml).
                            classes.append(c)
                        else:
                            classes.append(class_)
                    # ZPL defines "class" as either a string representing a
                    # class in this definition, or a class object representing
                    # an external class.
                    params[key] = classes
                elif expected_type == 'list(ExtraPath)':
                    if not isinstance(value_node, yaml.SequenceNode):
                        raise yaml.constructor.ConstructorError(
                            None, None,
                            "expected a sequence node, but found %s" % value_node.id,
                            value_node.start_mark)
                    extra_paths = []
                    for path_node in value_node.value:
                        extra_paths.append(loader.construct_sequence(path_node))
                    params[key] = extra_paths
                elif expected_type == "list(RelationshipSchemaSpec)":
                    schemaspecs = []
                    for s in loader.construct_sequence(value_node):
                        schemaspecs.append(str_to_relschemaspec(s))
                    params[key] = schemaspecs
                elif expected_type.startswith("list"):
                    params[key] = loader.construct_sequence(value_node)
                elif expected_type == "str":
                    params[key] = str(loader.construct_scalar(value_node))
                elif expected_type == 'RelationshipSchemaSpec':
                    schemastr = str(loader.construct_scalar(value_node))
                    params[key] = str_to_relschemaspec(schemastr)
                elif expected_type == 'Severity':
                    severitystr = str(loader.construct_scalar(value_node))
                    params[key] = str_to_severity(severitystr)
                else:
                    m = re.match('^SpecsParameter\((.*)\)$', expected_type)
                    if m:
                        spectype = m.group(1)
                        params[key] = construct_specsparameters(loader, value_node, spectype)
                    else:
                        raise Exception("Unhandled type '%s'" % expected_type)

            except yaml.constructor.ConstructorError, e:
                yaml_error(loader, e)
            except Exception, e:
                yaml_error(loader, yaml.constructor.ConstructorError(
                    None, None,
                    "Unable to deserialize %s object (param %s): %s" % (cls.__name__, key_node.value, e),
                    value_node.start_mark), exc_info=sys.exc_info())

        return params

    def represent_zenpackspec(dumper, obj):
        return represent_spec(dumper, obj, yaml_tag=u'!ZenPackSpec')

    def construct_zenpackspec(loader, node):
        params = construct_spec(ZenPackSpec, loader, node)
        name = params.pop("name")

        fatal = not getattr(loader, 'warnings', False)
        yaml_errored = getattr(loader, 'yaml_errored', False)

        try:
            return ZenPackSpec(name, **params)
        except Exception, e:
            if yaml_errored and not fatal:
                LOG.error("(possibly because of earlier errors) %s" % e)
            else:
                raise

        return None

    # These subclasses exist so that each copy of zenpacklib installed on a
    # zenoss system provide their own loader (for add_constructor and yaml.load)
    # and its own dumper (for add_representer) so that the proper methods will
    # be used for this specific zenpacklib.
    class Loader(yaml.Loader):
        pass

    class Dumper(yaml.Dumper):
        pass

    class WarningLoader(Loader):
        warnings = True
        yaml_errored = False

    Dumper.add_representer(ZenPackSpec, represent_zenpackspec)
    Dumper.add_representer(DeviceClassSpec, represent_spec)
    Dumper.add_representer(ZPropertySpec, represent_spec)
    Dumper.add_representer(ClassSpec, represent_spec)
    Dumper.add_representer(ClassPropertySpec, represent_spec)
    Dumper.add_representer(ClassRelationshipSpec, represent_spec)
    Dumper.add_representer(RelationshipSchemaSpec, represent_relschemaspec)
    Loader.add_constructor(u'!ZenPackSpec', construct_zenpackspec)

    yaml.add_path_resolver(u'!ZenPackSpec', [], Loader=Loader)

    Dumper.add_representer(ZenPackSpecParams, represent_zenpackspec)
    Dumper.add_representer(DeviceClassSpecParams, represent_spec)
    Dumper.add_representer(ZPropertySpecParams, represent_spec)
    Dumper.add_representer(ClassSpecParams, represent_spec)
    Dumper.add_representer(ClassPropertySpecParams, represent_spec)
    Dumper.add_representer(ClassRelationshipSpecParams, represent_spec)
    Dumper.add_representer(RRDTemplateSpecParams, represent_spec)
    Dumper.add_representer(RRDThresholdSpecParams, represent_spec)
    Dumper.add_representer(RRDDatasourceSpecParams, represent_spec)
    Dumper.add_representer(RRDDatapointSpecParams, represent_spec)
    Dumper.add_representer(GraphDefinitionSpecParams, represent_spec)
    Dumper.add_representer(GraphPointSpecParams, represent_spec)


# Public Functions ##########################################################

def load_yaml(yaml_filename=None):
    """Load YAML from yaml_filename.

    Loads from zenpack.yaml in the current directory if
    yaml_filename isn't specified.

    """
    CFG = None

    if YAML_INSTALLED:
        if yaml_filename is None:
            yaml_filename = os.path.join(
                os.path.dirname(__file__), 'zenpack.yaml')

        try:
            CFG = yaml.load(file(yaml_filename, 'r'), Loader=Loader)
        except Exception as e:
            LOG.error(e)
    else:
        zenpack_name = None

        # Guess ZenPack name from the path.
        dirname = __file__
        while dirname != '/':
            dirname = os.path.dirname(dirname)
            basename = os.path.basename(dirname)
            if basename.startswith('ZenPacks.'):
                zenpack_name = basename
                break

        LOG.error(
            '%s requires PyYAML. Run "easy_install PyYAML".',
            zenpack_name or 'ZenPack')

        # Create a simple ZenPackSpec that should be harmless.
        CFG = ZenPackSpec(name=zenpack_name or 'NoYAML')

    if CFG:
        CFG.create()
    else:
        LOG.error("Unable to load %s", yaml_filename)
    return CFG


def enableTesting():
    """Enable test mode. Only call from code under tests/.

    If this is called from production code it will cause all Zope
    clients to start in test mode. Which isn't useful for anything but
    unit testing.

    """
    global TestCase

    if TestCase:
        return

    from Products.ZenTestCase.BaseTestCase import BaseTestCase
    from transaction._transaction import Transaction

    class TestCase(BaseTestCase):

        # As in BaseTestCase, the default behavior is to disable
        # all logging from within a unit test.  To enable it,
        # set disableLogging = False in your subclass.  This is
        # recommended during active development, but is too noisy
        # to leave as the default.
        disableLogging = True

        def afterSetUp(self):
            super(TestCase, self).afterSetUp()

            # Not included with BaseTestCase. Needed to test that UI
            # components have been properly registered.
            from Products.Five import zcml
            import Products.ZenUI3
            zcml.load_config('configure.zcml', Products.ZenUI3)

            if not hasattr(self, 'zenpack_module_name') or self.zenpack_module_name is None:
                self.zenpack_module_name = '.'.join(self.__module__.split('.')[:-2])

            try:
                zenpack_module = importlib.import_module(self.zenpack_module_name)
            except Exception:
                LOG.exception("Unable to load zenpack named '%s' - is it installed? (%s)", self.zenpack_module_name)
                raise

            zenpackspec = getattr(zenpack_module, 'CFG', None)
            if not zenpackspec:
                raise NameError(
                    "name {!r} is not defined"
                    .format('.'.join((self.zenpack_module_name, 'CFG'))))

            zenpackspec.test_setup()

            import Products.ZenEvents
            zcml.load_config('meta.zcml', Products.ZenEvents)

            try:
                import ZenPacks.zenoss.DynamicView
                zcml.load_config('configure.zcml', ZenPacks.zenoss.DynamicView)
            except ImportError:
                pass

            try:
                import ZenPacks.zenoss.Impact
                zcml.load_config('meta.zcml', ZenPacks.zenoss.Impact)
                zcml.load_config('configure.zcml', ZenPacks.zenoss.Impact)
            except ImportError:
                pass

            try:
                zcml.load_config('configure.zcml', zenpack_module)
            except IOError:
                pass

            # BaseTestCast.afterSetUp already hides transaction.commit. So we also
            # need to hide transaction.abort.
            self._transaction_abort = Transaction.abort
            Transaction.abort = lambda *x: None

        def beforeTearDown(self):
            super(TestCase, self).beforeTearDown()

            if hasattr(self, '_transaction_abort'):
                Transaction.abort = self._transaction_abort

        # If the exception occurs during setUp, beforeTearDown is not called,
        # so we also need to restore abort here as well:
        def _close(self):
            if hasattr(self, '_transaction_abort'):
                Transaction.abort = self._transaction_abort

            super(TestCase, self)._close()


def ucfirst(text):
    """Return text with the first letter uppercased.

    This differs from str.capitalize and str.title methods in that it
    doesn't lowercase the remainder of text.

    """
    return text[0].upper() + text[1:]


def relname_from_classname(classname, plural=False):
    """Return relationship name given classname and plural flag."""

    if '.' in classname:
        classname = classname.replace('.', '_').lower()

    relname = list(classname)
    for i, c in enumerate(classname):
        if relname[i].isupper():
            relname[i] = relname[i].lower()
        else:
            break

    return ''.join((''.join(relname), 's' if plural else ''))


def relationships_from_yuml(yuml):
    """Return schema relationships definition given yuml text.

    The yuml text required is a subset of what is supported by yUML
    (http://yuml.me). See the following example:

        // Containing relationships.
        [APIC]++ -[FabricPod]
        [APIC]++ -[FvTenant]
        [FvTenant]++ -[VzBrCP]
        [FvTenant]++ -[FvAp]
        [FvAp]++ -[FvAEPg]
        [FvAEPg]++ -[FvRsProv]
        [FvAEPg]++ -[FvRsCons]
        // Non-containing relationships.
        [FvBD]1 -.- *[FvAEPg]
        [VzBrCP]1 -.- *[FvRsProv]
        [VzBrCP]1 -.- *[FvRsCons]

    The created relationships are given default names that orginarily
    should be used. However, in some cases such as when one class has
    multiple relationships to the same class, relationships must be
    explicitly named. That would be done as in the following example:

        // Explicitly-Named Relationships
        [Pool]*default_sr -.-default_for_pools 0..1[SR]
        [Pool]*suspend_image_sr -.-suspend_image_for_pools *[SR]
        [Pool]*crash_dump_sr -.-crash_dump_for_pools *[SR]

    The yuml parameter can be specified either as a newline-delimited
    string, or as a tuple or list of relationships.

    """
    classes = []
    match_comment = re.compile(r'^//').search

    match_line = re.compile(
        r'\[(?P<left_classname>[^\]]+)\]'
        r'(?P<left_cardinality>[\.\*\+\d]*)'
        r'(?P<left_relname>[a-zA-Z_]*)'
        r'\s*?'
        r'(?P<relationship_separator>[\-\.]+)'
        r'(?P<right_relname>[a-zA-Z_]*)'
        r'\s*?'
        r'(?P<right_cardinality>[\.\*\+\d]*)'
        r'\[(?P<right_classname>[^\]]+)\]'
        ).search

    if isinstance(yuml, basestring):
        yuml_lines = yuml.strip().splitlines()

    for line in yuml_lines:
        line = line.strip()

        if not line:
            continue

        if match_comment(line):
            continue

        match = match_line(line)
        if not match:
            raise ValueError("parse error in relationships_from_yuml at %s" % line)

        left_class = match.group('left_classname')
        right_class = match.group('right_classname')
        left_relname = match.group('left_relname')
        left_cardinality = match.group('left_cardinality')
        right_relname = match.group('right_relname')
        right_cardinality = match.group('right_cardinality')

        if '++' in left_cardinality:
            left_type = 'ToManyCont'
        elif '*' in right_cardinality:
            left_type = 'ToMany'
        else:
            left_type = 'ToOne'

        if '++' in right_cardinality:
            right_type = 'ToManyCont'
        elif '*' in left_cardinality:
            right_type = 'ToMany'
        else:
            right_type = 'ToOne'

        if not left_relname:
            left_relname = relname_from_classname(
                right_class, plural=left_type != 'ToOne')

        if not right_relname:
            right_relname = relname_from_classname(
                left_class, plural=right_type != 'ToOne')

        # Order them correctly (larger one on the right)
        if RelationshipSchemaSpec.valid_orientation(left_type, right_type):
            classes.append(dict(
                left_class=left_class,
                left_relname=left_relname,
                left_type=left_type,
                right_type=right_type,
                right_class=right_class,
                right_relname=right_relname
            ))
        else:
            # flip them around
            classes.append(dict(
                left_class=right_class,
                left_relname=right_relname,
                left_type=right_type,
                right_type=left_type,
                right_class=left_class,
                right_relname=left_relname
            ))

    return classes


def MethodInfoProperty(method_name):
    """Return a property with the Infos for object(s) returned by a method.

    A list of Info objects is returned for methods returning a list, or a single
    one for those returning a single value.
    """
    def getter(self):
        try:
            return Zuul.info(getattr(self._object, method_name)())
        except TypeError:
            # If not callable avoid the traceback and send the property
            return Zuul.info(getattr(self._object, method_name))

    return property(getter)


def EnumInfoProperty(data, enum):
    """Return a property filtered via an enum."""
    def getter(self, data, enum):
        if not enum:
            return ProxyProperty(data)
        else:
            data = getattr(self._object, data, None)
            try:
                data = int(data)
                return Zuul.info(enum[data])
            except Exception:
                return Zuul.info(data)

    return property(lambda x: getter(x, data, enum))


def RelationshipInfoProperty(relationship_name):
    """Return a property with the Infos for object(s) in the relationship.

    A list of Info objects is returned for ToMany relationships, and a
    single Info object is returned for ToOne relationships.

    """
    def getter(self):
        return Zuul.info(getattr(self._object, relationship_name)())

    return property(getter)


def RelationshipLengthProperty(relationship_name):
    """Return a property representing number of objects in relationship."""
    def getter(self):
        relationship = getattr(self._object, relationship_name)
        try:
            return relationship.countObjects()
        except Exception:
            return len(relationship())

    return property(getter)


def RelationshipGetter(relationship_name):
    """Return getter for id or ids in relationship_name."""
    def getter(self):
        try:
            relationship = getattr(self, relationship_name)
            if isinstance(relationship, ToManyRelationship):
                return self.getIdsInRelationship(getattr(self, relationship_name))
            elif isinstance(relationship, ToOneRelationship):
                return self.getIdForRelationship(relationship)
        except Exception:
            LOG.error(
                "error getting %s ids for %s",
                relationship_name, self.getPrimaryUrlPath())
            raise

    return getter


def RelationshipSetter(relationship_name):
    """Return setter for id or ides in relationship_name."""
    def setter(self, id_or_ids):
        try:
            relationship = getattr(self, relationship_name)
            if isinstance(relationship, ToManyRelationship):
                self.setIdsInRelationship(relationship, id_or_ids)
            elif isinstance(relationship, ToOneRelationship):
                self.setIdForRelationship(relationship, id_or_ids)
        except Exception:
            LOG.error(
                "error setting %s ids for %s",
                relationship_name, self.getPrimaryUrlPath())
            raise

    return setter


# Private Types #############################################################

OrderAndValue = collections.namedtuple('OrderAndValue', ['order', 'value'])


# Private Functions #########################################################

def get_zenpack_path(zenpack_name):
    """Return filesystem path for given ZenPack."""
    zenpack_module = importlib.import_module(zenpack_name)
    if hasattr(zenpack_module, '__file__'):
        return os.path.dirname(zenpack_module.__file__)
    else:
        return None


def ordered_values(iterable):
    """Return ordered list of values for iterable of OrderAndValue instances."""
    return [
        x.value for x in sorted(iterable, key=operator.attrgetter('order'))]


def pluralize(text):
    """Return pluralized version of text.

    Totally naive implementation currently. Could use a third party
    library if we knew it would be installed.
    """
    if text.endswith('s'):
        return '{}es'.format(text)

    return '{}s'.format(text)


def fix_kwargs(kwargs):
    """Return kwargs with reserved words suffixed with _."""
    new_kwargs = {}
    for k, v in kwargs.items():
        if k in ('class', 'type'):
            new_kwargs['{}_'.format(k)] = v
        else:
            new_kwargs[k] = v

    return new_kwargs


def update(d, u):
    """Return dict d updated with nested data from dict u."""
    for k, v in u.iteritems():
        if isinstance(v, collections.Mapping):
            r = update(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d


def catalog_search(scope, name, *args, **kwargs):
    """Return iterable of matching brains in named catalog."""

    catalog = getattr(scope, '{}Search'.format(name), None)
    if not catalog:
        LOG.debug("Catalog %sSearch not found at %s.  It should be created when the first included component is indexed" % (name, scope))
        return []

    if args:
        if isinstance(args[0], BaseQuery):
            return catalog.evalAdvancedQuery(args[0])
        elif isinstance(args[0], dict):
            return catalog(args[0])
        else:
            raise TypeError(
                "search() argument must be a BaseQuery or a dict, "
                "not {0!r}"
                .format(type(args[0]).__name__))

    return catalog(**kwargs)


def apply_defaults(dictionary, default_defaults=None, leave_defaults=False):
    """Modify dictionary to put values from DEFAULTS key into other keys.

    Unless leave_defaults is set to True, the DEFAULTS key will no longer exist
    in dictionary. dictionary must be a dictionary of dictionaries.

    Example usage:

        >>> mydict = {
        ...     'DEFAULTS': {'is_two': False},
        ...     'key1': {'number': 1},
        ...     'key2': {'number': 2, 'is_two': True},
        ... }
        >>> apply_defaults(mydict)
        >>> print mydict
        {
            'key1': {'number': 1, 'is_two': False},
            'key2': {'number': 2, 'is_two': True},
        }

    """
    if default_defaults:
        dictionary.setdefault('DEFAULTS', {})
        for default_key, default_value in default_defaults.iteritems():
            dictionary['DEFAULTS'].setdefault(default_key, default_value)

    if 'DEFAULTS' in dictionary:
        if leave_defaults:
            defaults = dictionary.get('DEFAULTS')
        else:
            defaults = dictionary.pop('DEFAULTS')
        for k, v in dictionary.iteritems():
            dictionary[k] = dict(defaults, **v)


def get_symbol_name(*args):
    """Return fully-qualified symbol name given path args.

    Example usage:

        >>> get_symbol_name('ZenPacks.example.Name')
        'ZenPacks.example.Name'

        >>> get_symbol_name('ZenPacks.example.Name', 'schema')
        'ZenPacks.example.Name.schema'

        >>> get_symbol_name('ZenPacks.example.Name', 'schema', 'APIC')
        'ZenPacks.example.Name.schema.APIC'

        >>> get_symbol_name('ZenPacks.example.Name', 'schema.Pool')
        'ZenPacks.example.Name.schema.Pool'

    No verification is done. Names for symbols that don't exist may
    be returned.

    """
    return '.'.join(x for x in args if x)


def create_module(*args):
    """Import and return module given path args.

    See get_symbol_name documentation for usage. May raise ImportError.

    """
    module_name = get_symbol_name(*args)
    try:
        return importlib.import_module(module_name)
    except ImportError:
        module = imp.new_module(module_name)
        module.__name__ = module_name
        sys.modules[module_name] = module

        module_parts = module_name.split('.')

        if len(module_parts) > 1:
            parent_module_name = get_symbol_name(*module_parts[:-1])
            parent_module = create_module(parent_module_name)
            setattr(parent_module, module_parts[-1], module)

    return importlib.import_module(module_name)


def get_class_factory(klass):
    """Return class factory for class."""
    if issubclass(klass, IInfo):
        return InterfaceClass
    else:
        return type


def create_schema_class(schema_module, classname, bases, attributes):
    """Create and return described schema class."""
    if isinstance(schema_module, basestring):
        schema_module = create_module(schema_module)

    schema_class = getattr(schema_module, classname, None)
    if schema_class:
        return schema_class

    class_factory = get_class_factory(bases[0])
    schema_class = class_factory(classname, tuple(bases), attributes)
    schema_class.__module__ = schema_module.__name__
    setattr(schema_module, classname, schema_class)

    return schema_class


def create_stub_class(module, schema_class, classname):
    """Create and return described stub class."""
    if isinstance(module, basestring):
        module = create_module(module)

    concrete_class = getattr(module, classname, None)
    if concrete_class:
        return concrete_class

    class_factory = get_class_factory(schema_class)
    stub_class = class_factory(classname, (schema_class,), {})
    stub_class.__module__ = module.__name__
    setattr(module, classname, stub_class)

    return stub_class


def create_class(module, schema_module, classname, bases, attributes):
    """Create and return described class."""
    if isinstance(module, basestring):
        module = create_module(module)

    schema_class = create_schema_class(
        schema_module, classname, bases, attributes)

    return create_stub_class(module, schema_class, classname)


# Impact Stuff ##############################################################

try:
    from ZenPacks.zenoss.Impact.impactd.relations import ImpactEdge, DSVRelationshipProvider, RelationshipEdgeError
    from ZenPacks.zenoss.Impact.impactd.interfaces import IRelationshipDataProvider
except ImportError:
    IMPACT_INSTALLED = False
else:
    IMPACT_INSTALLED = True

try:
    from ZenPacks.zenoss.DynamicView import BaseRelation, BaseGroup
    from ZenPacks.zenoss.DynamicView import TAG_IMPACTED_BY, TAG_IMPACTS, TAG_ALL
    from ZenPacks.zenoss.DynamicView.interfaces import IRelatable, IRelationsProvider, IGroup
    from ZenPacks.zenoss.DynamicView.dynamicview import DynamicViewMappings
    from ZenPacks.zenoss.DynamicView.model.adapters import BaseRelatable, BaseRelationsProvider

except ImportError:
    DYNAMICVIEW_INSTALLED = False
else:
    DYNAMICVIEW_INSTALLED = True

if IMPACT_INSTALLED:
    class ImpactRelationshipDataProvider(object):

        """Generic Impact RelationshipDataProvider adapter factory.

        Implements IRelationshipDataProvider.

        Creates impact relationships by introspecting the adapted object's
        impacted_by and impacts properties.

        """

        implements(IRelationshipDataProvider)
        adapts(DeviceBase, ComponentBase)

        def __init__(self, adapted):
            self.adapted = adapted

        @property
        def relationship_provider(self):
            """Return string indicating from where generated edges came.

            Required by IRelationshipDataProvider.

            """
            return getattr(self.adapted, 'zenpack_name', 'ZenPack')

        def belongsInImpactGraph(self):
            """Return True so generated edges will show in impact graph.

            Required by IRelationshipDataProvider.

            """
            return True

        def getEdges(self):
            """Generate ImpactEdge instances for adapted object.

            Required by IRelationshipDataProvider.

            """
            provider = self.relationship_provider
            myguid = IGlobalIdentifier(self.adapted).getGUID()
            impacted_by = getattr(self.adapted, 'impacted_by', [])
            if impacted_by:
                for methodname in impacted_by:
                    for impactor_guid in self.get_remote_guids(methodname):
                        yield ImpactEdge(impactor_guid, myguid, provider)

            impacts = getattr(self.adapted, 'impacts', [])
            if impacts:
                for methodname in impacts:
                    for impactee_guid in self.get_remote_guids(methodname):
                        yield ImpactEdge(myguid, impactee_guid, provider)

        def get_remote_guids(self, methodname):
            """Generate object GUIDs returned by adapted.methodname()."""
            method = getattr(self.adapted, methodname, None)
            if not method or not callable(method):
                LOG.warning(
                    "no %r relationship or method for %r",
                    methodname,
                    self.adapted.meta_type)

                return

            r = method()
            if not r:
                return

            try:
                for obj in r:
                    yield IGlobalIdentifier(obj).getGUID()

            except TypeError:
                yield IGlobalIdentifier(r).getGUID()

if DYNAMICVIEW_INSTALLED:
    class DynamicViewRelatable(BaseRelatable):
        """Generic DynamicView Relatable adapter (IRelatable)

        Places object into a group based upon the class name.
        """

        implements(IRelatable)
        adapts(DeviceBase, ComponentBase)

        @property
        def id(self):
            return self._adapted.getPrimaryId()

        @property
        def name(self):
            return self._adapted.titleOrId()

        @property
        def tags(self):
            return set([self._adapted.meta_type])

        @property
        def group(self):
            return self._adapted.class_dynamicview_group

    class DynamicViewRelationsProvider(BaseRelationsProvider):
        """Generic DynamicView RelationsProvider subscription adapter (IRelationsProvider)

        Creates impact relationships by introspecting the adapted object's
        impacted_by and impacts properties.

        Note that these impact relationships will also be exposed through to
        impact, so it is not necessary to activate both
        ImpactRelationshipDataProvider and DynamicViewRelatable /
        DynamicViewRelationsProvider for a given model class.
        """
        implements(IRelationsProvider)
        adapts(DeviceBase, ComponentBase)

        def relations(self, type=TAG_ALL):
            target = IRelatable(self._adapted)
            relations = getattr(self._adapted, 'dynamicview_relations', {})

            # Group methods by type to allow easy tagging of multiple types
            # per yielded relation. This allows supporting the special TAG_ALL
            # type without duplicating work or relations.
            types_by_methodname = collections.defaultdict(set)
            if type == TAG_ALL:
                for ltype, lmethodnames in relations.items():
                    for lmethodname in lmethodnames:
                        types_by_methodname[lmethodname].add(ltype)
            else:
                for lmethodname in relations.get(type, []):
                    types_by_methodname[lmethodname].add(type)

            for methodname, type_set in types_by_methodname.items():
                for remote in self.get_remote_relatables(methodname):
                    yield BaseRelation(target, remote, list(type_set))

        def get_remote_relatables(self, methodname):
            """Generate object relatables returned by adapted.methodname()."""
            method = getattr(self._adapted, methodname, None)
            if not method or not callable(method):
                LOG.warning(
                    "no %r relationship or method for %r",
                    methodname,
                    self._adapted.meta_type)

                return

            r = method()
            if not r:
                return

            try:
                for obj in r:
                    yield IRelatable(obj)

            except TypeError:
                yield IRelatable(r)


# Static Utilities ##########################################################

def create_zenpack_srcdir(zenpack_name):
    """Create a new ZenPack source directory."""
    import shutil
    import errno

    if os.path.exists(zenpack_name):
        sys.exit("{} directory already exists.".format(zenpack_name))

    print "Creating source directory for {}:".format(zenpack_name)

    zenpack_name_parts = zenpack_name.split('.')

    packages = reduce(
        lambda x, y: x + ['.'.join((x[-1], y))],
        zenpack_name_parts[1:],
        ['ZenPacks'])

    namespace_packages = packages[:-1]

    # Create ZenPacks.example.Thing/ZenPacks/example/Thing directory.
    module_directory = os.path.join(zenpack_name, *zenpack_name_parts)

    try:
        print "  - making directory: {}".format(module_directory)
        os.makedirs(module_directory)
    except OSError as e:
        if e.errno == errno.EEXIST:
            sys.exit("{} directory already exists.".format(zenpack_name))
        else:
            sys.exit(
                "Failed to create {!r} directory: {}"
                .format(zenpack_name, e.strerror))

    # Create setup.py.
    setup_py_fname = os.path.join(zenpack_name, 'setup.py')
    print "  - creating file: {}".format(setup_py_fname)
    with open(setup_py_fname, 'w') as setup_py_f:
        setup_py_f.write(
            SETUP_PY.format(
                zenpack_name=zenpack_name,
                namespace_packages=namespace_packages,
                packages=packages))

    # Create MANIFEST.in.
    manifest_in_fname = os.path.join(zenpack_name, 'MANIFEST.in')
    print "  - creating file: {}".format(manifest_in_fname)
    with open(manifest_in_fname, 'w') as manifest_in_f:
        manifest_in_f.write("graft ZenPacks\n")

    # Create __init__.py files in all namespace directories.
    for namespace_package in namespace_packages:
        namespace_init_fname = os.path.join(
            zenpack_name,
            os.path.join(*namespace_package.split('.')),
            '__init__.py')

        print "  - creating file: {}".format(namespace_init_fname)
        with open(namespace_init_fname, 'w') as namespace_init_f:
            namespace_init_f.write(
                "__import__('pkg_resources').declare_namespace(__name__)\n")

    # Create __init__.py in ZenPack module directory.
    init_fname = os.path.join(module_directory, '__init__.py')
    print "  - creating file: {}".format(init_fname)
    with open(init_fname, 'w') as init_f:
        init_f.write(
            "from . import zenpacklib\n\n"
            "zenpacklib.load_yaml()\n")

    # Create zenpack.yaml in ZenPack module directory.
    yaml_fname = os.path.join(module_directory, 'zenpack.yaml')
    print "  - creating file: {}".format(yaml_fname)
    with open(yaml_fname, 'w') as yaml_f:
        yaml_f.write("name: {}\n".format(zenpack_name))

    # Copy zenpacklib.py (this file) into ZenPack module directory.
    print "  - copying: {} to {}".format(__file__, module_directory)
    shutil.copy2(__file__, module_directory)


# Templates #################################################################

JS_LINK_FROM_GRID = """
Ext.apply(Zenoss.render, {
    zenpacklib_{zenpack_id_prefix}_entityLinkFromGrid: function(obj, metaData, record, rowIndex, colIndex) {
        if (!obj)
            return;

        if (typeof(obj) == 'string')
            obj = record.data;

        if (!obj.title && obj.name)
            obj.title = obj.name;

        var isLink = false;

        if (this.refName == 'componentgrid') {
            // Zenoss >= 4.2 / ExtJS4
            if (colIndex != 1 || this.subComponentGridPanel)
                isLink = true;
        } else {
            // Zenoss < 4.2 / ExtJS3
            if (!this.panel || this.panel.subComponentGridPanel)
                isLink = true;
        }

        if (isLink) {
            return '<a href="'+obj.uid+'"onClick="Ext.getCmp(\\'component_card\\').componentgrid.jumpToEntity(\\''+obj.uid +'\\', \\''+obj.meta_type+'\\');return false;">'+obj.title+'</a>';
        } else {
            return obj.title;
        }
    },

    zenpacklib_{zenpack_id_prefix}_entityTypeLinkFromGrid: function(obj, metaData, record, rowIndex, colIndex) {
        if (!obj)
            return;

        if (typeof(obj) == 'string')
            obj = record.data;

        if (!obj.title && obj.name)
            obj.title = obj.name;

        var isLink = false;

        if (this.refName == 'componentgrid') {
            // Zenoss >= 4.2 / ExtJS4
            if (colIndex != 1 || this.subComponentGridPanel)
                isLink = true;
        } else {
            // Zenoss < 4.2 / ExtJS3
            if (!this.panel || this.panel.subComponentGridPanel)
                isLink = true;
        }

        if (isLink) {
            return '<a href="javascript:Ext.getCmp(\\'component_card\\').componentgrid.jumpToEntity(\\''+obj.uid+'\\', \\''+obj.meta_type+'\\');">'+obj.title+'</a> (' + obj.class_label + ')';
        } else {
            return obj.title;
        }
    }

});

ZC.ZPL_{zenpack_id_prefix}_ComponentGridPanel = Ext.extend(ZC.ComponentGridPanel, {
    subComponentGridPanel: false,

    jumpToEntity: function(uid, meta_type) {
        var tree = Ext.getCmp('deviceDetailNav').treepanel;
        var tree_selection_model = tree.getSelectionModel();
        var components_node = tree.getRootNode().findChildBy(
            function(n) {
                if (n.data) {
                    // Zenoss >= 4.2 / ExtJS4
                    return n.data.text == 'Components';
                }

                // Zenoss < 4.2 / ExtJS3
                return n.text == 'Components';
            });

        var component_card = Ext.getCmp('component_card');

        if (components_node.data) {
            // Zenoss >= 4.2 / ExtJS4
            component_card.setContext(components_node.data.id, meta_type);
        } else {
            // Zenoss < 4.2 / ExtJS3
            component_card.setContext(components_node.id, meta_type);
        }

        component_card.selectByToken(uid);

        var component_type_node = components_node.findChildBy(
            function(n) {
                if (n.data) {
                    // Zenoss >= 4.2 / ExtJS4
                    return n.data.id == meta_type;
                }

                // Zenoss < 4.2 / ExtJS3
                return n.id == meta_type;
            });

        if (component_type_node.select) {
            tree_selection_model.suspendEvents();
            component_type_node.select();
            tree_selection_model.resumeEvents();
        } else {
            tree_selection_model.select([component_type_node], false, true);
        }
    }
});

Ext.reg('ZPL_{zenpack_id_prefix}_ComponentGridPanel', ZC.ZPL_{zenpack_id_prefix}_ComponentGridPanel);

Zenoss.ZPL_{zenpack_id_prefix}_RenderableDisplayField = Ext.extend(Zenoss.DisplayField, {
    constructor: function(config) {
        if (typeof(config.renderer) == 'string') {
          config.renderer = eval(config.renderer);
        }
        Zenoss.ZPL_{zenpack_id_prefix}_RenderableDisplayField.superclass.constructor.call(this, config);
    },
    valueToRaw: function(value) {
        if (typeof(value) == 'boolean' || typeof(value) == 'object') {
            return value;
        } else {
            return Zenoss.ZPL_{zenpack_id_prefix}_RenderableDisplayField.superclass.valueToRaw(value);
        }
    }
});

Ext.reg('ZPL_{zenpack_id_prefix}_RenderableDisplayField', 'Zenoss.ZPL_{zenpack_id_prefix}_RenderableDisplayField');

""".strip()


USAGE = """
Usage: {} <command> [options]

Available commands and example options:

  # Create a new ZenPack source directory.
  create ZenPacks.example.MyNewPack

  # Check zenpack.yaml for errors.
  lint zenpack.yaml

  # Print yUML (http://yuml.me/) class diagram source based on zenpack.yaml.
  class_diagram yuml zenpack.yaml

  # Export existing monitoring templates to yaml.
  dump_templates ZenPacks.example.AlreadyInstalled

  # Convert a pre-release zenpacklib.ZenPackSpec to yaml.
  py_to_yaml ZenPacks.example.AlreadyInstalled

  # Print all possible facet paths for a given device, and whether they
  # are currently filtered.
  list_paths [device name]

  # Print zenpacklib version.
  version
""".lstrip()


SETUP_PY = """
################################
# These variables are overwritten by Zenoss when the ZenPack is exported
# or saved.  Do not modify them directly here.
# NB: PACKAGES is deprecated
NAME = "{zenpack_name}"
VERSION = "1.0.0dev"
AUTHOR = "Your Name Here"
LICENSE = ""
NAMESPACE_PACKAGES = {namespace_packages}
PACKAGES = {packages}
INSTALL_REQUIRES = []
COMPAT_ZENOSS_VERS = ""
PREV_ZENPACK_NAME = ""
# STOP_REPLACEMENTS
################################
# Zenoss will not overwrite any changes you make below here.

from setuptools import setup, find_packages


setup(
    # This ZenPack metadata should usually be edited with the Zenoss
    # ZenPack edit page.  Whenever the edit page is submitted it will
    # overwrite the values below (the ones it knows about) with new values.
    name=NAME,
    version=VERSION,
    author=AUTHOR,
    license=LICENSE,

    # This is the version spec which indicates what versions of Zenoss
    # this ZenPack is compatible with
    compatZenossVers=COMPAT_ZENOSS_VERS,

    # previousZenPackName is a facility for telling Zenoss that the name
    # of this ZenPack has changed.  If no ZenPack with the current name is
    # installed then a zenpack of this name if installed will be upgraded.
    prevZenPackName=PREV_ZENPACK_NAME,

    # Indicate to setuptools which namespace packages the zenpack
    # participates in
    namespace_packages=NAMESPACE_PACKAGES,

    # Tell setuptools what packages this zenpack provides.
    packages=find_packages(),

    # Tell setuptools to figure out for itself which files to include
    # in the binary egg when it is built.
    include_package_data=True,

    # Indicate dependencies on other python modules or ZenPacks.  This line
    # is modified by zenoss when the ZenPack edit page is submitted.  Zenoss
    # tries to put add/delete the names it manages at the beginning of this
    # list, so any manual additions should be added to the end.  Things will
    # go poorly if this line is broken into multiple lines or modified to
    # dramatically.
    install_requires=INSTALL_REQUIRES,

    # Every ZenPack egg must define exactly one zenoss.zenpacks entry point
    # of this form.
    entry_points={{
        'zenoss.zenpacks': '%s = %s' % (NAME, NAME),
    }},

    # All ZenPack eggs must be installed in unzipped form.
    zip_safe=False,
)
""".lstrip()


if __name__ == '__main__':
    from Products.ZenUtils.ZenScriptBase import ZenScriptBase

    class ZPLCommand(ZenScriptBase):
        def run(self):
            args = sys.argv[1:]

            if len(args) == 2 and args[0] == 'lint':
                filename = args[1]

                with open(filename, 'r') as file:
                    linecount = len(file.readlines())

                # Change our logging output format.
                logging.getLogger().handlers = []
                for logger in logging.Logger.manager.loggerDict.values():
                    logger.handlers = []
                handler = logging.StreamHandler(sys.stdout)
                formatter = logging.Formatter(
                    fmt='%s:%s:0: %%(message)s' % (filename, linecount))
                handler.setFormatter(formatter)
                logging.getLogger().addHandler(handler)

                try:
                    with open(filename, 'r') as stream:
                        yaml.load(stream, Loader=WarningLoader)
                except Exception, e:
                    LOG.exception(e)

            elif len(args) == 2 and args[0] == 'py_to_yaml':
                zenpack_name = args[1]

                self.connect()
                zenpack = self.dmd.ZenPackManager.packs._getOb(zenpack_name)
                if zenpack is None:
                    LOG.error("ZenPack '%s' not found." % zenpack_name)
                    return
                zenpack_init_py = os.path.join(os.path.dirname(inspect.getfile(zenpack.__class__)), '__init__.py')

                # create a dummy zenpacklib sufficient to be used in an
                # __init__.py, so we can capture export the data.
                zenpacklib_module = create_module("zenpacklib")
                zenpacklib_module.ZenPackSpec = type('ZenPackSpec', (dict,), {})
                zenpack_schema_module = create_module("schema")
                zenpack_schema_module.ZenPack = ZenPackBase

                def zpl_create(self):
                    zenpacklib_module.CFG = dict(self)
                zenpacklib_module.ZenPackSpec.create = zpl_create

                stream = open(zenpack_init_py, 'r')
                inputfile = stream.read()

                # tweak the input slightly.
                inputfile = re.sub(r'from .* import zenpacklib', '', inputfile)
                inputfile = re.sub(r'from .* import schema', '', inputfile)
                inputfile = re.sub(r'__file__', '"%s"' % zenpack_init_py, inputfile)

                # Kludge 'from . import' into working.
                import site
                site.addsitedir(os.path.dirname(zenpack_init_py))
                inputfile = re.sub(r'from . import', 'import', inputfile)

                g = dict(zenpacklib=zenpacklib_module, schema=zenpack_schema_module)
                l = dict()
                exec inputfile in g, l

                CFG = zenpacklib_module.CFG
                CFG['name'] = zenpack_name

                # convert the cfg dictionary to yaml
                specparams = ZenPackSpecParams(**CFG)

                # Dig around in ZODB and add any defined monitoring templates
                # to the spec.
                templates = self.zenpack_templatespecs(zenpack_name)
                for dc_name in templates:
                    if dc_name not in specparams.device_classes:
                        LOG.warning("Device class '%s' was not defined in %s - adding to the YAML file.  You may need to adjust the 'create' and 'remove' options.",
                                    dc_name, zenpack_init_py)
                        specparams.device_classes[dc_name] = DeviceClassSpecParams(specparams, dc_name)

                    # And merge in the templates we found in ZODB.
                    specparams.device_classes[dc_name].templates.update(templates[dc_name])

                outputfile = yaml.dump(specparams, Dumper=Dumper)

                # tweak the yaml slightly.
                outputfile = outputfile.replace("__builtin__.object", "object")
                outputfile = re.sub(r"!!float '(\d+)'", r"\1", outputfile)

                print outputfile

            elif len(args) == 2 and args[0] == 'dump_templates':
                zenpack_name = args[1]
                self.connect()

                templates = self.zenpack_templatespecs(zenpack_name)
                if templates:
                    zpsp = ZenPackSpecParams(
                        zenpack_name,
                        device_classes={x: {} for x in templates})

                    for dc_name in templates:
                        zpsp.device_classes[dc_name].templates = templates[dc_name]

                    print yaml.dump(zpsp, Dumper=Dumper)

            elif len(args) == 3 and args[0] == "class_diagram":
                diagram_type = args[1]
                filename = args[2]

                with open(filename, 'r') as stream:
                    CFG = yaml.load(stream, Loader=Loader)

                if diagram_type == 'yuml':
                    print "# Classes"
                    for cname in sorted(CFG.classes):
                        print "[{}]".format(cname)

                    print "\n# Inheritence"
                    for cname in CFG.classes:
                        cspec = CFG.classes[cname]
                        for baseclass in cspec.bases:
                            if type(baseclass) != str:
                                baseclass = aq_base(baseclass).__name__
                            print "[{}]^-[{}]".format(baseclass, cspec.name)

                    print "\n# Containing Relationships"
                    for crspec in CFG.class_relationships:
                        if crspec.cardinality == '1:MC':
                            print "[{}]++{}-{}[{}]".format(
                                crspec.left_class, crspec.left_relname,
                                crspec.right_relname, crspec.right_class)

                    print "\n# Non-Containing Relationships"
                    for crspec in CFG.class_relationships:
                        if crspec.cardinality == '1:1':
                            print "[{}]{}-.-{}[{}]".format(
                                crspec.left_class, crspec.left_relname,
                                crspec.right_relname, crspec.right_class)
                        if crspec.cardinality == '1:M':
                            print "[{}]{}-.-{}++[{}]".format(
                                crspec.left_class, crspec.left_relname,
                                crspec.right_relname, crspec.right_class)
                        if crspec.cardinality == 'M:M':
                            print "[{}]++{}-.-{}++[{}]".format(
                                crspec.left_class, crspec.left_relname,
                                crspec.right_relname, crspec.right_class)
                else:
                    LOG.error("Diagram type '%s' is not supported.", diagram_type)

            elif len(args) == 2 and args[0] == "list_paths":
                self.connect()
                device = self.dmd.Devices.findDevice(args[1])
                if device is None:
                    LOG.error("Device '%s' not found." % args[1])
                    return

                from Acquisition import aq_chain
                from Products.ZenRelations.RelationshipBase import RelationshipBase

                all_paths = set()
                included_paths = set()
                class_summary = collections.defaultdict(set)

                for component in device.getDeviceComponents():
                    for facet in component.get_facets(recurse_all=True):
                        path = []
                        for obj in aq_chain(facet):
                            if obj == component:
                                break
                            if isinstance(obj, RelationshipBase):
                                path.insert(0, obj.id)
                        all_paths.add(component.meta_type + ":" + "/".join(path) + ":" + facet.meta_type)

                    for facet in component.get_facets():
                        path = []
                        for obj in aq_chain(facet):
                            if obj == component:
                                break
                            if isinstance(obj, RelationshipBase):
                                path.insert(0, obj.id)
                        included_paths.add(component.meta_type + ":" + "/".join(path) + ":" + facet.meta_type)
                        class_summary[component.meta_type].add(facet.meta_type)

                print "Paths\n-----\n"
                for path in sorted(all_paths):
                    if path in included_paths:
                        if "/" not in path:
                            # normally all direct relationships are included
                            print "DIRECT  " + path
                        else:
                            # sometimes extra paths are pulled in due to extra_paths
                            # configuration.
                            print "EXTRA   " + path
                    else:
                        print "EXCLUDE " + path

                print "\nClass Summary\n-------------\n"
                for source_class in sorted(class_summary.keys()):
                    print "%s is reachable from %s" % (source_class, ", ".join(sorted(class_summary[source_class])))

            elif len(args) == 2 and args[0] == "create":
                create_zenpack_srcdir(args[1])

            elif len(args) == 1 and args[0] == "version":
                print __version__

            else:
                print USAGE.format(sys.argv[0])

        def zenpack_templatespecs(self, zenpack_name):
            """Return dictionary of RRDTemplateSpecParams by device_class.

            Example return value:

                {
                    '/Server/Linux': {
                        'Device': RRDTemplateSpecParams(...),
                    },
                    '/Server/SSH/Linux': {
                        'Device': RRDTemplateSpecParams(...),
                        'IpInterface': RRDTemplateSpecParams(...),
                    },
                }

            """
            zenpack = self.dmd.ZenPackManager.packs._getOb(zenpack_name, None)
            if zenpack is None:
                LOG.error("ZenPack '%s' not found." % zenpack_name)
                return

            # Find explicitly associated templates, and templates implicitly
            # associated through an explicitly associated device class.
            from Products.ZenModel.DeviceClass import DeviceClass
            from Products.ZenModel.RRDTemplate import RRDTemplate

            templates = []
            for packable in zenpack.packables():
                if isinstance(packable, DeviceClass):
                    templates.extend(packable.getAllRRDTemplates())
                elif isinstance(packable, RRDTemplate):
                    templates.append(packable)

            # Only create specs for templates that have an associated device
            # class. This prevents locally-overridden templates from being
            # included.
            specs = collections.defaultdict(dict)
            for template in templates:
                deviceClass = template.deviceClass()
                if deviceClass:
                    dc_name = deviceClass.getOrganizerName()
                    spec = RRDTemplateSpecParams.fromObject(template)
                    specs[dc_name][template.id] = spec

            return specs

    script = ZPLCommand()
    script.run()
