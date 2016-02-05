#!/usr/bin/env python
###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2014, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

import json
import sys
import logging
log = logging.getLogger('zen.OpenStack.poll_openstack')

import Globals
from Products.ZenUtils.Utils import unused
unused(Globals)

from twisted.internet.defer import inlineCallbacks, returnValue

from utils import add_local_lib_path
add_local_lib_path()

from apiclients.txapiclient import APIClient

class OpenStackPoller(object):
    def __init__(self, username, api_key, project_id, auth_url, region_name):
        self._username = username
        self._api_key = api_key
        self._project_id = project_id
        self._auth_url = auth_url
        self._api_version = 2
        self._region_name = region_name

    @inlineCallbacks
    def _populateFlavorData(self, client, data):
        result = yield client.nova_flavors(detailed=True, is_public=None)
        data['flavorTotalCount'] = len(result['flavors'])

    @inlineCallbacks
    def _populateImageData(self, client, data):
        data['imageTotalCount'] = 0
        data['imageSavingCount'] = 0
        data['imageUnknownCount'] = 0
        data['imagePreparingCount'] = 0
        data['imageActiveCount'] = 0
        data['imageQueuedCount'] = 0
        data['imageFailedCount'] = 0
        data['imageOtherCount'] = 0

        result = yield client.nova_images(detailed=True, limit=None)

        for image in result['images']:
            data['imageTotalCount'] += 1
            severity = None

            if image['status'] == 'SAVING':
                data['imageSavingCount'] += 1
                severity = 2
            elif image['status'] == 'UNKNOWN':
                data['imageUnknownCount'] += 1
                severity = 5
            elif image['status'] == 'PREPARING':
                data['imagePreparingCount'] += 1
                severity = 2
            elif image['status'] == 'ACTIVE':
                data['imageActiveCount'] += 1
                severity = 0
            elif image['status'] == 'QUEUED':
                data['imageQueuedCount'] += 1
                severity = 2
            elif image['status'] == 'FAILED':
                data['imageFailedCount'] += 1
                severity = 5
            else:
                # As of Cactus (v1.1) there shouldn't be any other statuses.
                data['imageOtherCount'] += 1
                severity = 1

            data['events'].append(dict(
                severity=severity,
                summary='image status is {0}'.format(image['status']),
                component='image{0}'.format(image['id']),
                eventKey='imageStatus',
                eventClassKey='openstackImageStatus',
                imageStatus=image['status'],
            ))

    @inlineCallbacks
    def _populateServerData(self, client, data):
        data['serverTotalCount'] = 0
        data['serverActiveCount'] = 0
        data['serverBuildCount'] = 0
        data['serverRebuildCount'] = 0
        data['serverSuspendedCount'] = 0
        data['serverQueueResizeCount'] = 0
        data['serverPrepResizeCount'] = 0
        data['serverResizeCount'] = 0
        data['serverVerifyResizeCount'] = 0
        data['serverPasswordCount'] = 0
        data['serverRescueCount'] = 0
        data['serverRebootCount'] = 0
        data['serverHardRebootCount'] = 0
        data['serverDeleteIpCount'] = 0
        data['serverUnknownCount'] = 0
        data['serverOtherCount'] = 0

        result = yield client.nova_servers(detailed=True, search_opts={'all_tenants': 1})

        for server in result['servers']:
            data['serverTotalCount'] += 1
            severity = None

            if server['status'] == 'ACTIVE':
                data['serverActiveCount'] += 1
                severity = 0
            elif server['status'] == 'BUILD':
                data['serverBuildCount'] += 1
                severity = 5
            elif server['status'] == 'REBUILD':
                data['serverRebuildCount'] += 1
                severity = 5
            elif server['status'] == 'SUSPENDED':
                data['serverSuspendedCount'] += 1
                severity = 2
            elif server['status'] == 'QUEUE_RESIZE':
                data['serverQueueResizeCount'] += 1
                severity = 2
            elif server['status'] == 'PREP_RESIZE':
                data['serverPrepResizeCount'] += 1
                severity = 3
            elif server['status'] == 'RESIZE':
                data['serverResizeCount'] += 1
                severity = 4
            elif server['status'] == 'VERIFY_RESIZE':
                data['serverVerifyResizeCount'] += 1
                severity = 2
            elif server['status'] == 'PASSWORD':
                data['serverPasswordCount'] += 1
                severity = 2
            elif server['status'] == 'RESCUE':
                data['serverRescueCount'] += 1
                severity = 5
            elif server['status'] == 'REBOOT':
                data['serverRebootCount'] += 1
                severity = 5
            elif server['status'] == 'HARD_REBOOT':
                data['serverHardRebootCount'] += 1
                severity = 5
            elif server['status'] == 'DELETE_IP':
                data['serverDeleteIpCount'] += 1
                severity = 3
            elif server['status'] == 'UNKNOWN':
                data['serverUnknownCount'] += 1
                severity = 5
            else:
                # As of Cactus (v1.1) there shouldn't be any other statuses.
                data['serverOtherCount'] += 1
                severity = 1


    @inlineCallbacks
    def _populateAgentData(self, client, data):
        data['agentTotalCount'] = 0
        data['agentDHCPCount'] = 0
        data['agentOVSCount'] = 0
        data['agentLinuxBridgeCount'] = 0
        data['agentHyperVCount'] = 0
        data['agentNECCount'] = 0
        data['agentOFACount'] = 0
        data['agentL3Count'] = 0
        data['agentLBCount'] = 0
        data['agentMLNXCount'] = 0
        data['agentMeteringCount'] = 0
        data['agentMetadataCount'] = 0
        data['agentSDNVECount'] = 0
        data['agentNICSCount'] = 0
        data['agentAliveCount'] = 0
        data['agentDeadCount'] = 0
        data['agentMLNXCount'] = 0
        data['agentMeteringCount'] = 0

        result = yield client.neutron_agents()

        for agent in result['agents']:
            data['agentTotalCount'] += 1
            severity = None

            if agent['agent_type'] == 'DHCP agent':
                data['agentDHCPCount'] += 1
                severity = 0
            elif agent['agent_type'] == 'Open vSwitch agent':
                data['agentOVSCount'] += 1
                severity = 0
            elif agent['agent_type'] == 'Linux bridge agent':
                data['agentLinuxBridgeCount'] += 1
                severity = 0
            elif agent['agent_type'] == 'HyperV agent':
                data['agentHyperVCount'] += 1
                severity = 0
            elif agent['agent_type'] == 'NEC plugin agent':
                data['agentNECCount'] += 1
                severity = 0
            elif agent['agent_type'] == 'OFA driver agent':
                data['agentOFACount'] += 1
                severity = 0
            elif agent['agent_type'] == 'L3 agent':
                data['agentL3Count'] += 1
                severity = 0
            elif agent['agent_type'] == 'Loadbalancer agent':
                data['agentLBCount'] += 1
                severity = 0
            elif agent['agent_type'] == 'Mellanox plugin agent':
                data['agentMLNXCount'] += 1
                severity = 0
            elif agent['agent_type'] == 'Metering agent':
                data['agentMeteringCount'] += 1
                severity = 0
            elif agent['agent_type'] == 'Metadata agent':
                data['agentMetadataCount'] += 1
                severity = 0
            elif agent['agent_type'] == 'IBM SDN-VE agent':
                data['agentSDNVECount'] += 1
                severity = 0
            elif agent['agent_type'] == 'NIC Switch agent':
                data['agentNICSCount'] += 1
                severity = 0
            if agent['alive'] is True:
                data['agentAliveCount'] += 1
                severity = 0
            else:
                data['agentDeadCount'] += 1
                severity = 5


    @inlineCallbacks
    def _populateNetworkData(self, client, data):
        data['networkTotalCount'] = 0
        data['networkActiveCount'] = 0
        data['networkBuildCount'] = 0
        data['networkDownCount'] = 0
        data['networkErrorCount'] = 0
        data['networkSharedCount'] = 0
        data['networkExternalCount'] = 0
        data['networkInternalCount'] = 0

        result = yield client.neutron_networks()

        for net in result['networks']:
            data['networkTotalCount'] += 1
            severity = None

            if net['status'] == 'ACTIVE':
                data['networkActiveCount'] += 1
                severity = 0
            elif net['status'] == 'BUILD':
                data['networkBuildCount'] += 1
                severity = 5
            elif net['status'] == 'DOWN':
                data['networkDownCount'] += 1
                severity = 5
            elif net['status'] == 'ERROR':
                data['networkErrorCount'] += 1
                severity = 5
            if net['shared'] is True:
                data['networkSharedCount'] += 1
                severity = None
            if net['router:external'] is True:
                data['networkExternalCount'] += 1
                severity = None
            else:
                data['networkInternalCount'] += 1
                severity = None


    @inlineCallbacks
    def _populateRouterData(self, client, data):
        data['routerTotalCount'] = 0
        data['routerActiveCount'] = 0
        data['routerBuildCount'] = 0
        data['routerDownCount'] = 0
        data['routerErrorCount'] = 0

        result = yield client.neutron_routers()

        for router in result['routers']:
            data['routerTotalCount'] += 1
            severity = None

            if router['status'] == 'ACTIVE':
                data['routerActiveCount'] += 1
                severity = 0
            elif router['status'] == 'BUILD':
                data['routerBuildCount'] += 1
                severity = 5
            elif router['status'] == 'DOWN':
                data['routerDownCount'] += 1
                severity = 5
            elif router['status'] == 'ERROR':
                data['routerErrorCount'] += 1
                severity = 5


    @inlineCallbacks
    def _populatePoolData(self, client, data):
        data['poolTotalCount'] = 0
        data['poolThinProvisioningSupportCount'] = 0
        data['poolThickProvisioningSupportCount'] = 0
        data['poolQoSSupportCount'] = 0

        result = yield client.cinder_pools()

        for pool in result['pools']:
            data['poolTotalCount'] += 1

            if pool['capabilities']['thin_provisioning_support']:
                data['poolThinProvisioningSupportCount'] += 1
            elif pool['capabilities']['thick_provisioning_support']:
                data['poolThickProvisioningSupportCount'] += 1
            if pool['capabilities']['QoS_support']:
                data['poolQoSSupportCount'] += 1


    @inlineCallbacks
    def _populateVolumeData(self, client, data):
        data['volumeTotalCount'] = 0
        data['volumeActiveCount'] = 0
        data['volumeBootableCount'] = 0
        data['volumeAttachedCount'] = 0
        data['volumeAvailableCount'] = 0
        data['volumeInUseCount'] = 0
        data['volumeUnknownCount'] = 0

        result = yield client.cinder_volumes()

        for volume in result['volumes']:
            data['volumeTotalCount'] += 1
            severity = None

            if volume['status'] == 'ACTIVE':
                data['volumeActiveCount'] += 1
                data['volumeAvailableCount'] += 1
                severity = 0
            if volume['status'] == 'in-use':
                data['volumeActiveCount'] += 1
                data['volumeInUseCount'] += 1
                severity = 0
            if volume['bootable'] == 'true':
                data['volumeBootableCount'] += 1
                severity = 0
            if len(volume['attachments']) > 0:
                data['volumeAttachedCount'] += 1
                severity = 0
            if volume['status'] == 'ERROR':
                data['volumeErrorCount'] += 1
                severity = 5


    @inlineCallbacks
    def _populateSnapshotData(self, client, data):
        data['snapshotTotalCount'] = 0
        data['snapshotAvailableCount'] = 0
        data['snapshotInProgressCount'] = 0

        result = yield client.cinder_volumesnapshots()

        for snapshot in result['snapshots']:
            data['snapshotTotalCount'] += 1

            if snapshot['status'] == 'available':
                data['snapshotAvailableCount'] += 1
            if '100%' not in snapshot['os-extended-snapshot-attributes:progress']:
                data['snapshotInProgressCount'] += 1


    @inlineCallbacks
    def getData(self):
        client = APIClient(
            self._username,
            self._api_key,
            self._auth_url,
            self._project_id)

        data = {}
        data['events'] = []

        try:
            yield self._populateFlavorData(client, data)
            yield self._populateImageData(client, data)
            yield self._populateServerData(client, data)

            yield self._populateNetworkData(client, data)
            yield self._populateAgentData(client, data)
            yield self._populateRouterData(client, data)

            yield self._populatePoolData(client, data)
            yield self._populateVolumeData(client, data)
            yield self._populateSnapshotData(client, data)

        except Exception:
            raise

        returnValue(data)

    @inlineCallbacks
    def printJSON(self):
        data = None
        try:
            data = yield self.getData()
            data['events'].append(dict(
                severity=0,
                summary='OpenStack connectivity restored',
                eventKey='openStackFailure',
                eventClassKey='openStackRestored',
            ))
        except Exception, ex:
            data = dict(
                events=[dict(
                    severity=5,
                    summary='OpenStack failure: %s' % ex,
                    eventKey='openStackFailure',
                    eventClassKey='openStackFailure',
                )]
            )

        print json.dumps(data)

        # Shut down, we're done.
        if reactor.running:
            reactor.stop()

if __name__ == '__main__':
    from twisted.internet import reactor

    username = api_key = project_id = auth_url = api_version = region_name = None
    try:
        username, api_key, project_id, auth_url, region_name = sys.argv[1:7]
    except ValueError:
        print >> sys.stderr, (
            "Usage: %s <username> <api_key> <project_id> <auth_url> <region_name>"
            ) % sys.argv[0]

        sys.exit(1)

    poller = OpenStackPoller(
        username, api_key, project_id, auth_url, region_name)

    poller.printJSON()
    reactor.run()
