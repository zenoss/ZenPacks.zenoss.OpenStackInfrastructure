#!/usr/bin/env python
###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2011, Zenoss Inc.
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

from util import addLocalLibPath
addLocalLibPath()

from novaclient import client as novaclient

class OpenStackPoller(object):
    def __init__(self, username, api_key, project_id, auth_url, api_version, region_name):
        self._username = username
        self._api_key = api_key
        self._project_id = project_id
        self._auth_url = auth_url
        self._api_version = api_version
        self._region_name = region_name

    def getData(self):
        if (log.isEnabledFor(logging.DEBUG)):
            http_log_debug = True
            logging.getLogger('novaclient.client').setLevel(logging.DEBUG)
        else:
            http_log_debug = False

        client = novaclient.Client(
            self._api_version,
            self._username,
            self._api_key,
            self._project_id,
            self._auth_url,
            region_name=self._region_name or None,
            http_log_debug=http_log_debug        
        )

        data = {}
        data['events'] = []

        data['flavorTotalCount'] = len(client.flavors.list())

        data['imageTotalCount'] = 0
        data['imageSavingCount'] = 0
        data['imageUnknownCount'] = 0
        data['imagePreparingCount'] = 0
        data['imageActiveCount'] = 0
        data['imageQueuedCount'] = 0
        data['imageFailedCount'] = 0
        data['imageOtherCount'] = 0

        for image in client.images.list():
            data['imageTotalCount'] += 1
            severity = None

            if image.status == 'SAVING':
                data['imageSavingCount'] += 1
                severity = 2
            elif image.status == 'UNKNOWN':
                data['imageUnknownCount'] += 1
                severity = 5
            elif image.status == 'PREPARING':
                data['imagePreparingCount'] += 1
                severity = 2
            elif image.status == 'ACTIVE':
                data['imageActiveCount'] += 1
                severity = 0
            elif image.status == 'QUEUED':
                data['imageQueuedCount'] += 1
                severity = 2
            elif image.status == 'FAILED':
                data['imageFailedCount'] += 1
                severity = 5
            else:
                # As of Cactus (v1.1) there shouldn't be any other statuses.
                data['imageOtherCount'] += 1
                severity = 1

            data['events'].append(dict(
                severity=severity,
                summary='image status is {0}'.format(image.status),
                component='image{0}'.format(image.id),
                eventKey='imageStatus',
                eventClassKey='openstackImageStatus',
                imageStatus=image.status,
            ))

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

        for server in client.servers.list():
            data['serverTotalCount'] += 1
            severity = None

            if server.status == 'ACTIVE':
                data['serverActiveCount'] += 1
                severity = 0
            elif server.status == 'BUILD':
                data['serverBuildCount'] += 1
                severity = 5
            elif server.status == 'REBUILD':
                data['serverRebuildCount'] += 1
                severity = 5
            elif server.status == 'SUSPENDED':
                data['serverSuspendedCount'] += 1
                severity = 2
            elif server.status == 'QUEUE_RESIZE':
                data['serverQueueResizeCount'] += 1
                severity = 2
            elif server.status == 'PREP_RESIZE':
                data['serverPrepResizeCount'] += 1
                severity = 3
            elif server.status == 'RESIZE':
                data['serverResizeCount'] += 1
                severity = 4
            elif server.status == 'VERIFY_RESIZE':
                data['serverVerifyResizeCount'] += 1
                severity = 2
            elif server.status == 'PASSWORD':
                data['serverPasswordCount'] += 1
                severity = 2
            elif server.status == 'RESCUE':
                data['serverRescueCount'] += 1
                severity = 5
            elif server.status == 'REBOOT':
                data['serverRebootCount'] += 1
                severity = 5
            elif server.status == 'HARD_REBOOT':
                data['serverHardRebootCount'] += 1
                severity = 5
            elif server.status == 'DELETE_IP':
                data['serverDeleteIpCount'] += 1
                severity = 3
            elif server.status == 'UNKNOWN':
                data['serverUnknownCount'] += 1
                severity = 5
            else:
                # As of Cactus (v1.1) there shouldn't be any other statuses.
                data['serverOtherCount'] += 1
                severity = 1

            data['events'].append(dict(
                severity=severity,
                summary='server status is {0}'.format(server.status),
                component='server{0}'.format(server.id),
                eventKey='serverStatus',
                eventClassKey='openstackServerStatus',
                serverStatus=server.status,
            ))

        return data

    def printJSON(self):
        data = None
        try:
            data = self.getData()
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

if __name__ == '__main__':
    username = api_key = project_id = auth_url = region_name = None
    try:
        username, api_key, project_id, auth_url, region_name = sys.argv[1:6]
    except ValueError:
        print >> sys.stderr, (
            "Usage: %s <username> <api_key> <project_id> <auth_url> "
            "<region_name>"
            ) % sys.argv[0]

        sys.exit(1)

    poller = OpenStackPoller(
        username, api_key, project_id, auth_url, region_name)

    poller.printJSON()
