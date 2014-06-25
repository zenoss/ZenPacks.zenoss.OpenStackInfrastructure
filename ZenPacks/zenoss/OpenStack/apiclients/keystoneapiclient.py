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

from ZenPacks.zenoss.OpenStack.utils import add_local_lib_path
add_local_lib_path()

from keystoneclient.v2_0.client import Client as keystoneclient


class KeystoneAPIClient(object):

    def __init__(self, username, api_key, project_id,
                 auth_url, api_version):
        self._username = username
        self._api_key = api_key
        self._project_id = project_id
        self._auth_url = auth_url
        self._api_version = api_version
        # use keystone client v2 by default
        self._client = keystoneclient(
                username=self._username,
                password=self._api_key,
                tenant_name=self._project_id,
                auth_url=self._auth_url,
            )
        self._token = self._get_token()

    def _get_token(self):
        # token expires in 3600 seconds
        return self._client.service_catalog.catalog['token']['id']

    def get_endpoints(self):
        return self._client.endpoints.list()

    def get_roles(self):
        return self._client.roles.list()

    def get_services(self):
        return self._client.services.list()

    def get_tenants(self):
        return self._client.tenants.list()

    def get_users(self):
        return self._client.users.list()

