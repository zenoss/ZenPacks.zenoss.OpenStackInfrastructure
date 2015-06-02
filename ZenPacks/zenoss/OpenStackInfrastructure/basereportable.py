#!/usr/bin/env python
##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""
basereportable - upgraded versions of the ZenETL basereportables which
provide a more appropriate default behavior for zenpacks.

These adapters automatically export all properties and relationships of any
model object they are applied to in a consistent manner.

Enabling basic analytics model export support for a ZenPack can be done entirely
through ZCML as follows:

Add the following to configure.zcml:

    <!-- Analytics -->
    <include file="reportable.zcml"
             xmlns:zcml="http://namespaces.zope.org/zcml"
             zcml:condition="installed ZenPacks.zenoss.ZenETL" />


The contents of reportable.zcml will depend on the structure of your ZenPack.

The goal is to bind the BaseReportable and BaseReportableFactory adapters to
every model class in your ZenPack, most particularly to those that inherit from
Device or DeviceComponent.

If you are using zenpacklib, all devices and devicecomponents inherit from
a common base class, so you can simply use the following:

    <?xml version="1.0" encoding="utf-8"?>
    <configure xmlns="http://namespaces.zope.org/zope"
               xmlns:browser="http://namespaces.zope.org/browser"
               >

      <!-- Define the reportable schema -->

      <adapter factory=".basereportable.BaseReportable"
               for=".zenpacklib.Device"
               provides="Products.Zuul.interfaces.IReportable"
               />

      <adapter factory=".basereportable.BaseReportableFactory"
               for=".zenpacklib.Device"
               provides="Products.Zuul.interfaces.IReportableFactory"
               />

      <adapter factory=".basereportable.BaseReportable"
               for=".zenpacklib.Component"
               provides="Products.Zuul.interfaces.IReportable"
               />

      <adapter factory=".basereportable.BaseReportableFactory"
               for=".zenpacklib.Component"
               provides="Products.Zuul.interfaces.IReportableFactory"
               />

    </configure>

All of the device/devicecomponent schema classes will inherit these adapters
automatically.

If you are not using zenpacklib, but you do have a similar base class that most
components inherit from, you may bind to that class instead.  If your ZenPack's
devicecomponents do not share a common base class within your zenpack, then
you will need to bind each one individually.  For example, in StorageBase,
we would have:

      <adapter factory=".basereportable.BaseReportable"
               for=".HardDisk.HardDisk"
               provides="Products.Zuul.interfaces.IReportable"
               />

      <adapter factory=".basereportable.BaseReportableFactory"
               for=".HardDisk.HardDisk"
               provides="Products.Zuul.interfaces.IReportableFactory"
               />

      <adapter factory=".basereportable.BaseReportable"
               for=".LUN.LUN"
               provides="Products.Zuul.interfaces.IReportable"
               />

      <adapter factory=".basereportable.BaseReportableFactory"
               for=".LUN.LUN"
               provides="Products.Zuul.interfaces.IReportableFactory"
               />

   (etc, for every class)


Generally, creating this ZCML file is all you will need to do in order to get
a reasonable implementation of Reportable adapters for your ZenPack.

To test the result, you may invoke this script directly:

    python basereportable.py <device name>

It will output all of the data that will be sent to analytics.  (Note that you
must install the ZenETL zenpack in order to even run this test!)

If this data looks reasonable, you're done.   If you find that some of the
reportables need tweaking, you may subclass the BaseReportable class provided
in this file and extend the reportProperties method.   If you are unhappy with
the naming of the entities or columns, you may modify the naming in 
entity_class_for_class, as follows:


    import basereportable
    from ZenPacks.zenoss.OpenStackInfrastructure.SoftwareComponent import SoftwareComponent


    class BaseReportable(basereportable.BaseReportable):

        @classmethod
        def entity_class_for_class(cls, object_class):
            entity_class = super(BaseReportable, cls).entity_class_for_class(object_class)
            return entity_class.replace("open_stack", "openstack")


Another customization you may wish to do is to output some of your components
in multiple analytics tables.  This is particularly important if you have
subclassed a component class that is provided outside of your ZenPack.

For example, if you subclass IpInterface and create MyIpInterface, by default,
your data will only go into the dim_my_ip_interface table, not into
dim_ip_interface.  This could cause your interfaces to not show up in analytics
reports that are meant to show "all" interfaces, for instance.

