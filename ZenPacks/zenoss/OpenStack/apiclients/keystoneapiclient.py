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

'''
OpenStack Keystone API client.
'''

import time
from datetime import datetime


import Globals
from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor, defer, threads

from ZenPacks.zenoss.OpenStack.utils import add_local_lib_path
add_local_lib_path()

from keystoneclient.v2_0.client import Client as keystoneclient
import logging
log = logging.getLogger()
log = logging.getLogger('zen.OpenStackAPIClient')

TOKEN_TTL = 3600
TIME_TO_RENEW = 300

class KeystoneAPIClient(object):

    def __init__(self, url, username, api_key, project_id):
        self._username = username
        self._api_key = api_key
        self._project_id = project_id
        self._auth_url = url
        # use keystone client v2 by default
        self._client = None
        self.auth_token_epoch = 0

    def _get_data(self, result):
        self._client = result

    def _err_data(self, failure):
        log.error("Keystone API Client _err_data(): %s" % failure)

    # a token is valid for 60 minutes.
    # renew token if used for >= 55 minutes
    def _is_expiring(self):
        threshold = TOKEN_TTL - TIME_TO_RENEW
        if (time.time() - self.auth_token_epoch) >= threshold or \
            self._client is None:
            return True
        return False

    def __get_client(self):
        return  keystoneclient(
                username=self._username,
                password=self._api_key,
                tenant_name=self._project_id,
                auth_url=self._auth_url,
            )

    @inlineCallbacks
    def _get_client(self):
        try:
            c = yield self.__get_client()
        except Exception as ex:
            log.error("Keystone API Client _get_client() error: %s" % ex.message)

        self.auth_token_epoch = time.time()
        defer.returnValue(c)

    def _get_token(self):
        if self._is_expiring():
            d = self._get_client()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)

        return self._client.service_catalog.catalog['token']['id']

    @inlineCallbacks
    def get_token(self):
        result = []
        try:
            result = yield self._get_token()
        except Exception as ex:
            log.error("Keystone API Client get_token() error: %s" % ex.message)

        defer.returnValue(result)

    def _get_endpoints(self):
        if self._is_expiring():
            d = self._get_client()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)

        return self._client.endpoints.list()

    @inlineCallbacks
    def get_endpoints(self):
        result = []
        try:
            result = yield self._get_endpoints()
        except Exception as ex:
            log.error("Keystone API Client get_endpoints() error: %s" % ex.message)

        defer.returnValue(result)

    def _get_regions(self):
        if self._is_expiring():
            d = self._get_client()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)

        regions = set()
        endpoints = self._client.service_catalog.get_endpoints()
        for (service, service_endpoints) in endpoints.iteritems():
            for endpoint in service_endpoints:
                regions.add(endpoint['region'])

        return [{'key': c, 'label': c} for c in sorted(regions)]

    @inlineCallbacks
    def get_regions(self):
        result = []
        try:
            result = yield self._get_regions()
        except Exception as ex:
            log.error("Keystone API Client get_regions() error: %s" % ex.message)

        defer.returnValue(result)

    def _get_roles(self):
        if self._is_expiring():
            d = self._get_client()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)

        return self._client.roles.list()

    @inlineCallbacks
    def get_roles(self):
        result = []
        try:
            result = yield self._get_roles()
        except Exception as ex:
            log.error("Keystone API Client get_roles() error: %s" % ex.message)

        defer.returnValue(result)

    def _get_services(self):
        if self._is_expiring():
            d = self._get_client()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)

        return self._client.services.list()

    @inlineCallbacks
    def get_services(self):
        result = []
        try:
            result = yield self._get_services()
        except Exception as ex:
            log.error("Keystone API Client get_services() error: %s" % ex.message)

        defer.returnValue(result)

    def _get_tenants(self):
        if self._is_expiring():
            d = self._get_client()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)

        return self._client.tenants.list()

    @inlineCallbacks
    def get_tenants(self):
        result = []
        try:
            result = yield self._get_tenants()
        except Exception as ex:
            log.error("Keystone API Client get_tenants() error: %s" % ex.message)

        defer.returnValue(result)

    def _get_ceilometerurl(self, region_name):
        if self._is_expiring():
            d = self._get_client()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)


        endpoints = self._client.service_catalog.get_endpoints('metering')
        if 'metering' in endpoints:
             for endpoint in endpoints['metering']:
                 if endpoint.has_key('region') and \
                    endpoint['region'] == region_name and \
                    endpoint.has_key('publicURL'):
                     return endpoint['publicURL']
        return ""

    @inlineCallbacks
    def get_ceilometerurl(self, region_name = ""):
        result = []
        if len(region_name) > 0:
            try:
                result = yield self._get_ceilometerurl(region_name)
            except Exception as ex:
                log.error("Keystone API Client get_ceilometerurl() error: %s" % ex.message)

        defer.returnValue(result)

    def _get_users(self):
        if self._is_expiring():
            d = self._get_client()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)

        return self._client.users.list()

    @inlineCallbacks
    def get_users(self):
        result = []
        try:
            result = yield self._get_users()
        except Exception as ex:
            log.error("Keystone API Client get_users() error: %s" % ex.message)

        defer.returnValue(result)

