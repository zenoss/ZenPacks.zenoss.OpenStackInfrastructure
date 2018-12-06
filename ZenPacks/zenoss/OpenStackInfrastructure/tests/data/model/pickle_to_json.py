#!/usr/bin/env python

##############################################################################
#
# Copyright (C) Zenoss, Inc. 2018, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

# Convert a pickle file from zenmodeler --save_raw_results into a
# json format suitable for our unit tests.

import json
import pickle
import re
import sys

import Globals
from ZenPacks.zenoss.OpenStackInfrastructure.hostmap import HostMap
from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import next_ip_address

if len(sys.argv) != 2:
    raise Exception("Usage: %s <pickle file>" % sys.argv[0])

with open(sys.argv[1], 'r') as f:
    data = pickle.load(f)

if type(data.get('hostmap')) == HostMap:
    data['hostmap_mappings'] = data['hostmap'].freeze_mappings()
    data['hostmap_dns'] = data['hostmap'].resolved_hostnames
    del data['hostmap']

else:
    # Older versions of the modeler both didn't pickle the hostmap
    # object and also replaced the host references with host IDs.
    #
    # This means that we can't fully reverse engineer hostmap_mappings
    # and hostmap_dns from what we have available.
    #
    # We can approximate it though, by assigning an arbitrary IP to every
    # host ID we see, and reversing out a host reference (name).
    # This is sufficient for writing basic unit tests.

    # Find all the host IDs:
    hostids = set()

    for service in data['services']:
        if 'host' in service:
            hostids.add(service['host'])

        for agent in data['agents']:
            if 'host' in agent:
                hostids.add(agent['host'])

        for service in data['cinder_services']:
            if 'host' in service:
                hostids.add(service['host'])

        for host in data['zOpenStackNovaApiHosts'] + data['zOpenStackExtraHosts'] + [data['nova_url_host']] + [data['cinder_url_host']]:
            hostids.add(host)

    data['hostmap_mappings'] = {}
    data['hostmap_dns'] = {}
    for hostid in hostids:
        if hostid is None:
            continue

        # make up a hostname based on the hostref.  This is definitely
        # not necessarily correct in all cases, but it should be sufficient.
        hostref = re.sub(r'^host-', '', hostid)
        data['hostmap_mappings'][hostref] = hostid
        data['hostmap_dns'][hostref] = next_ip_address()

print json.dumps(data, indent=4)