To correct this, subclass BaseReportable, and provide an export_as_bases
similar to that shown below.  The idea is to, based on context, return a list
of parent classes to "also" export as.   This may be a class within
your zenpack, or outside of it.

    @property
    def export_as_bases(self):
        bases = super(BaseReportable, self).export_as_bases

        # Anything that is a IPInterface subclass, also export
        # as a IPInterface.
        if isinstance(self.context, IPInterface):
            bases.append(IPInterface)

        # Anything that is a softwarecomponent subclass, also export
        # as a softwarecomponent.
        if isinstance(self.context, SoftwareComponent):
            bases.append(SoftwareComponent)

        return bases

Generally this is the extent of customization you are likely to require for
most ZenPacks.   However, these classes can be subclassed to add almost any
functionality, if you really need to.  It is our hope, however, to get to
the point where the default adapters will just "do the right thing" without
any need to subclass.

"""

import Globals

import logging
LOG = logging.getLogger('zenpack.reportable')

import sys
from zope.component import adapts, getGlobalSiteManager
from zope.interface import implements, implementedBy

from Products.Five import zcml
from Products.ZenModel.ZenModelRM import ZenModelRM
from Products.ZenModel.Device import Device
from Products.ZenRelations.RelSchema import ToOne, ToMany
from Products.ZenRelations.utils import importClass
from Products.ZenUtils.Utils import unused
from Products.ZenUtils.ZenScriptBase import ZenScriptBase
from Products.Zuul.decorators import memoize
from Products.Zuul.interfaces import IReportable, IReportableFactory, ICatalogTool

from ZenPacks.zenoss.ZenETL.utils import un_camel as zenetl_un_camel
from ZenPacks.zenoss.ZenETL.reportable import \
    MARKER_LENGTH, \
    DEFAULT_STRING_LENGTH, \
    BaseReportableFactory as ETLBaseReportableFactory, \
    BaseReportable as ETLBaseReportable, \
    Reportable

unused(Globals)


def un_camel(text):
    return zenetl_un_camel(text).replace(" ", "")


def refValue(rel):
    # Given a ToOne relationship, return a proper value for reportProperties()
    if rel():
        return IReportable(rel()).sid
    else:
        return None


@memoize
def adapter_for_class(class_, adapter_interface):
    gsm = getGlobalSiteManager()

    adapter = gsm.adapters.registered((implementedBy(class_),), adapter_interface)

    if adapter:
        return adapter

    # recurse up the inheritence tree to find an adapter, if we don't have one
    # registered for this class directly.
    for base_class in class_.__bases__:
        return adapter_for_class(base_class, adapter_interface)


class BaseReportableFactory(ETLBaseReportableFactory):
    implements(IReportableFactory)
    adapts(ZenModelRM)

    class_context = None

    def set_class_context(self, class_):
        self.class_context = class_

    def exports(self):
        context_reportable = IReportable(self.context)
        if self.class_context and hasattr(context_reportable, 'set_class_context'):
            context_reportable.set_class_context(self.class_context)

        yield context_reportable

        if hasattr(context_reportable, 'export_as_bases'):
            # The idea here is to give the abiliity to export something both as
            # itself, but also as a more generic type (one of its base classes).
            # For example, an OpenStack Endpoint is both an openstack endpoint
            # and a Device.  Therefore I would like it to end up in both
            # dim_openstack_endpoint and dim_device.

            for class_ in context_reportable.export_as_bases:
                if class_ == self.class_context:
                    # no need to re-export as ourself..
                    continue

                reportable_factory_class = adapter_for_class(class_, IReportableFactory)
                reportable_class = adapter_for_class(class_, IReportable)

                # The problem is that normally, a Reportable or ReportableFactory
                # does not know what class it is adapting.  It therefore tends
                # to rely on the model object to tell it what to export, and
                # most of the reportables export all properties and relationships
                # of the supplied object.
                #
                # In this situation, though, we want to export, say, an Endpoint
                # as if it was a Device, and therefore to only export the
                # properties and relationships defined in the Device class.
                #
                # The only way to make this work is to introduce the idea of
                # class-context to Reportable (and ReportableFactory).
                #
                # A class-context-aware Reportable or ReportableFactory has
                # an additional method, set_class_context(), which is passed
                # a class object.
                #
                # The default behavior is still the same- if set_class_context
                # has not been used, the reportable should behave as it does
                # today.
                #
                # However, in this specific situation (export_as_bases), if a
                # class-context-aware ReportableFactory is available, I will
                # use it (and expect it to pass that class context on to the
                # reportables it generates).
                #
                # Otherwise, I will create the single reportable directly, not
                # using any reportablefactory, because I can't trust the
                # an existing factory that doesn't realize that it's dealing
                # with a base class, not the actual object class, to not
                # duplicate all the exports I have already done.
                factory = reportable_factory_class(self.context)

                if hasattr(reportable_factory_class, 'set_class_context'):
                    factory.set_class_context(class_)
                    for export in factory.exports():
                        yield export
                else:
                    yield reportable_class(self.context)

        relations = getattr(self.context, '_relations', tuple())
        for relName, relation in relations:
            if isinstance(relation, ToMany) and \
               issubclass(relation.remoteType, ToMany):

                # For a many-many relationship, we need to implement a
                # reportable to represent the relationship, if we're
                # on the proper end of it.  Really, either end will work,
                # but we need something deterministic, so just go with
                # whichever end has the alphabetically earliest relname.
                if min(relation.remoteName, relName) == relName:
                    related = getattr(self.context, relName, None)
                    if related:
                        related = related()

                    entity_class_name = "%s_to_%s" % (
                        IReportable(self.context).entity_class_name,
                        un_camel(importClass(
                            relation.remoteClass, None).meta_type).replace(
                            "open_stack_infrastructure", "osi")
                    )

                    for remoteObject in related:
                        yield BaseManyToManyReportable(
                            fromObject=self.context, toObject=remoteObject,
                            entity_class_name=entity_class_name)


class BaseReportable(ETLBaseReportable):
    class_context = None

    def __init__(self, context):
        super(BaseReportable, self).__init__(context)
        self.class_context = self.context.__class__
        self.rel_property_name = dict()
        seen_target_entity = set()

        relations = getattr(self.context, '_relations', tuple())
        for relName, relation in relations:
            try:
                if type(relation.remoteClass) == str:
                    remoteClass = importClass(relation.remoteClass, None)
                else:
                    remoteClass = relation.remoteClass()

                if remoteClass.meta_type in ('ZenModelRM'):
                    # Way too generic.  Just go with the relname.
                    target_entity = un_camel(relName)
                else:
                    target_entity = self.entity_class_for_class(remoteClass)

                    if target_entity in seen_target_entity:
                        # if we have more than one relationship to the same
                        # target entity, prefix all but the first
                        # with the relname to disambiguate.
                        target_entity = un_camel(relName + '_' + target_entity)

                seen_target_entity.add(target_entity)
                self.rel_property_name[relName] = target_entity
            except Exception, e:
                LOG.error("Error processing relationship %s on %s: %s") % (relName, self.context, e)

    @property
    def entity_class_name(self):
        return self.__class__.entity_class_for_class(self.class_context)

    @classmethod
    def entity_class_for_class(cls, object_class):
        # Unfortunately, since entity_class_name is not a classmethod, we can
        # not determine the entity_class_name for the target of a relationship
        # if we only know its type, not an actual object.   So it's necessary
        # to define this method.  It should always return the same value
        # as entity_class_name would.   If you have relationships that point
        # to an object managed by a different reportable, which perhaps does
        # not use entity class names derived from meta_types in the normal way,
        # of if you have subclassed entity_class_name, you will need to also
        # subclass this function and ensure that it matches.
        return un_camel(object_class.meta_type)

    def set_class_context(self, class_):
        self.class_context = class_

    @property
    def export_as_bases(self):
        """
        In addition to exporting as dim_{entity_class_name}, also export
        to the dimension table for the specified classes.

        If the reportable for the specified class is not class-context-aware,
        This may cause columns from the subclass to be leaked to the base class's
        dimension table, so some care should be taken in using this.
        """
        bases = []

        if isinstance(self.context, Device):
            # If we're reporting any subclass of device, also export it to
            # dim_device.
            bases.append(Device)

        return bases

    def reportProperties(self):

        # additional properties not provided by the ZenETL BaseReportable
        eclass = self.entity_class_name

        # Persistent object reference
        yield (eclass + '_id', 'string', self.context.id, DEFAULT_STRING_LENGTH)

        # Human-friendly name that can change
        yield (eclass + '_name', 'string', self.context.titleOrId(), DEFAULT_STRING_LENGTH)

        # Type
        yield (eclass + '_type', 'string', self.context.meta_type, DEFAULT_STRING_LENGTH)

        # UID
        yield (eclass + '_uid', 'string', self.uid, DEFAULT_STRING_LENGTH)

        # If we're also exporting as a base class, add a reference to that table.
        # (with the same SID as ourselves, of course)
        for base_class in self.export_as_bases:
            base_eclass = self.entity_class_for_class(base_class)
            yield (base_eclass + "_key", 'reference', self.sid, MARKER_LENGTH)

        for entry in super(BaseReportable, self).reportProperties():
            yield entry

    def _getProperty(self, propspec):
        prop = super(BaseReportable, self)._getProperty(propspec)
        if prop is None:
            return None

        # The default version of this returns the property name directly.
        # instead, we use morefully qualified version, and converted to
        # lowercase (with underscores)
        prop_id = prop[0]
        if prop_id.startswith(propspec['id']):
            new_prop_id = un_camel(self.entity_class_name + '_' + propspec['id'])
            # preserve any suffixes that might have been appended.
            prop_id = new_prop_id + prop_id[len(propspec['id']):]

        return (prop_id, prop[1], prop[2], prop[3])

    def _getRelationProps(self):
        # The default version of this does not support ToMany relationships.

        # Note that the default implementation of reportProperties already
        # handles the device_key property itself, so we don't worry about that.
        relations = getattr(self.context, '_relations', tuple())
        for relName, relation in relations:
            propname = self.rel_property_name[relName]

            if isinstance(relation, ToOne):
                related = getattr(self.context, relName, None)
                yield (propname + '_key', 'reference', refValue(related), MARKER_LENGTH)
            else:
                related = getattr(self.context, relName, None)
                try:
                    yield (propname + '_count', 'int', related.countObjects(), MARKER_LENGTH)
                except Exception:
                    # broken relationship, or something.  Just return 0.
                    yield (propname + '_count', 'int', 0, MARKER_LENGTH)


class BaseManyToManyReportable(Reportable):
    implements(IReportable)

    def __init__(self, fromObject=None, toObject=None,
                 entity_class_name=None):
        super(BaseManyToManyReportable, self).__init__()
        self.fromObject = fromObject
        self.toObject = toObject
        self.entity_class_name = entity_class_name

    @property
    def id(self):
        return "%s__%s" % (self.fromObject.id, self.toObject.id)

    @property
    def uid(self):
        return "%s__%s" % (self.fromObject.uid, self.toObject.uid)

    @property
    def sid(self):
        return "%s__%s" % (IReportable(self.fromObject).sid, IReportable(self.toObject).sid)

    def reportProperties(self):
        fromReportable = IReportable(self.fromObject)
        toReportable = IReportable(self.toObject)

        return [
            (fromReportable.entity_class_name + "_key", 'reference', fromReportable.sid, MARKER_LENGTH),
            (toReportable.entity_class_name + "_key",   'reference', toReportable.sid, MARKER_LENGTH),
        ]


# Allows for command-line invocation to dump out all the reported data
# for testing purposes.
#
# Usage: reportable.py <device name>
#
class DumpReportables(ZenScriptBase):
    def run(self):
        if len(sys.argv) < 2:
            raise ValueError("Usage: reportable.py <device name>")

        device_name = sys.argv[1]

        import ZenPacks.zenoss.ZenETL
        zcml.load_config('configure.zcml', ZenPacks.zenoss.ZenETL)

        import ZenPacks.zenoss.vSphere
        zcml.load_config('configure.zcml', ZenPacks.zenoss.vSphere)

        self.connect()

        device = self.dmd.Devices.findDevice(device_name)
        if not device:
            raise ValueError("Device not found")

        for brain in ICatalogTool(device).search():
            component = brain.getObject()
            factory = IReportableFactory(component)

            for reportable in factory.exports():
                if reportable.id in ('os', 'hw'):
                    # not my problem.
                    continue

                print "      adapter=%s.%s -> %s.%s" % (
                    factory.__class__.__module__,
                    factory.__class__.__name__,
                    reportable.__class__.__module__,
                    reportable.__class__.__name__,
                )
                print "      reportable.entity_class_name=%s" % reportable.entity_class_name
                print "      reportable.id=%s, sid=%s" % (reportable.id, reportable.sid)

                props = reportable.reportProperties()

                for name, type_, value, length in props:
                    if name in ('snmpindex', 'monitor', 'productionState', 'preMWProductionState'):
                        # boring, so let's omit them.
                        continue

                    if length == -1:
                        print "         %s [%s] = %s" % (name, type_, value)
                    else:
                        print "         %s [%s.%s] = %s" % (name, type_, length, value)

                print ""


def main():
    script = DumpReportables()
    script.run()

if __name__ == '__main__':
    main()
