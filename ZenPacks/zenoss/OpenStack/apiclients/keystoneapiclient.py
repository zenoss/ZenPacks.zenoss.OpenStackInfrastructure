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
from Queue import Queue


import Globals
from twisted.internet.defer import inlineCallbacks, DeferredQueue
from twisted.internet import reactor, defer, threads

from ZenPacks.zenoss.OpenStack.utils import add_local_lib_path
add_local_lib_path()

from keystoneclient.v2_0.client import Client as keystoneclient
import logging
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
        # the time when a new token is obtained
        self.auth_token_epoch = 0
        self.token = {}              # token.keys(): [u'issued_at', u'expires', u'id', u'tenant']
        self.endpoints = {}
        self.regions = []

    def _get_data(self, result):
        if result.__str__().find('keystoneclient.v2_0.client.Client') > -1:
            self._client = result
            self.token = result.service_catalog.catalog['token']
        elif result.__str__().find('Token') > -1:
            self.token = result.token
        elif result.__str__().find('Endpoint') > -1:
            self.endpoints = result
        elif result.__str__().find('Role') > -1:
            self.roles = result
        elif result.__str__().find('Service') > -1:
            self.services = result
        elif result.__str__().find('Tenant') > -1:
            self.tenants = result
        elif result.__str__().find('User') > -1:
            self.users = result
        else:
            pass

    def _get_data_and_deferred(self, result, deferredName = ''):
        if result.__str__().find('keystoneclient.v2_0.client.Client') > -1:
            self._client = result
        elif result.__str__().find('Token') > -1:
            self.token = result.token
        if deferredName == 'endpoints':
            d = self._get_endpoints()
            d.addCallbacks(self._get_data, self._err_data)
        elif deferredName == 'roles':
            d = self._get_roles()
            d.addCallbacks(self._get_data, self._err_data)
        elif deferredName == 'services':
            d = self._get_services()
            d.addCallbacks(self._get_data, self._err_data)
        elif deferredName == 'tenants':
            d = self._get_tenants()
            d.addCallbacks(self._get_data, self._err_data)
        elif deferredName == 'users':
            d = self._get_users()
            d.addCallbacks(self._get_data, self._err_data)

    def _err_data(self, failure):
        log.error("Keystone API Client _err_data(): %s" % failure)

    # a token is valid for 60 minutes.
    # renew token if used for >= 55 minutes
    def _is_expiring(self):
        threshold = TOKEN_TTL - TIME_TO_RENEW
        if (time.time() - self.auth_token_epoch) >= threshold:
            return True
        return False

    @inlineCallbacks
    def _get_client(self):
        c = None
        try:
            c = yield keystoneclient(
                        username=self._username,
                        password=self._api_key,
                        tenant_name=self._project_id,
                        auth_url=self._auth_url,
                    )
        except Exception as ex:
            log.error("Keystone API Client _get_client() error: %s" % ex.message)

        self.auth_token_epoch = time.time()
        defer.returnValue(c)

    @inlineCallbacks
    def _authenticate(self):
        token_ref = None
        try:
            token_ref = yield self._client.tokens.authenticate(
                        username=self._username,
                        tenant_name=self._project_id,
                        password=self._api_key,
                        token=self.token,
                )
        except Exception as ex:
            log.error("Keystone API Client _get_client() error: %s" % ex.message)

        self.auth_token_epoch = time.time()
        defer.returnValue(token_ref)

    def get_token(self):
        if self._client is None:
            d = self._get_client()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)
        elif self._is_expiring():
            d = self._authenticate()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)

        return self.token['id']

    @inlineCallbacks
    def _get_endpoints(self):
        ep = {}
        try:
            ep = yield self._client.endpoints.list()
        except Exception as ex:
            log.error("Keystone API Client _get_endpoints() error: %s" % ex.message)

        defer.returnValue(ep)

    def get_endpoints(self):
        if self._client is None:
            d = self._get_client()
            d.addCallback(self._get_data_and_deferred, 'endpoints')
            d.addErrback(self._err_data)
        elif self._is_expiring():
            d = self._authenticate()
            d.addCallback(self._get_data_and_deferred, 'endpoints')
            d.addErrback(self._err_data)
        else:
            d = self._get_endpoints()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)

        return self.endpoints
        
    def get_regions(self):
        endpoints = self.get_endpoints()
        self.regions = []
        for ep in endpoints:
            if len(self.regions) == 0 or self.regions[0].find(ep.region) < 0:
                self.regions.append(ep.region)
        return [{'key': c, 'label': c} for c in sorted(self.regions)]

    @inlineCallbacks
    def _get_roles(self):
        roles = []
        try:
            roles = yield self._client.roles.list()
        except Exception as ex:
            log.error("Keystone API Client get_roles() error: %s" % ex.message)

        defer.returnValue(roles)

    def get_roles(self):
        if self._client is None:
            d = self._get_client()
            d.addCallback(self._get_data_and_deferred, 'roles')
            d.addErrback(self._err_data)
        elif self._is_expiring():
            d = self._authenticate()
            d.addCallback(self._get_data_and_deferred, 'roles')
            d.addErrback(self._err_data)
        else:
            d = self._get_roles()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)

        return self.roles

    @inlineCallbacks
    def _get_services(self):
        services = []
        try:
            services = yield self._client.services.list()
        except Exception as ex:
            log.error("Keystone API Client get_services() error: %s" % ex.message)

        defer.returnValue(services)

    def get_services(self):
        if self._client is None:
            d = self._get_client()
            d.addCallback(self._get_data_and_deferred, 'services')
            d.addErrback(self._err_data)
        elif self._is_expiring():
            d = self._authenticate()
            d.addCallback(self._get_data_and_deferred, 'services')
            d.addErrback(self._err_data)
        else:
            d = self._get_services()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)

        return self.services

    @inlineCallbacks
    def _get_tenants(self):
        tenants = []
        try:
            tenants = yield self._client.tenants.list()
        except Exception as ex:
            log.error("Keystone API Client get_tenants() error: %s" % ex.message)

        defer.returnValue(tenants)

    def get_tenants(self):
        if self._client is None:
            d = self._get_client()
            d.addCallback(self._get_data_and_deferred, 'tenants')
            d.addErrback(self._err_data)
        elif self._is_expiring():
            d = self._authenticate()
            d.addCallback(self._get_data_and_deferred, 'tenants')
            d.addErrback(self._err_data)
        else:
            d = self._get_tenants()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)

        return self.tenants

    def get_ceilometerurl(self, region_name):
        if self._client is None:
            d = self._get_client()
            d.addCallback(self._get_data_and_deferred, 'users')
            d.addErrback(self._err_data)
        elif self._is_expiring():
            d = self._authenticate()
            d.addCallback(self._get_data_and_deferred, 'users')
            d.addErrback(self._err_data)

        endpoints = self._client.service_catalog.get_endpoints('metering')
        if 'metering' in endpoints.keys():
             for endpoint in endpoints['metering']:
                 if endpoint.has_key('region') and \
                    endpoint['region'] == region_name and \
                    endpoint.has_key('publicURL'):
                     return endpoint['publicURL']
        return ""

    @inlineCallbacks
    def _get_users(self):
        users = []
        try:
            users = yield self._client.users.list()
        except Exception as ex:
            log.error("Keystone API Client get_users() error: %s" % ex.message)

        defer.returnValue(users)

    def get_users(self):
        if self._client is None:
            d = self._get_client()
            d.addCallback(self._get_data_and_deferred, 'users')
            d.addErrback(self._err_data)
        elif self._is_expiring():
            d = self._authenticate()
            d.addCallback(self._get_data_and_deferred, 'users')
            d.addErrback(self._err_data)
        else:
            d = self._get_users()
            d.addCallback(self._get_data)
            d.addErrback(self._err_data)

        return self.users

