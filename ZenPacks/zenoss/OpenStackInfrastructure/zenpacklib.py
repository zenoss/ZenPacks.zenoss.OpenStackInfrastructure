##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013-2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""zenpacklib - ZenPack API abstraction.

This module provides a single integration point for common ZenPacks.

"""

import logging
LOG = logging.getLogger('zen.zenpacklib')

# Suppresses "No handlers could be found for logger" errors if logging
# hasn't been configured.
LOG.addHandler(logging.NullHandler())

import collections
import imp
import importlib
import json
import operator
import os
import re
import sys
import math

from zope.browser.interfaces import IBrowserView
from zope.component import adapts, getGlobalSiteManager
from zope.event import notify
from zope.interface import classImplements, implements
from zope.interface.interface import InterfaceClass

from Products.AdvancedQuery import Eq, Or
from Products.AdvancedQuery.AdvancedQuery import _BaseQuery as BaseQuery
from Products.Five import zcml

from Products.ZenModel.Device import Device as BaseDevice
from Products.ZenModel.DeviceComponent import DeviceComponent as BaseDeviceComponent
from Products.ZenModel.HWComponent import HWComponent as BaseHWComponent
from Products.ZenModel.ManagedEntity import ManagedEntity as BaseManagedEntity
from Products.ZenModel.ZenossSecurity import ZEN_CHANGE_DEVICE
from Products.ZenModel.ZenPack import ZenPack as ZenPackBase
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

    # NEW_COMPONENT_TYPES AND NEW_RELATIONS will be monkeypatched in
    # via zenpacklib when this class is instantiated.

    def _buildDeviceRelations(self):
        for d in self.dmd.Devices.getSubDevicesGen():
            d.buildRelations()

    def install(self, app):
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

    def remove(self, app, leaveObjects=False):
        from Products.Zuul.interfaces import ICatalogTool
        if not leaveObjects:
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
                    LOG.info('Removing DeviceClass %s' % dcspec.path)
                    app.dmd.Devices.manage_deleteOrganizer(dcspec.path)

        super(ZenPack, self).remove(app, leaveObjects=leaveObjects)


class ModelBase(object):

    """Base class for ZenPack model classes."""

    def getIconPath(self):
        """Return relative URL path for class' icon."""
        return getattr(self, 'icon_url', '/zport/dmd/img/icons/noicon.png')


class DeviceBase(ModelBase):

    """First superclass for zenpacklib types created by DeviceTypeFactory.

    Contains attributes that should be standard on all ZenPack Device
    types.

    """

    def search(self, name, *args, **kwargs):
        return catalog_search(self, name, *args, **kwargs)


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

    def get_catalog_name(self, name, scope):
        if scope == 'device':
            return '{}Search'.format(name)
        else:
            name = self.__module__.replace('.', '_')
            return '{}Search'.format(name)

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
                return getattr(self.dmd.Device, self.get_catalog_name(name, scope))
            except AttributeError:
                if create:
                    return self._create_catalog(name, 'global')
        return

    def get_catalog_scopes(self, name):
        """Return catalog scopes by name."""
        spec = self._get_catalog_spec(name)
        if not spec:
            []

        scopes = [spec['indexes'][x].get('scope', 'device') for x in spec['indexes']]
        if 'both' in scopes:
            scopes = [x for x in scopes if x != 'both']
            scopes.append('device')
            scopes.append('global')
        return set(scopes)

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

    def _get_catalog_spec(self, name):
        if not hasattr(self, '_catalogs'):
            LOG.error("%s has no catalogs defined", self.id)
            return

        spec = self._catalogs.get(name)
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

    def _create_catalog(self, name, scope='device'):
        """Create and return catalog defined by name."""
        from Products.ZCatalog.Catalog import CatalogError
        from Products.ZCatalog.ZCatalog import manage_addZCatalog

        from Products.Zuul.interfaces import ICatalogTool

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
                if scope == 'device':
                    results = ICatalogTool(device).search(types=(classname,))
                else:
                    results = ICatalogTool(deviceClass).search(types=(classname,))

                for result in results:
                    if hasattr(result.getObject(), 'index_object'):
                        result.getObject().index_object()

        return zcatalog

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
        for result in self.device().search('ComponentBase', id=id_):
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
        for result in self.device().search('ComponentBase', query):
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

    def get_facets(self, seen=None):
        """Generate non-containing related objects for faceting."""
        if seen is None:
            seen = set()

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

            for obj in relobjs:
                if obj in seen:
                    continue

                yield obj
                seen.add(obj)
                for facet in obj.get_facets(seen=seen):
                    yield facet

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
                    item['xtype'] = 'ZPLRenderableDisplayField'
                    item['renderer'] = renderer


