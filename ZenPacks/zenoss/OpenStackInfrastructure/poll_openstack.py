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

from twisted.internet.defer import inlineCallbacks, returnValue

from apiclients.exceptions import APIClientError
from apiclients.session import SessionManager
from apiclients.txapiclient import NovaClient, NeutronClient, CinderClient


class OpenStackPoller(object):

    def __init__(self, username, api_key, project_id, user_domain_name, project_domain_name, auth_url, region_name):
        self._username = username
        self._api_key = api_key
        self._project_id = project_id
        self._user_domain_name = user_domain_name
        self._project_domain_name = project_domain_name
        self._auth_url = auth_url
        self._api_version = 2
        self._region_name = region_name
        self.api_error_messages = None

    def api_event_to_data(self, exception):
        """Append an event to existing data dictionary"""

        if not self.api_error_messages:
            self.api_error_messages = set()

        self.api_error_messages.add(exception.message)

    @inlineCallbacks
    def _populateFlavorData(self, nova, data):

        try:
            result = yield nova.flavors(detailed=True, is_public=None)
        except APIClientError as ex:
            if '403 Forbidden' in ex.message:
                return
            else:
                self.api_event_to_data(ex)
                return

        data['flavorTotalCount'] = len(result['flavors'])

    @inlineCallbacks
    def _populateImageData(self, nova, data):

        try:
            result = yield nova.images(limit=0)
        except APIClientError as ex:
            if '403 Forbidden' in ex.message:
                return
            else:
                self.api_event_to_data(ex)
                return

        data['imageTotalCount'] = 0
        data['imageSavingCount'] = 0
        data['imageUnknownCount'] = 0
        data['imagePreparingCount'] = 0
        data['imageActiveCount'] = 0
        data['imageQueuedCount'] = 0
        data['imageFailedCount'] = 0
        data['imageOtherCount'] = 0

        for image in result.get('images'):
            data['imageTotalCount'] += 1

            if image['status'] == 'SAVING':
                data['imageSavingCount'] += 1
            elif image['status'] == 'UNKNOWN':
                data['imageUnknownCount'] += 1
            elif image['status'] == 'PREPARING':
                data['imagePreparingCount'] += 1
            elif image['status'] == 'ACTIVE':
                data['imageActiveCount'] += 1
            elif image['status'] == 'QUEUED':
                data['imageQueuedCount'] += 1
            elif image['status'] == 'FAILED':
                data['imageFailedCount'] += 1
            else:
                # As of Cactus (v1.1) there shouldn't be any other statuses.
                data['imageOtherCount'] += 1

    @inlineCallbacks
    def _populateServerData(self, nova, data):

        try:
            result = yield nova.servers(detailed=True, search_opts={'all_tenants': 1})
        except APIClientError as ex:
            if '403 Forbidden' in ex.message:
                result = yield nova.servers_single(detailed=True)
            else:
                self.api_event_to_data(ex)
                return

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

        for server in result['servers']:
            data['serverTotalCount'] += 1

            if server['status'] == 'ACTIVE':
                data['serverActiveCount'] += 1
            elif server['status'] == 'BUILD':
                data['serverBuildCount'] += 1
            elif server['status'] == 'REBUILD':
                data['serverRebuildCount'] += 1
            elif server['status'] == 'SUSPENDED':
                data['serverSuspendedCount'] += 1
            elif server['status'] == 'QUEUE_RESIZE':
                data['serverQueueResizeCount'] += 1
            elif server['status'] == 'PREP_RESIZE':
                data['serverPrepResizeCount'] += 1
            elif server['status'] == 'RESIZE':
                data['serverResizeCount'] += 1
            elif server['status'] == 'VERIFY_RESIZE':
                data['serverVerifyResizeCount'] += 1
            elif server['status'] == 'PASSWORD':
                data['serverPasswordCount'] += 1
            elif server['status'] == 'RESCUE':
                data['serverRescueCount'] += 1
            elif server['status'] == 'REBOOT':
                data['serverRebootCount'] += 1
            elif server['status'] == 'HARD_REBOOT':
                data['serverHardRebootCount'] += 1
            elif server['status'] == 'DELETE_IP':
                data['serverDeleteIpCount'] += 1
            elif server['status'] == 'UNKNOWN':
                data['serverUnknownCount'] += 1
            else:
                # As of Cactus (v1.1) there shouldn't be any other statuses.
                data['serverOtherCount'] += 1

    @inlineCallbacks
    def _populateAgentData(self, neutron, data):

        try:
            result = yield neutron.agents()
        except APIClientError as ex:
            if '403 Forbidden' in ex.message:
                return
            else:
                self.api_event_to_data(ex)
                return

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

        for agent in result.get('agents', {}):
            data['agentTotalCount'] += 1

            if agent['agent_type'] == 'DHCP agent':
                data['agentDHCPCount'] += 1
            elif agent['agent_type'] == 'Open vSwitch agent':
                data['agentOVSCount'] += 1
            elif agent['agent_type'] == 'Linux bridge agent':
                data['agentLinuxBridgeCount'] += 1
            elif agent['agent_type'] == 'HyperV agent':
                data['agentHyperVCount'] += 1
            elif agent['agent_type'] == 'NEC plugin agent':
                data['agentNECCount'] += 1
            elif agent['agent_type'] == 'OFA driver agent':
                data['agentOFACount'] += 1
            elif agent['agent_type'] == 'L3 agent':
                data['agentL3Count'] += 1
            elif agent['agent_type'] == 'Loadbalancer agent':
                data['agentLBCount'] += 1
            elif agent['agent_type'] == 'Mellanox plugin agent':
                data['agentMLNXCount'] += 1
            elif agent['agent_type'] == 'Metering agent':
                data['agentMeteringCount'] += 1
            elif agent['agent_type'] == 'Metadata agent':
                data['agentMetadataCount'] += 1
            elif agent['agent_type'] == 'IBM SDN-VE agent':
                data['agentSDNVECount'] += 1
            elif agent['agent_type'] == 'NIC Switch agent':
                data['agentNICSCount'] += 1
            if agent['alive'] is True:
                data['agentAliveCount'] += 1
            else:
                data['agentDeadCount'] += 1

    @inlineCallbacks
    def _populateNetworkData(self, neutron, data):

        try:
            result = yield neutron.networks()
        except APIClientError as ex:
            if '403 Forbidden' in ex.message:
                return
            else:
                self.api_event_to_data(ex)
                return

        data['networkTotalCount'] = 0
        data['networkActiveCount'] = 0
        data['networkBuildCount'] = 0
        data['networkDownCount'] = 0
        data['networkErrorCount'] = 0
        data['networkSharedCount'] = 0
        data['networkExternalCount'] = 0
        data['networkInternalCount'] = 0

        for net in result.get('networks', {}):
            data['networkTotalCount'] += 1

            if net['status'] == 'ACTIVE':
                data['networkActiveCount'] += 1
            elif net['status'] == 'BUILD':
                data['networkBuildCount'] += 1
            elif net['status'] == 'DOWN':
                data['networkDownCount'] += 1
            elif net['status'] == 'ERROR':
                data['networkErrorCount'] += 1
            if net['shared'] is True:
                data['networkSharedCount'] += 1
            if net['router:external'] is True:
                data['networkExternalCount'] += 1
            else:
                data['networkInternalCount'] += 1

    @inlineCallbacks
    def _populateRouterData(self, neutron, data):

        try:
            result = yield neutron.routers()
        except APIClientError as ex:
            if '403 Forbidden' in ex.message:
                return
            else:
                self.api_event_to_data(ex)
                return

        data['routerTotalCount'] = 0
        data['routerActiveCount'] = 0
        data['routerBuildCount'] = 0
        data['routerDownCount'] = 0
        data['routerErrorCount'] = 0

        for router in result.get('routers', {}):
            data['routerTotalCount'] += 1

            if router['status'] == 'ACTIVE':
                data['routerActiveCount'] += 1
            elif router['status'] == 'BUILD':
                data['routerBuildCount'] += 1
            elif router['status'] == 'DOWN':
                data['routerDownCount'] += 1
            elif router['status'] == 'ERROR':
                data['routerErrorCount'] += 1

    @inlineCallbacks
    def _populatePoolData(self, cinder, data):

        try:
            result = yield cinder.pools()
        except APIClientError as ex:
            if '403 Forbidden' in ex.message:
                return
            else:
                self.api_event_to_data(ex)
                return

        data['poolTotalCount'] = 0
        data['poolThinProvisioningSupportCount'] = 0
        data['poolThickProvisioningSupportCount'] = 0
        data['poolQoSSupportCount'] = 0

        def pool_has_data(pool, key1, key2):
            if pool.get(key1, {}).get(key2, False):
                return 1
            return 0

        for pool in result.get('pools', {}):
            data['poolTotalCount'] += 1

            data['poolThinProvisioningSupportCount'] += \
                pool_has_data(pool, 'capabilities', 'thin_provisioning_support')
            data['poolThickProvisioningSupportCount'] += \
                pool_has_data(pool, 'capabilities', 'thick_provisioning_support')
            data['poolQoSSupportCount'] += \
                pool_has_data(pool, 'capabilities', 'QoS_support')

    @inlineCallbacks
    def _populateVolumeData(self, cinder, data):

        try:
            result = yield cinder.volumes()
        except APIClientError as ex:
            if '403 Forbidden' in ex.message:
                return
            else:
                self.api_event_to_data(ex)
                return

        data['volumeTotalCount'] = 0
        data['volumeActiveCount'] = 0
        data['volumeBootableCount'] = 0
        data['volumeAttachedCount'] = 0
        data['volumeAvailableCount'] = 0
        data['volumeInUseCount'] = 0
        data['volumeUnknownCount'] = 0

        for volume in result.get('volumes', {}):
            data['volumeTotalCount'] += 1

            if volume['status'] == 'ACTIVE':
                data['volumeActiveCount'] += 1
                data['volumeAvailableCount'] += 1
            if volume['status'] == 'in-use':
                data['volumeActiveCount'] += 1
                data['volumeInUseCount'] += 1
            if volume['bootable'] == 'true':
                data['volumeBootableCount'] += 1
            if len(volume['attachments']) > 0:
                data['volumeAttachedCount'] += 1
            if volume['status'] == 'ERROR':
                data['volumeErrorCount'] += 1

    @inlineCallbacks
    def _populateSnapshotData(self, cinder, data):

        try:
            result = yield cinder.volumesnapshots()
        except APIClientError as ex:
            if '403 Forbidden' in ex.message:
                return
            else:
                self.api_event_to_data(ex)
                return

        data['snapshotTotalCount'] = 0
        data['snapshotAvailableCount'] = 0
        data['snapshotInProgressCount'] = 0

        for snapshot in result.get('snapshots', {}):
            data['snapshotTotalCount'] += 1

            if snapshot['status'] == 'available':
                data['snapshotAvailableCount'] += 1
            if '100%' not in snapshot['os-extended-snapshot-attributes:progress']:
                data['snapshotInProgressCount'] += 1

    @inlineCallbacks
    def getData(self):
        sm = SessionManager(
            self._username,
            self._api_key,
            self._auth_url,
            self._project_id,
            self._user_domain_name,
            self._project_domain_name,
            self._region_name)
        nova = NovaClient(session_manager=sm)
        neutron = NeutronClient(session_manager=sm)
        cinder = CinderClient(session_manager=sm)

        data = {}
        data['events'] = []

        try:
            yield self._populateFlavorData(nova, data)
            yield self._populateImageData(nova, data)
            yield self._populateServerData(nova, data)

            yield self._populateNetworkData(neutron, data)
            yield self._populateAgentData(neutron, data)
            yield self._populateRouterData(neutron, data)

            yield self._populatePoolData(cinder, data)
            yield self._populateVolumeData(cinder, data)
            yield self._populateSnapshotData(cinder, data)

        except Exception:
            raise

        # Raise any non-forbidded API access errors we caught above.
        if self.api_error_messages:
            raise Exception("APIClientError")

        returnValue(data)

    @inlineCallbacks
    def printJSON(self):
        data = None
        try:
            data = yield self.getData()

            data['events'].append(dict(
                severity=0,
                summary='OpenStack connectivity restored',
                eventKey='openStackPoll',
                eventClassKey='openStack-poll',
            ))
        except Exception, ex:

            summary = 'OpenStack failure: {}. '.format(ex)
            if self.api_error_messages:
                summary += 'APIClient Errors: '
                summary += '. '.join(self.api_error_messages)

            data = dict(
                events=[dict(
                    severity=5,
                    summary=summary,
                    eventKey='openStackPoll',
                    eventClassKey='openstack-poll',
                )]
            )

        print json.dumps(data, indent=4, sort_keys=True)

        # Shut down, we're done.
        if reactor.running:
            reactor.stop()


if __name__ == '__main__':
    from twisted.internet import reactor

    username = api_key = project_id = user_domain_name = project_domain_name = auth_url = api_version = region_name = None
    try:
        username, api_key, project_id, user_domain_name, project_domain_name, auth_url, region_name = sys.argv[1:8]
    except ValueError:
        print >> sys.stderr, (
            "Usage: %s <username> <api_key> <project_id> <user_domain_name> <project_domain_name> <auth_url> <region_name>"
            ) % sys.argv[0]

        sys.exit(1)

    poller = OpenStackPoller(
        username, api_key, project_id, user_domain_name, project_domain_name, auth_url, region_name)

    poller.printJSON()
    reactor.run()
