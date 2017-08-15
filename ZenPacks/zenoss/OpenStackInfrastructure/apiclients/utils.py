###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2017, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

# Note: because this file is included (indirectly) by openstack_helper.py,
# which does not 'import Globals' for performance reasons, we can not
# depend on any platform or zenpack modules here.

from twisted.internet import reactor, defer, error
from twisted.python import failure

import logging
LOG = logging.getLogger('zen.OpenStack.apiclient.utils')

SEMAPHORES = {}
ZP_VERSION = []


def zenpack_version():
    if not ZP_VERSION:
        import pkg_resources
        working_set = pkg_resources.WorkingSet()
        requirement = pkg_resources.Requirement.parse('ZenPacks.zenoss.OpenStackInfrastructure')
        ZP_VERSION.append(working_set.find(requirement).version)
    return ZP_VERSION[0]


def add_timeout(deferred, seconds, exception_class=error.TimeoutError):
    """Return new Deferred that will errback TimeoutError after seconds."""
    deferred_with_timeout = defer.Deferred()

    def fire_timeout():
        deferred.cancel()

        if not deferred_with_timeout.called:
            deferred_with_timeout.errback(exception_class())

    delayed_timeout = reactor.callLater(seconds, fire_timeout)

    def handle_result(result):
        # Cancel the timeout if it hasn't yet occurred.
        if delayed_timeout.active():
            delayed_timeout.cancel()

        if isinstance(result, failure.Failure):
            # Stop the errback chain if deferred was canceled by timeout.
            if isinstance(result.value, defer.CancelledError):
                return

            # Propagate other errors.
            deferred_with_timeout.errback(exception_class())
        else:
            # Propagate all good results.
            deferred_with_timeout.callback(result)

    deferred.addBoth(handle_result)

    return deferred_with_timeout


def getDeferredSemaphore(key, limit):
    if key not in SEMAPHORES:
        SEMAPHORES[key] = defer.DeferredSemaphore(limit)
    semaphore = SEMAPHORES[key]

    if semaphore.limit != limit:
        if limit >= semaphore.tokens:
            semaphore.limit = limit
            LOG.info("Unable to lower maximum parallel query limit for %s to %d ", key, limit)
        else:
            LOG.warning("Unable to lower maximum parallel query limit for %s to %d at this time (%d connections currently active)", key, limit, semaphore.tokens)

    return semaphore
