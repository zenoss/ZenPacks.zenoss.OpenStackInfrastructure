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

import sys
import novaclient

class OpenStackPoller(object):
    _authUrl = None
    _username = None
    _key = None

    def __init__(self, authUrl, username, key):
        self._authUrl = authUrl
        self._username = username
        self._key = key

    def getData(self):
        client = novaclient.OpenStack(
            self._username, self,_key, self._authUrl)

        data = dict(
            flavors=[],
            images=[],
            servers=[],
        )

        # TODO: Stopping work on this here. It turns out that there might not
        #       be anything worth polling for.

        for flavor in client.flavors.list():
            data['flavors'].append(dict(
                id=flavor.id,
                name=flavor.name,
                ram=flavor.ram,
            ))

    def printJSON(self):
        print json.dumps(self.getData())

if __name__ == '__main__':
    authUrl = username = key = None
    try:
        authUrl, username, key = sys.argv[1:4]
    except ValueError:
        print >> sys.stderr, "Usage: {0} <authUrl> <username> <api_key>" \
            .format(sys.argv[0])

        sys.exit(1)

    poller = OpenStackPoller(authUrl, username, key)
    poller.printJSON()

