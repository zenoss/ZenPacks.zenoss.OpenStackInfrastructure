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
from ceilometerclient.v2.client import Client as ceilometerclient

class CeilometerAPIClient(object):

    def __init__(self, username, api_key, project_id,
                 auth_url, api_version, region_name):
        self._username = username
        self._api_key = api_key
        self._project_id = project_id
        self._auth_url = auth_url
        self._api_version = api_version
        self._region_name = region_name
        self._token = self._get_token()
        self._endpoint = self._get_endpoint()

        self._meters = []

        self._client = ceilometerclient(
            endpoint=self._endpoint,
            token=self._token
        )

        self._get_meters()

    def _get_token(self):
        # token expires in 3600 seconds
        token = ''
        if  len(self._username) > 0 and \
            len(self._api_key) > 0 and \
            len(self._project_id) > 0 and \
            len(self._auth_url) > 0:
            client = keystoneclient(
                username=self._username,
                password=self._api_key,
                tenant_name=self._project_id,
                auth_url=self._auth_url,
            )
            token = client.service_catalog.catalog['token']['id']
        return token

    def _get_endpoint(self):
        endpoint = ''
        if len(self._auth_url) > 0:
            endpoint = self._auth_url[:(self._auth_url.rindex(':'))] + ':8777'
        return endpoint

    def _get_meters(self):
        meterlist = self._client.meters.list()
        for m in meterlist:
            meter = {}
            meter['name'] = m.name
            meter['resource_id'] = m.resource_id
            meter['project_id'] = m.project_id
            meter['user_id'] = m.user_id
            self._meters.append(meter)

    def get_meternames(self):
        if len(self._meters) == 0:
            self._get_meters()

        return [meter['name'] for meter in self._meters if len(meter['name']) > 0]

    def get_statistics(self, meter_name = ''):
        if len(meter_name) == 0:
            return None
        meternames = self.get_meternames()
        if meter_name not in meternames:
            return None

        return self._client.statistics.list(meter_name)[0].to_dict()

    def get_meters(self):
        return [meter.to_dict() for meter in self._client.meters.list()]

    def get_alarms(self):
        return [alarm.to_dict() for alarm in self._client.alarms.list()]

    def get_resources(self):
        return [resource.to_dict() for resource in self._client.resources.list()]

    def get_samples(self):
        return [sample.to_dict() for sample in self._client.samples.list()]


#       query1 = [
#           {'field':'metadata.event_type',
#            'value':'compute.instance.exists',
#            'type':'',
#            'op':'',
#           },
#           {'field':'metadata.event_type',
#            'value':'compute.instance.delete.start',
#            'type':'',
#            'op':'',
#           },
#           {'field':'timestamp',
#            'value':'2013-07-03T13:34:17',
#            'type':'',
#            'op':'ge',
#           },
#       ]
#       query2 = [
#           {'field':'',
#            'value':'',
#            'type':'',
#            'op':'',
#           },
#       ]
#       ceiloclient.resources.list(query1)
#       data['meters-list'] = ceiloclient.meters.list()
#       data['events-list'] = ceiloclient.events.list()
#       data['alarms-list'] = ceiloclient.alarms.list()
#       data['resources-list'] = ceiloclient.resources.list()
#       data['samples-list'] = ceiloclient.samples.list()
#       pdb.set_trace()
#       data['statistics-list'] = ceiloclient.statistics.list()


