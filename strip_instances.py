#!/usr/bin/env python
#
#
# Copyright (C) Zenoss, Inc. 2008, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
#

"""Remove product instances from objects.xml file.

A bug in Zenoss' ZenPack export causes it to export individual instances
of product classes to the objects.xml file. These instances are related to
devices added to the running Zenoss system, and are not applicable to anyone
else who would install the ZenPack.

It is expected that this script would be located, and executed from the
top-level directory of the ZenPack.

"""

objects_filename = 'ZenPacks.zenoss.OpenStackInfrastructure/objects/objects.xml'

print "Stripping product instances from objects.xml."

lines = []

with open(objects_filename, 'r') as f:
    in_instances = False
    for line in f:
        if line.startswith("<tomany id='instances'>"):
            in_instances = True
            continue

        if in_instances and line.startswith("</tomany>"):
            in_instances = False
            continue

        if not in_instances:
            lines.append(line)

with open(objects_filename, 'w') as f:
    for line in lines:
        f.write(line)
