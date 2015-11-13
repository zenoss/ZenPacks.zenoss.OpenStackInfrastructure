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
import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('openstackHelper')

from optparse import OptionParser
from twisted.internet.defer import inlineCallbacks, returnValue

from apiclients.txapiclient import APIClient


class OpenstackHelper(object):

    @inlineCallbacks
    def getRegions(self, username, api_key, project_id, auth_url):
        """Get a list of available regions, given a keystone endpoint and credentials."""

        client = APIClient(
            username=username,
            password=api_key,
            project_id=project_id,
            auth_url=auth_url,
        )

        serviceCatalog = yield client.serviceCatalog()

        ep = []
        [ep.extend(x['endpoints']) for x in serviceCatalog]
        regions = set([x['region'] for x in ep])

        returnValue([{'key': c, 'label': c} for c in sorted(regions)])

    @inlineCallbacks
    def getCeilometerUrl(self, username, api_key, project_id, auth_url, region_name):
        """Return the first defined ceilometer URL, given a keystone endpoint,
        credentials, and a region.  May return an empty string if none is found."""

        client = KeystoneAPIClient(
            username=username,
            password=api_key,
            project_id=project_id,
            auth_url=auth_url,
        )

        serviceCatalog = yield client.serviceCatalog()

        for sc in serviceCatalog:
            if sc['type'] == 'metering':
                for endpoint in sc['endpoints']:
                    if endpoint['region'] == region_name:
                        returnValue(str(endpoint['publicURL']))
                        return

        # never found one.
        returnValue("")


if __name__ == '__main__':
    from twisted.internet import reactor
    OpenstackHelper.exitValue = 0

    try:
        methodname = sys.argv.pop(1)
    except Exception:
        pass

    supported_methods = {
        'getRegions': ('username', 'api_key', 'project_id', 'auth_url',),
        'getCeilometerUrl': ('username', 'api_key', 'project_id', 'auth_url', 'region_name',)
    }

    if methodname in supported_methods:
        required_opts = supported_methods[methodname]
        parser = OptionParser(usage="usage: %%prog %s [options]" % methodname)
        for opt in required_opts:
            parser.add_option("--" + opt, dest=opt)
        (options, args) = parser.parse_args()

        for required_opt in required_opts:
            if getattr(options, required_opt) is None:
                parser.print_help()
                parser.error("Option '--%s' is required." % required_opt)

        helper = OpenstackHelper()
        method = getattr(helper, methodname)
        kwargs = {}
        for opt in required_opts:
            kwargs[opt] = getattr(options, opt)

        def success(result):
            print json.dumps(result)
            if reactor.running:
                reactor.stop()

        def failure(failure):
            OpenstackHelper.exitValue = 1
            log.error(failure)
            error = "%s: %s" % (failure.value.__class__.__name__, str(failure.value))
            print json.dumps({'error': error})
            if reactor.running:
                reactor.stop()

        # invoke the method with the supplied arguments
        d = method(**kwargs)
        d.addCallback(success)
        d.addErrback(failure)
        reactor.run()

        sys.exit(OpenstackHelper.exitValue)

    else:
        print >> sys.stderr, "Usage: %s (%s) [options]" % (
            sys.argv[0],
            '|'.join(sorted(supported_methods.keys()))
        )
        sys.exit(1)
