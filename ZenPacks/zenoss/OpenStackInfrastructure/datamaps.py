##############################################################################
#
# Copyright (C) Zenoss, Inc. 2019, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from time import time

from Products.DataCollector.plugins.DataMaps import ObjectMap


class ConsolidatingObjectMapQueue(object):
    """
    Provide a black box which you can insert object maps into, and then
    drain object maps out of.  The maps will be held for a period of time
    before they are released, and incremental changes aggregated into a smaller
    set of effective changes, when possible, according to the following rules:

    * If a component is created by a map (_add=True), hold all updates
      to this component for a period of time (shortlived_seconds).  If a
      map comes in during that time to delete that same component, discard
      all maps for it and don't waste zenhub's time.

    * If a component is deleted (.remove=True), discard any other pending
      object maps for this component, and release the remove datamap immediately.
      In addition, store the component ID in a blacklist for
      (delete_blacklist_seconds) seconds.

    * If any objmap comes in for a blacklisted component, drop it.

    * For all other updates, build an aggregate datamap, overlaying each
      new datamap's changes onto it, until its age reaches
      update_consolidate_seconds, then release it for consumption.
    """

    def __init__(self, shortlived_seconds=40, delete_blacklist_seconds=600, update_consolidate_seconds=40):
        self.shortlived_seconds = shortlived_seconds
        self.delete_blacklist_seconds = delete_blacklist_seconds
        self.update_consolidate_seconds = update_consolidate_seconds
        self.held_objmaps = {}
        self.blacklisted_components = {}

    def reset(self):
        self.held_objmaps = {}
        self.blacklisted_components = {}

    def now(self):
        return time()

    def append(self, objmap):
        # for convenience, ignore None objmaps if passed in.  (mapping functions
        # can return None if there's no data to apply, and it's easier to just
        # check for that here)
        if objmap is None:
            return

        component_id = objmap.id

        if component_id not in self.held_objmaps:
            self.held_objmaps[component_id] = (self.now(), objmap)
        else:
            _, stored_objmap = self.held_objmaps[component_id]

            # Only overwrite _add and remove if the value is True.
            if getattr(objmap, '_add', False):
                stored_objmap._add = objmap._add
            if getattr(objmap, 'remove', False):
                stored_objmap.remove = objmap.remove

            # update the existing objmap's other values
            for p in objmap.__dict__:
                if p not in ('_attrs', 'id', 'modname', 'relname', '_add', 'remove'):
                    setattr(stored_objmap, p, getattr(objmap, p))

    def _expire_blacklisted_components(self):
        now = self.now()
        expired = set()
        for component_id, added_time in self.blacklisted_components.iteritems():
            age = now - added_time
            if age > self.delete_blacklist_seconds:
                expired.add(component_id)
        for component_id in expired:
            del self.blacklisted_components[component_id]

    def _new_objmap(self, objmap):
        # Create a new empty objmap based on the suppied one, with all
        # structural properties carried over, but no data, no _add, and no
        # remove.
        new_objmap = ObjectMap()

        if objmap.modname:
            new_objmap.modname = objmap.modname
        if objmap.compname:
            new_objmap.compname = objmap.compname
        if objmap.classname:
            new_objmap.classname = objmap.classname
        if hasattr(objmap, 'relname'):
            new_objmap.relname = objmap.relname
        if hasattr(objmap, 'id'):
            new_objmap.id = objmap.id

        return new_objmap

    def drain(self):
        # remove entries from self.blacklisted_components that are too old.
        self._expire_blacklisted_components()

        # return a list of objectmaps that are ready to be applied.
        released_objmaps = {}
        now = self.now()

        # Blacklist any components that have been both added and deleted
        # while in this queue- no need to send such updates to zodb, after all.
        for component_id in self.held_objmaps:
            first_update, objmap = self.held_objmaps[component_id]
            if getattr(objmap, 'remove', False) and getattr(objmap, '_add', False):
                self.blacklisted_components[component_id] = now

        # Remove any updates pertaining to components which are
        # blacklisted.
        for component_id in self.blacklisted_components:
            del self.held_objmaps[component_id]

        # release updates after an appropriate amount of time:
        for component_id in self.held_objmaps:
            first_update, objmap = self.held_objmaps[component_id]

            if getattr(objmap, '_add', False):
                # newly added components get held for "shortlived_seconds"
                release_time = first_update + self.shortlived_seconds
            elif getattr(objmap, 'remove', False):
                # deleted components can be released immediately- there's
                # no benefit in holding a delete.
                release_time = now

                # Blacklist any components that have been deleted.  That is,
                # don't allow them to be re-added or anything else.
                self.blacklisted_components[component_id] = now
            else:
                # regular updates get held for "update_consolidate_seconds"
                release_time = first_update + self.update_consolidate_seconds

            if release_time <= now:
                released_objmaps[component_id] = objmap

        # Purge anything we've released
        for component_id in released_objmaps:
            del self.held_objmaps[component_id]

        # Now, the fun part.  We have a bunch of objmaps in relased_objmaps now,
        # but they may have dependencies upon each other that require them
        # to be applied in the right order, or even split up.
        #
        # The only case where this really is an issue is when one objmap calls
        # set_<relationship>=<id>, where <id> is a newly created component.
        #
        # We define 3 groups of objectmaps, A, B, C.   All maps in set A
        # are applied first, then all in set B, then all in set C.
        #
        # Objmaps that create a component go in set A.
        # If they have set_x references to another component in set A, those
        # references are moved to a newly-created objmap (for the same
        # component) in set B.
        #
        # All other objmaps go in group C.
        #
        # The objmaps in each group are not ordered in any particular way.

        A = []
        B = []
        C = []

        for component_id, objmap in released_objmaps.iteritems():
            if getattr(objmap, '_add', False):
                # this objmap creates a new component- put it in group A
                A.append(objmap)
            else:
                # updating an existing component- group C.
                C.append(objmap)

        # look for references in group A that need to go to group B.
        A_ids = [x.id for x in A]
        for objmap in A:
            moved = {}
            for k, v in objmap.__dict__.iteritems():
                if k.startswith('set_') and v in A_ids:
                    # take it out of the original objmap
                    moved[k] = v
                    delattr(objmap, k)
                    objmap._attrs.remove(k)
            if moved:
                # create a new objmap for this component, with just
                # the set_ properties we removed from the original in it.
                new_om = self._new_objmap(objmap)
                new_om.updateFromDict(moved)
                B.append(new_om)

        return A + B + C
