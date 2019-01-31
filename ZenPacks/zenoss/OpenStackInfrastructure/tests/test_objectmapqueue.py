#!/usr/bin/env python

##############################################################################
#
# Copyright (C) Zenoss, Inc. 2019, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import Globals

import logging
logging.basicConfig(level=logging.ERROR)
log = logging.getLogger('zen.OpenStack')


from Products.DataCollector.plugins.DataMaps import ObjectMap

from Products.ZenUtils.Utils import unused
unused(Globals)

from ZenPacks.zenoss.OpenStackInfrastructure.datamaps import ConsolidatingObjectMapQueue
from ZenPacks.zenoss.ZenPackLib import zenpacklib
# Required before zenpacklib.TestCase can be used.
zenpacklib.enableTesting()


class TestConsolidatingObjectMapQueue(zenpacklib.TestCase):

    def afterSetUp(self):
        self.queue = ConsolidatingObjectMapQueue()
        self.clock = 1000.0

        def _now():
            return self.clock
        self.queue.now = _now

    def new_objmap(self, component_id):
        return ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.TestComponent',
            compname='',
            data={
                'id': component_id,
                'relname': 'components'
            }
        )

    def depends_on_ids(self, om):
        for k, v in om.__dict__.iteritems():
            if k.startswith('set_'):
                if isinstance(v, list):
                    for x in v:
                        yield x
                else:
                    yield v

    def test_single_update(self):
        objmap = self.new_objmap("c1")
        objmap.prop1 = 'value1'
        self.queue.append(objmap)

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Should hold updates for 40 seconds")

        # time passes..
        self.clock += 40

        # should now be released
        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 1, msg="Should have held updates for 40 seconds")
        self.assertEquals(objmaps[0].prop1, 'value1')

        # much time passes..
        self.clock += 4000
        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Queue should still be empty")

    def test_multiple_updates(self):
        objmap = self.new_objmap("c1")
        objmap.prop1 = 'value1'
        objmap.prop2 = 'value2'
        self.queue.append(objmap)

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Should hold updates for 40 seconds")

        objmap = self.new_objmap("c1")
        objmap.prop1 = 'value3'
        self.queue.append(objmap)

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Should hold updates for 40 seconds")

        # time passes..
        self.clock += 40

        # should now be released
        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 1, msg="Should have held updates for 40 seconds")
        self.assertEquals(objmaps[0].prop2, 'value2', msg="Should have values from first map")
        self.assertEquals(objmaps[0].prop1, 'value3', msg="Should override values")

        # much time passes..
        self.clock += 4000
        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Queue should still be empty")

    def test_add_component(self):
        objmap = self.new_objmap("c1")
        objmap._add = True
        objmap.prop1 = 'value1'
        objmap.prop2 = 'value2'
        self.queue.append(objmap)

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Should hold inserts for 40 seconds")

        # time passes..
        self.clock += 40

        # should now be released
        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 1, msg="Should have held inserts for 40 seconds")
        self.assertEquals(objmaps[0].prop1, 'value1', msg="Should have values from first map")
        self.assertEquals(objmaps[0].prop2, 'value2', msg="Should have values from first map")

        # much time passes..
        self.clock += 4000
        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Queue should still be empty")

    def test_delete_component(self):
        objmap = self.new_objmap("c1")
        objmap._remove = True
        self.queue.append(objmap)

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 1, msg="Should not hold deletes back")

        # much time passes..
        self.clock += 4000
        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Queue should still be empty")

    def test_update_after_delete_component(self):
        objmap = self.new_objmap("c1")
        objmap._remove = True
        self.queue.append(objmap)

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 1, msg="Should not hold deletes back")

        self.clock += 60
        objmap = self.new_objmap("c1")
        objmap.prop1 = 'value2'
        self.queue.append(objmap)
        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Change should have been dropped due to blacklist")

        # much time passes..
        self.clock += 4000
        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Queue should still be empty")

    def test_lifecycle_shortlived(self):
        objmap = self.new_objmap("c1")
        objmap._add = True
        objmap.prop1 = 'value1'
        objmap.prop2 = 'value2'
        self.queue.append(objmap)

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Should hold inserts for 40 seconds")

        objmap = self.new_objmap("c1")
        objmap._remove = True
        self.queue.append(objmap)

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Still Nothing to do, since it was deleted before add was processed")

        # much time passes..
        self.clock += 4000
        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Queue should still be empty")

    def test_lifecycle_longlived(self):
        objmap = self.new_objmap("c1")
        objmap._add = True
        objmap.prop1 = 'value1'
        objmap.prop2 = 'value2'
        self.queue.append(objmap)

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Should hold inserts for 40 seconds")

        # time passes..
        self.clock += 60

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 1, msg="Should have held inserts for 40 seconds")
        self.assertTrue(objmaps[0]._add, msg="Component created as expected")

        # time passes..
        self.clock += 60

        # remove it.
        objmap = self.new_objmap("c1")
        objmap._remove = True
        self.queue.append(objmap)

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 1, msg="Component should be removed")
        self.assertTrue(objmaps[0]._remove, msg="Component removed as expected")

        # much time passes..
        self.clock += 4000
        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Queue should still be empty")

    def test_interrelated_toOne(self):
        objmap1 = self.new_objmap("c1")
        objmap1._add = True
        objmap2 = self.new_objmap("c2")
        objmap2._add = True
        objmap2.set_foo = "c4"
        objmap3 = self.new_objmap("c3")
        objmap3._add = True
        objmap3.set_foo = "c1"

        self.queue.append(objmap3)
        self.queue.append(objmap2)
        self.queue.append(objmap1)

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Should hold inserts for 40 seconds")

        # time passes..
        self.clock += 60

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 4, msg="Should have released all 3+1")

        # are all dependencies met?
        existing = set(['c4'])
        for objmap in objmaps:
            existing.add(objmap.id)
            self.assertTrue(
                existing.issuperset(self.depends_on_ids(objmap)),
                msg="All IDs referred to by %s are known (known=%s)" % (objmap, existing))

        # Try it again, flipped around.
        objmap1 = self.new_objmap("c1")
        objmap1._add = True
        objmap2 = self.new_objmap("c2")
        objmap2._add = True
        objmap2.set_foo = "c4"
        objmap3 = self.new_objmap("c3")
        objmap3._add = True
        objmap3.set_foo = "c1"

        self.queue.reset()
        self.queue.append(objmap1)
        self.queue.append(objmap2)
        self.queue.append(objmap3)
        self.clock += 60
        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 4, msg="Should have released all 3+1")

        existing = set(['c4'])
        for objmap in objmaps:
            existing.add(objmap.id)
            self.assertTrue(
                existing.issuperset(self.depends_on_ids(objmap)),
                msg="All IDs referred to by %s are known (known=%s)" % (objmap, existing))

    def test_interrelated_toMany(self):
        objmap1 = self.new_objmap("c1")
        objmap1._add = True
        objmap2 = self.new_objmap("c2")
        objmap2._add = True
        objmap2.set_foos = ["c4", "c3"]
        objmap3 = self.new_objmap("c3")
        objmap3._add = True
        objmap3.set_foos = ["c1"]

        self.queue.append(objmap3)
        self.queue.append(objmap2)
        self.queue.append(objmap1)

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 0, msg="Should hold inserts for 40 seconds")

        # time passes..
        self.clock += 60

        objmaps = self.queue.drain()
        self.assertEquals(len(objmaps), 5, msg="Should have released all 3+2")

        # are all dependencies met?
        existing = set(['c4'])
        for objmap in objmaps:
            existing.add(objmap.id)
            self.assertTrue(
                existing.issuperset(self.depends_on_ids(objmap)),
                msg="All IDs referred to by %s are known (known=%s)" % (objmap, existing))


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestConsolidatingObjectMapQueue))
    return suite


if __name__ == "__main__":
    from zope.testrunner.runner import Runner
    runner = Runner(found_suites=[test_suite()])
    runner.run()
