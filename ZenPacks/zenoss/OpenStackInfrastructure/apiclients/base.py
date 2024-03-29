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

import logging
log = logging.getLogger('zen.OpenStack.txapiclient')

from .session import SessionManager
from .exceptions import APIClientError

from twisted.internet.defer import inlineCallbacks, returnValue

import json


class BaseClient(object):
    session_manager = None
    keystone_service_type = None  # override in subclasses

    def __init__(self, username=None, password=None, auth_url=None, project_id=None, user_domain_name=None, project_domain_name=None, region_name=None, session_manager=None):
        if session_manager:
            self.session_manager = session_manager
        else:
            self.session_manager = SessionManager(username, password, auth_url, project_id, user_domain_name, project_domain_name,  region_name)

    @inlineCallbacks
    def get_url(self, interface="public"):
        base_url = yield self.session_manager.get_service_url(self.keystone_service_type, interface)
        returnValue(base_url)

    @inlineCallbacks
    def get_json(self, url_path, interface="public", **kwargs):
        """
        Any list operation can potentially return a collection, where pages
        of results are linked by next/previous links.  If found, we will
        follow the 'next' links, building up a merged result, and
        then return the whole thing.
        """
        result = {}
        base_url = yield self.session_manager.get_service_url(self.keystone_service_type, interface)
        if not base_url:
            returnValue(result)

        full_url = base_url + url_path

        while True:
            body, headers = yield self.session_manager.authenticated_GET_request(full_url, params=kwargs)
            # will raise an exception if there was an error, so we can assume
            # that the result is normal json.

            try:
                data = json.loads(body)
            except ValueError:
                raise APIClientError("Unable to parse JSON response from %s: %s" % (full_url, body))

            full_url = None
            for key in data.keys():
                if key != 'links':
                    if isinstance(data[key], list):
                        result.setdefault(key, [])
                        result[key].extend(data[key])
                    elif key in result:
                        log.error("While parsing response to %s, ignoring overwritten key in subsequent page: %s (%s -> %s)",
                            full_url, key, result[key], data[key])
                    else:
                        result[key] = data[key]

                if '_links' in key:
                    for link in data[key]:
                        if link['rel'] == 'next':
                            full_url = str(link['href'])

            if full_url is None:
                break

        returnValue(result)


def api(url_path):

    @inlineCallbacks
    def api_caller(self, **kwargs):
        result = yield self.get_json(url_path, **kwargs)
        returnValue(result)

    return api_caller