def DeviceTypeFactory(name, bases):
    """Return a "ZenPackified" device class given bases tuple."""
    all_bases = (DeviceBase,) + bases

    return type(name, all_bases, {})


Device = DeviceTypeFactory(
    'Device', (BaseDevice,))


def ComponentTypeFactory(name, bases):
    """Return a "ZenPackified" component class given bases tuple."""
    all_bases = (ComponentBase,) + bases

    def index_object(self, idxs=None):
        for base in all_bases:
            if hasattr(base, 'index_object'):
                try:
                    base.index_object(self, idxs=idxs)
                except TypeError:
                    base.index_object(self)

    def unindex_object(self):
        for base in all_bases:
            if hasattr(base, 'unindex_object'):
                base.unindex_object(self)

    attributes = {
        'index_object': index_object,
        'unindex_object': unindex_object,
        }

    return type(name, all_bases, attributes)


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

    def specs_from_param(self, spec_type, param_name, param_dict):
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
            apply_defaults(param_dict)

        return {
            k: spec_type(self, k, **(fix_kwargs(v)))
            for k, v in param_dict.iteritems()}


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
            device_classes=None):
        """TODO."""
        self.name = name
        self.NEW_COMPONENT_TYPES = []
        self.NEW_RELATIONS = collections.defaultdict(list)

        # zProperties
        self.zProperties = self.specs_from_param(
            ZPropertySpec, 'zProperties', zProperties)

        # Classes
        if classes:
            for classname, classdata in classes.items():
                if 'relationships' not in classdata:
                    classdata['relationships'] = {}

                # Merge class_relationships.
                if class_relationships:
                    update(
                        classdata['relationships'],
                        class_relationships.get(classname, {}))

        self.classes = self.specs_from_param(ClassSpec, 'classes', classes)
        self.imported_classes = {}

        for classname, classdata in classes.iteritems():
            relationships = classdata['relationships']
            for relationship in relationships:
                try:
                    if 'schema' in relationships[relationship]:
                        className = relationships[relationship]['schema'].remoteClass
                        if '.' in className and className.split('.')[-1] not in self.classes:
                            module = ".".join(className.split('.')[0:-1])
                            kls = importClass(module)
                            self.imported_classes[className] = kls
                    else:
                        LOG.error('%s: relationship %s has no schema' % (self.name, relationship))
                except ImportError:
                    pass

        for class_ in self.classes.values():
            for relationship in class_.relationships.values():
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

        snippet = (
            "(function(){{\n"
            "var ZC = Ext.ns('Zenoss.component');\n"
            "{link_code}\n"
            "{snippets}"
            "}})();\n"
            .format(
                link_code=JS_LINK_FROM_GRID,
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

    def __init__(self, zenpack_spec, path, create=True, zProperties=None,
                 remove=False):
        self.zenpack_spec = zenpack_spec
        self.path = path.lstrip('/')
        self.create = bool(create)
        self.remove = bool(remove)

        if zProperties is None:
            self.zProperties = {}
        else:
            self.zProperties = zProperties


class ZPropertySpec(Spec):

    """TODO."""

    def __init__(
            self,
            zenpack_spec,
            name,
            type_='string',
            default=None,
            category=None,
            ):
        """TODO."""
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

    """TODO."""

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
            dynamicview_views=None,
            dynamicview_group=None,
            dynamicview_relations=None            
            ):
        """TODO."""
        self.zenpack = zenpack
        self.name = name

        # Verify that bases is a tuple of base types.
        if isinstance(base, (tuple, list, set)):
            bases = tuple(base)
        else:
            bases = (base,)

        self.bases = bases

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

    def inherited_properties(self):
        properties = {}
        for base in self.bases:
            if not isinstance(base, type):
                class_spec = self.zenpack.classes[base]
                properties.update(class_spec.properties)

        properties.update(self.properties)

        return properties

    def inherited_relationships(self):
        relationships = {}
        for base in self.bases:
            if not isinstance(base, type):
                class_spec = self.zenpack.classes[base]
                relationships.update(class_spec.relationships)

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
            if hasattr(base, '_relations'):
                relations.extend(base._relations)
            if hasattr(base, '_templates'):
                templates.extend(base._templates)
            if hasattr(base, '_catalogs'):
                catalogs.update(base._catalogs)

        # Add local properties and catalog indexes.
        for name, spec in self.properties.iteritems():
            if not spec.datapoint:
                attributes[name] = spec.default  # defaults to None
            else:
                # Lookup the datapoint and get the value from rrd
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
        attributes['_relations'] = tuple(relations)
        attributes['_templates'] = tuple(templates)
        attributes['_catalogs'] = catalogs

        # Add Impact stuff.
        attributes['impacts'] = self.impacts
        attributes['impacted_by'] = self.impacted_by
        attributes['dynamicview_relations'] = self.dynamicview_relations

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
            for rel,spec in self.relationships.items():
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
        return list(containing | faceting)

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
            renderer = 'Zenoss.render.zenpacklib_entityLinkFromGrid'

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
            "renderer: Zenoss.render.zenpacklib_entityLinkFromGrid"
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

        if width > 1000:
            LOG.warning(
                "%s: %s custom columns exceed 750 pixels (%s)",
                self.zenpack.name, self.name, width)

        return (
            "Ext.define('Zenoss.component.{meta_type}Panel', {{\n"
            "    alias: ['widget.{meta_type}Panel'],\n"
            "    extend: 'Zenoss.component.ZPLComponentGridPanel',\n"
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
            .format(
                meta_type=self.meta_type,
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
            index_scope='device'
            ):
        """TODO."""
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
            self.renderer = 'Zenoss.render.zenpacklib_entityLinkFromGrid'

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

        return [
            OrderAndValue(
                order=self.order,
                value='{{{}}}'.format(','.join(column_fields))),
            ]


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
            ):
        """TODO."""
        self.class_ = class_
        self.name = name

        # Schema
        if not schema:
            LOG.error(
                "no schema specified for %s relationship on %s",
                class_.name, name)

            return

        # Qualify unqualified classnames.
        if '.' not in schema.remoteClass:
            schema.remoteClass = '{}.{}'.format(
                self.class_.zenpack.name, schema.remoteClass)

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
            self.renderer = 'Zenoss.render.zenpacklib_entityTypeLinkFromGrid' \
                if self.render_with_type else 'Zenoss.render.zenpacklib_entityLinkFromGrid'

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

        if not isinstance(self.schema, (ToOne)):
            relname_count = '{}_count'.format(self.name)
            properties[relname_count] = RelationshipLengthProperty(self.name)

        properties[self.name] = RelationshipInfoProperty(self.name)

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


# Public Functions ##########################################################

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

            zenpack_module_name = '.'.join(self.__module__.split('.')[:-2])
            zenpack_module = importlib.import_module(zenpack_module_name)

            zenpackspec = getattr(zenpack_module, 'CFG', None)
            if not zenpackspec:
                raise NameError(
                    "name {!r} is not defined"
                    .format('.'.join((zenpack_module_name, 'CFG'))))

            zenpackspec.test_setup()

            import Products.ZenEvents
            zcml.load_config('meta.zcml', Products.ZenEvents)

            try:
                import ZenPacks.zenoss.DynamicView
                zcml.load_config('configure.zcml', ZenPacks.zenoss.DynamicView)
            except ImportError:
                return

            try:
                import ZenPacks.zenoss.Impact
                zcml.load_config('meta.zcml', ZenPacks.zenoss.Impact)
                zcml.load_config('configure.zcml', ZenPacks.zenoss.Impact)
            except ImportError:
                return

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
    classes = collections.defaultdict(dict)
    match_comment = re.compile(r'^\s*//').search

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
        if match_comment(line):
            continue

        match = match_line(line)
        if not match:
            LOG.error("parse error in relationships_from_yuml at %s" % line)
            continue

        left_class = match.group('left_classname')
        right_class = match.group('right_classname')
        left_relname = match.group('left_relname')
        left_cardinality = match.group('left_cardinality')
        right_relname = match.group('right_relname')
        right_cardinality = match.group('right_cardinality')

        if '++' in left_cardinality:
            left_type = ToManyCont
        elif '*' in right_cardinality:
            left_type = ToMany
        else:
            left_type = ToOne

        if '++' in right_cardinality:
            right_type = ToManyCont
        elif '*' in left_cardinality:
            right_type = ToMany
        else:
            right_type = ToOne

        if not left_relname:
            left_relname = relname_from_classname(
                right_class, plural=left_type != ToOne)

        if not right_relname:
            right_relname = relname_from_classname(
                left_class, plural=right_type != ToOne)

        classes[left_class][left_relname] = {
            'schema': left_type(right_type, right_class, right_relname),
            }

        classes[right_class][right_relname] = {
            'schema': right_type(left_type, left_class, left_relname),
            }

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
            return Zuul.info(getattr(self._object, method_name))
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
    return os.path.dirname(zenpack_module.__file__)


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


def apply_defaults(dictionary, default_defaults=None):
    """Modify dictionary to put values from DEFAULTS key into other keys.

    DEFAULTS key will no longer exist in dictionary. dictionary must be
    a dictionary of dictionaries.

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

            for tag in (TAG_ALL, type):
                relations = getattr(self._adapted, 'dynamicview_relations', {})
                for methodname in relations.get(tag, []):
                    for remote in self.get_remote_relatables(methodname):
                        yield BaseRelation(target, remote, type)

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


# Templates #################################################################

JS_LINK_FROM_GRID = """
Ext.apply(Zenoss.render, {
    zenpacklib_entityLinkFromGrid: function(obj, metaData, record, rowIndex, colIndex) {
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
            return '<a href="javascript:Ext.getCmp(\\'component_card\\').componentgrid.jumpToEntity(\\''+obj.uid+'\\', \\''+obj.meta_type+'\\');">'+obj.title+'</a>';
        } else {
            return obj.title;
        }
    },

    zenpacklib_entityTypeLinkFromGrid: function(obj, metaData, record, rowIndex, colIndex) {
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

Ext.define("Zenoss.component.ZPLComponentGridPanel", {
    alias: ["widget.ZPLComponentGridPanel"],
    extend: "Zenoss.component.ComponentGridPanel",

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

Ext.define("Zenoss.ZPLRenderableDisplayField", {
    extend: "Ext.form.DisplayField",
    alias: ['widget.ZPLRenderableDisplayField'],
    constructor: function(config) {
        if (typeof(config.renderer) == 'string') {
          config.renderer = eval(config.renderer)
        }
        Zenoss.ZPLRenderableDisplayField.superclass.constructor.call(this, config);
    }
});

""".strip()
