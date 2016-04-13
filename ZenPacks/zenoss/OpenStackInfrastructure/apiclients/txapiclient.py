###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2016, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

import httplib
import urllib
import json
import collections

import Globals
from ZenPacks.zenoss.OpenStackInfrastructure.utils import add_local_lib_path
from Products.ZenUtils.Utils import unused
add_local_lib_path()
unused(Globals)

from twisted.web import client as txwebclient
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.error import Error
from twisted.internet import reactor

import logging
log = logging.getLogger('zen.OpenStack.txapiclient')

Request = collections.namedtuple(
    'Request', ['url', 'method', 'agent', 'headers', 'postdata'])


def getPageAndHeaders(url, contextFactory=None, *args, **kwargs):
    """Return deferred with a (body, headers) success result.

    This is a small modification to twisted.web.client.getPage that
    allows the caller access to the response headers.

    """
    factory = txwebclient._makeGetterFactory(
        url,
        txwebclient.HTTPClientFactory,
        contextFactory=contextFactory,
        *args, **kwargs)

    return factory.deferred.addCallback(
        lambda page: (page, factory.response_headers))


class APIClient(object):

    """Twisted asynchronous API client."""

    def __init__(self, username, password, auth_url, project_id, is_admin=False):
        """Create Keystone API client."""
        self.username = username
        self.password = password
        self.auth_url = auth_url
        self.project_id = project_id
        self.is_admin = is_admin

        self.user_agent = None
        self._token = None
        self._apis = {}
        self._serviceCatalog = None
        self._keystone_url = None
        self._nova_url = None
        self._neutron_url = None
        self._ceilometer_url = None
        self._cinder_url = None
        self._cinderv2_url = None
        self._glance_url = None

    @property
    def keystone_endpoints(self):
        if '/v2' in self.auth_url:
            self._admin_only()
        self.user_agent = 'zenoss-keystoneclient'
        return self._apis.setdefault('keystone_endpoints', API(self, '/endpoints'))

    @property
    def keystone_tenants(self):
        if '/v2' in self.auth_url:
            self._admin_only()
        self.user_agent = 'zenoss-keystoneclient'
        return self._apis.setdefault('keystone_tenants', API(self, '/tenants'))

    @property
    def keystone_users(self):
        if '/v2' in self.auth_url:
            self._admin_only()
        self.user_agent = 'zenoss-keystoneclient'
        return self._apis.setdefault('keystone_users', API(self, '/users'))

    @property
    def keystone_roles(self):
        if '/v2' in self.auth_url:
            self._admin_only()
        self.user_agent = 'zenoss-keystoneclient'
        return self._apis.setdefault('keystone_roles', API(self, '/OS-KSADM/roles'))

    @property
    def keystone_services(self):
        if '/v2' in self.auth_url:
            self._admin_only()
        self.user_agent = 'zenoss-keystoneclient'
        return self._apis.setdefault('keystone_services', API(self, '/OS-KSADM/services'))

    def _admin_only(self, api_method='GET'):
        # for Keystone only
        if self.is_admin is False:
            raise UnauthorizedError("'%s' is only available in the Identity admin API v2.0" % api_method)

    @property
    def nova_avzones(self):
        self.user_agent = 'zenoss-novaclient'
        return self._apis.setdefault('nova_avzones', API(self, '/os-availability-zone/detail'))

    @property
    def nova_flavors(self):
        """Return entry-point to the API."""
        self.user_agent = 'zenoss-novaclient'
        return self._apis.setdefault('nova_flavors', API(self, '/flavors/detail'))

    @property
    def nova_hosts(self):
        self.user_agent = 'zenoss-novaclient'
        return self._apis.setdefault('nova_hosts', API(self, '/os-hosts'))

    @property
    def nova_hypervisors(self):
        self.user_agent = 'zenoss-novaclient'
        return self._apis.setdefault('nova_hypervisors', API(self, '/os-hypervisors'))

    @property
    def nova_hypervisorsdetailed(self):
        self.user_agent = 'zenoss-novaclient'
        return self._apis.setdefault('nova_hypervisors', API(self, '/os-hypervisors/detail'))

    @property
    def nova_hypervisorstats(self):
        self.user_agent = 'zenoss-novaclient'
        return self._apis.setdefault('nova_hypervisorstats', API(self, '/os-hypervisors/statistics'))

    @property
    def nova_hypervisor_detail_id(self):
        self.user_agent = 'zenoss-novaclient'
        return self._apis.setdefault('nova_hypervisordetail', API(self, '/os-hypervisors'))

    @property
    def nova_images(self):
        self.user_agent = 'zenoss-novaclient'
        return self._apis.setdefault('nova_images', API(self, '/images/detail'))

    @property
    def nova_servers(self):
        self.user_agent = 'zenoss-novaclient'
        return self._apis.setdefault('nova_servers', API(self, '/servers/detail?all_tenants=1'))

    @property
    def nova_services(self):
        self.user_agent = 'zenoss-novaclient'
        return self._apis.setdefault('nova_services', API(self, '/os-services'))

    @property
    def neutron_agents(self):
        self.user_agent = 'zenoss-neutronclient'
        return self._apis.setdefault('neutron_agents', API(self, '/v2.0/agents.json'))

    @property
    def neutron_floatingips(self):
        self.user_agent = 'zenoss-neutronclient'
        return self._apis.setdefault('neutron_floatingips', API(self, '/v2.0/floatingips.json'))

    @property
    def neutron_networks(self):
        self.user_agent = 'zenoss-neutronclient'
        return self._apis.setdefault('neutron_networks', API(self, '/v2.0/networks.json'))

    @property
    def neutron_ports(self):
        self.user_agent = 'zenoss-neutronclient'
        return self._apis.setdefault('neutron_ports', API(self, '/v2.0/ports.json'))

    @property
    def neutron_routers(self):
        self.user_agent = 'zenoss-neutronclient'
        return self._apis.setdefault('neutron_routers', API(self, '/v2.0/routers.json'))

    @property
    def neutron_security_groups(self):
        self.user_agent = 'zenoss-neutronclient'
        return self._apis.setdefault('neutron_security_groups', API(self, '/v2.0/security-groups.json'))

    @property
    def neutron_subnets(self):
        self.user_agent = 'zenoss-neutronclient'
        return self._apis.setdefault('neutron_subnets', API(self, '/v2.0/subnets.json'))

    @property
    def cinder_volumes(self):
        self.user_agent = 'zenoss-cinderv2client'
        return self._apis.setdefault('cinder_volumes', API(self, '/volumes/detail?all_tenants=1'))

    @property
    def cinder_volumetypes(self):
        self.user_agent = 'zenoss-cinderv2client'
        return self._apis.setdefault('cinder_volumetypes', API(self, '/types'))

    @property
    def cinder_volumebackups(self):
        self.user_agent = 'zenoss-cinderv2client'
        return self._apis.setdefault('cinder_volumebackups', API(self, '/backups/detail?all_tenants=1'))

    @property
    def cinder_volumesnapshots(self):
        self.user_agent = 'zenoss-cinderv2client'
        return self._apis.setdefault('cinderv_olumesnapshots', API(self, '/snapshots/detail?all_tenants=1'))

    @property
    def cinder_pools(self):
        self.user_agent = 'zenoss-cinderv2client'
        return self._apis.setdefault('cinder_pools', API(self, '/scheduler-stats/get_pools?detail=True'))

    @property
    def cinder_quotas(self):
        self.user_agent = 'zenoss-cinderv2client'
        return self._apis.setdefault('cinder_quotas', API(self, '/cinderquotas'))

    @property
    def cinder_services(self):
        self.user_agent = 'zenoss-cinderv2client'
        return self._apis.setdefault('cinder_services', API(self, '/os-services'))

    @property
    def ceilometer_resources(self):
        self.user_agent = 'zenoss-ceilometerclient'
        return self._apis.setdefault('ceilometer_resources', API(self, '/v2/resources'))

    @property
    def ceilometer_meters(self):
        self.user_agent = 'zenoss-ceilometerclient'
        return self._apis.setdefault('ceilometer_meters', API(self, '/v2/meters'))

    @property
    def ceilometer_statistics(self):
        self.user_agent = 'zenoss-ceilometerclient'
        return self._apis.setdefault('ceilometer_statistics', API(self, '/v2/meters/'))

    @property
    def ceilometer_samples(self):
        self.user_agent = 'zenoss-ceilometerclient'
        return self._apis.setdefault('ceilometer_samples', API(self, '/v2/samples'))

    @property
    def ceilometer_events(self):
        self.user_agent = 'zenoss-ceilometerclient'
        return self._apis.setdefault('ceilometer_events', API(self, '/v2/events'))

    @property
    def ceilometer_alarms(self):
        self.user_agent = 'zenoss-ceilometerclient'
        return self._apis.setdefault('ceilometer_alarms', API(self, '/v2/alarms'))

    #@property
    #def ceilometer_querysamples(self):
    #    self.user_agent = 'zenoss-ceilometerclient'
    #    return self._apis.setdefault('ceilometer_querysamples', API(self, '/v2/query/samples'))

    @inlineCallbacks
    def login(self):
        """Login to Keystone.

        Client normally handles logins transparently. So it's not
        recommended that login be explicitely called for most usages.

        """
        if self._token:
            returnValue(None)

        body = {}
        body["auth"] = {}
        body["auth"]["tenantName"] = self.project_id
        body["auth"]["passwordCredentials"] = {}
        body["auth"]["passwordCredentials"]["username"] = self.username
        body["auth"]["passwordCredentials"]["password"] = self.password

        r = yield self.direct_api_call('/tokens', data=body)

        if 'access' in r:
            if 'token' in r['access'] and 'id' in r['access']['token']:
                self._token = r['access']['token']['id'].encode(
                    'ascii', 'ignore')
            if 'serviceCatalog' in r['access']:
                self._serviceCatalog = r['access']['serviceCatalog']

        # collect URLs all in one call
        for sc in r['access']['serviceCatalog']:
            if sc['type'] == 'identity' and sc['name'] == 'keystone':
                self._keystone_url = sc['endpoints'][0]['adminURL'].encode(
                    'ascii', 'ignore')
            elif sc['type'] == 'compute' and sc['name'] == 'nova':
                self._nova_url = sc['endpoints'][0]['publicURL'].encode(
                    'ascii', 'ignore')
            elif sc['type'] == 'network':
                self._neutron_url = sc['endpoints'][0]['publicURL'].encode(
                    'ascii', 'ignore')
            elif sc['type'] == 'metering' and sc['name'] == 'ceilometer':
                self._ceilometer_url = sc['endpoints'][0]['publicURL'].encode(
                    'ascii', 'ignore')
            elif sc['type'] == 'volume' and sc['name'] == 'cinder':
                self._cinder_url = sc['endpoints'][0]['publicURL'].encode(
                    'ascii', 'ignore')
            elif sc['type'] == 'volumev2' and sc['name'] == 'cinderv2':
                self._cinderv2_url = sc['endpoints'][0]['publicURL'].encode(
                    'ascii', 'ignore')
            elif sc['type'] == 'image' and sc['name'] == 'glance':
                self._glance_url = sc['endpoints'][0]['publicURL'].encode(
                    'ascii', 'ignore')

        returnValue(r)

    @inlineCallbacks
    def serviceCatalog(self):
        if self._serviceCatalog is None:
            yield self.login()

        returnValue(self._serviceCatalog)

    @inlineCallbacks
    def api_call(self, path, data=None, params=None, **kwargs):
        """Wrap direct_api_call for convenience purposes.

        Will authenticate prior to making an API call if necessary, and
        reauthenticate and retry the API call if an unauthorized error
        is encountered during the first API call attempt.

        """
        if not self._token:
            yield self.login()
        else:
            log.debug('api_call(). Existing token: %s' % self._token)

        try:
            r = yield self.direct_api_call(
                path, data=data, params=params, **kwargs)
        except UnauthorizedError:
            # Could be caused by expired token. Try to login.
            yield self.login()

            # Then try the call again.
            r = yield self.direct_api_call(
                path, data=data, params=params, **kwargs)

        returnValue(r)

    @inlineCallbacks
    def direct_api_call(self, path, data=None, params=None, **kwargs):
        """Return result of API call request.

        Typically this is not meant to be called directly. It is meant
        to be used through the api property as follows:

            client.keystoneendpoints({'data': 'value'})

        However, it can be used directly as follows:

            client.api_call('/endpoints', data={'data': 'value'})

        """
        request = self._get_request(path, data=data, params=params, **kwargs)
        if hasattr(log, 'debug'):
            log.debug("Request URL: %s" % request.url)
        else:
            log.info("Request URL: %s" % request.url)

        try:
            response = yield getPageAndHeaders(
                request.url,
                method=request.method,
                agent=request.agent,
                headers=request.headers,
                postdata=request.postdata)

        except Error as e:
            # e.status == '200', e.message == 'OK' but still ends up here?
            # maybe response body is too long?
            if e.status == '200' and e.message == 'OK':
                try:
                    data = json.loads(e.response)
                    returnValue(data)
                except ValueError as e:
                    text = 'direct_api_call(). path: ' + path + '. ' + e.message + ' of response body.'
                    raise APIClientError(text)

            status = int(e.status)
            text = 'direct_api_call(). path: ' + path + '. ' + e.response.replace('\n\n', '.').strip()

            if status == httplib.UNAUTHORIZED:
                raise UnauthorizedError(text + ". (check username & password)")
            elif status == httplib.BAD_REQUEST:
                raise BadRequestError(text + ". (check headers and/or data)")
            elif status == httplib.NOT_FOUND:
                component = path.split('/')[-1].replace('.json', '')
                if component in ('subnets', 'ports', 'networks'):
                    log.info('No data for {0} '.format(component))
                    returnValue(json.loads('{"%s": []}' % component))
                raise NotFoundError(text + ' url used: ' + request.url)

            raise APIClientError(text)

        except Exception as e:
            raise APIClientError(e)

        returnValue(json.loads(response[0]))

    def _get_request(self, path, data=None,  params=None, **kwargs):
        # Process data. Supports a variety of input types.
        # /tokens uses POST, auth_url should be public url;
        # all others use GET, auth_url should be a specific one
        postdata = json.dumps(data) if data else None

        method = 'POST' if postdata else 'GET'

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': self.user_agent,
            }

        if self._token:
            headers['X-Auth-Token'] = self._token

        auth_url = self.auth_url.strip()    # always user auth_url for POST
        if method == 'GET':
            if 'keystone' in self.user_agent and self._keystone_url is not None:
                auth_url = self._keystone_url
            elif 'nova' in self.user_agent and self._nova_url is not None:
                auth_url = self._nova_url
            elif 'neutron' in self.user_agent and self._neutron_url is not None:
                auth_url = self._neutron_url
            elif 'cinderv2' in self.user_agent and self._cinderv2_url is not None:
                auth_url = self._cinderv2_url
            elif 'cinder' in self.user_agent and self._cinder_url is not None:
                auth_url = self._cinder_url
            elif 'glance' in self.user_agent and self._glance_url is not None:
                auth_url = self._glance_url
            elif 'ceilometer' in self.user_agent and self._ceilometer_url is not None:
                auth_url = self._ceilometer_url

        return Request(
            auth_url + path,
            method=method,
            agent=self.user_agent,
            headers=headers,
            postdata=postdata)

    @inlineCallbacks
    def nova_url(self):
        if not self._nova_url:
            yield self.login()
        returnValue(self._nova_url)

    @inlineCallbacks
    def ceilometer_url(self):
        if not self._ceilometer_url:
            yield self.login()
        returnValue(self._ceilometer_url)


class API(object):

    """Wrapper for each element of an API path including the leaf.  """

    def __init__(self, client, path=''):
        self.client = client
        self.path = path
        self._apis = {}

    def __getattr__(self, name):
        if name not in self._apis:
            self._apis[name] = API(self.client, '/'.join((self.path, name)))

        return self._apis[name]

    def __getitem__(self, name):
        return getattr(self, name)

    def __call__(self, data=None, params=None, **kwargs):
        # update url based on kwargs
        if '/flavors/detail' in self.path and 'is_public' in kwargs:
            if '?is_public=' in self.path:
                self.path = self.path[:self.path.index('?is_public=')]
            self.path = self.path + '?is_public=%s' % kwargs['is_public']

        elif '/os-hypervisors' in self.path and \
                'hypervisor_match' in kwargs and 'servers' in kwargs:
            target = 'servers' if kwargs['servers'] else 'search'
            self.path = '/os-hypervisors/%s/%s' % \
                        (urllib.quote(kwargs['hypervisor_match'], safe=''),
                         target)

        elif '/os-hypervisors' in self.path and \
                        'hypervisor_id' in kwargs:
            self.path = '/os-hypervisors/%s' % kwargs['hypervisor_id']

        elif '/cinderquotas' in self.path:
            self.path = '/os-quota-sets/%s?usage=%s' % (kwargs['tenant'], kwargs['usage'])

        # append meter name and query for ceilometer statistics
        elif '/v2/meters/' in self.path and 'meter_name' in kwargs and 'queries' in kwargs:
            self.path = self.path[:self.path.index('/v2/meters/') + len('/v2/meters/')]
            self.path = self.path + kwargs['meter_name'] + '/statistics'

        # append query for ceilometer samples
        elif '/v2/samples' in self.path and 'queries' in kwargs:
            self.path = self.path[:self.path.index('/v2/samples') + len('/v2/samples')]

        # append query for ceilometer events
        elif '/v2/events' in self.path and 'queries' in kwargs:
            self.path = self.path[:self.path.index('/v2/events') + len('/v2/events')]

        # append query for ceilometer alarms
        elif '/v2/alarms' in self.path and 'queries' in kwargs:
            self.path = self.path[:self.path.index('/v2/alarms') + len('/v2/alarms')]

        # if there are query entries, add them to the path
        if 'queries' in kwargs:
            for query in kwargs['queries']:
                self.path += '?q.field=%s&q.op=%s&q.type=%s&q.value=%s' % \
                        (query.get('field',''), query.get('op',''),
                         query.get('type',''), query.get('value',''))

        return self.client.api_call(
            self.path.encode('ascii', 'ignore'), data=data, params=params, **kwargs)


class APIClientError(Exception):
    """Parent class of all exceptions raised by api clients."""
    pass


class BadRequestError(APIClientError):
    """Wrapper for HTTP 400 Bad Request error."""
    pass


class UnauthorizedError(APIClientError):
    """Wrapper for HTTP 401 Unauthorized error."""
    pass


class NotFoundError(APIClientError):
    """Wrapper for HTTP 400 Bad Request error."""
    pass


@inlineCallbacks
def main():
    import pprint

    client = APIClient('admin', 'zenoss', 'http://10.87.209.30:5000/v2.0', 'admin', True)
#    client = APIClient('admin', 'password', 'http://192.168.56.122:5000/v2.0', 'admin', True)

    # Keystone
    tenants = {}
    try:
        endpoints = yield client.keystone_endpoints()
        tenants = yield client.keystone_tenants()
        users = yield client.keystone_users()
        roles = yield client.keystone_roles()
        services = yield client.keystone_services()
    except (BadRequestError, UnauthorizedError, NotFoundError, APIClientError) as e:
        pprint.pprint(e.message)
    else:
        pprint.pprint(endpoints)
        pprint.pprint(tenants)
        pprint.pprint(users)
        pprint.pprint(roles)
        pprint.pprint(services)

    # Nova
    try:
        avzones = yield client.nova_avzones()
        public_flavors = yield client.nova_flavors(is_public=True)
        private_flavors = yield client.nova_flavors(is_public=False)
        hosts = yield client.nova_hosts()
        hypervisors = yield client.nova_hypervisors(hypervisor_match='%', servers=True)
        hypervisorStats = yield client.nova_hypervisorstats()
        hypervisor_1 = yield client.nova_hypervisor_detail_id(hypervisor_id='1')
        images = yield client.nova_images(detailed=True)
        novaservices = yield client.nova_services()
        servers = yield client.nova_servers(detailed=True, search_opts={'all_tenants': 1})
    except (BadRequestError, UnauthorizedError, NotFoundError, APIClientError) as e:
        pprint.pprint(e.message)
    else:
        pprint.pprint(avzones)
        pprint.pprint(public_flavors)
        pprint.pprint(private_flavors)
        pprint.pprint(hosts)
        pprint.pprint(hypervisors)
        pprint.pprint(hypervisorStats)
        pprint.pprint(hypervisor_1)
        pprint.pprint(images)
        pprint.pprint(novaservices)
        pprint.pprint(servers)

    # Neutron
    try:
        neutronagents = yield client.neutron_agents()
        floatingips = yield client.neutron_floatingips()
        networks = yield client.neutron_networks()
        ports = yield client.neutron_ports()
        routers = yield client.neutron_routers()
        security_groups = yield client.neutron_security_groups()
        subnets = yield client.neutron_subnets()
    except (BadRequestError, UnauthorizedError, NotFoundError, APIClientError) as e:
        pprint.pprint(e.message)
    else:
        pprint.pprint(neutronagents)
        pprint.pprint(floatingips)
        pprint.pprint(networks)
        pprint.pprint(ports)
        pprint.pprint(routers)
        pprint.pprint(security_groups)
        pprint.pprint(subnets)

    # Cinder
    try:
        volumes = yield client.cinder_volumes()
        volumetypes = yield client.cinder_volumetypes()
        volumebackups = yield client.cinder_volumebackups()
        volumesnapshots = yield client.cinder_volumesnapshots()
        cinderservices = yield client.cinder_services(detailed=True)
        cinderpools = yield client.cinder_pools(detailed=True)
    except (BadRequestError, UnauthorizedError, NotFoundError, APIClientError) as e:
        pprint.pprint(e.message)
    else:
        pprint.pprint(volumes)
        pprint.pprint(volumetypes)
        pprint.pprint(volumebackups)
        pprint.pprint(volumesnapshots)
        pprint.pprint(cinderservices)
        pprint.pprint(cinderpools)

    if tenants and 'tenants' in tenants:
        for tenant in tenants['tenants']:
            try:
                quotas = yield client.cinder_quotas(tenant=tenant['id'].encode('ascii', 'ignore'), usage=False)
            except (BadRequestError, UnauthorizedError, NotFoundError) as e:
                pprint.pprint(e.message)
            else:
                pprint.pprint(quotas)
    try:
        avzones = yield client.nova_avzones()
        public_flavors = yield client.nova_flavors(is_public=True)
        private_flavors = yield client.nova_flavors(is_public=False)
        hosts = yield client.nova_hosts()
        hypervisors = yield client.nova_hypervisors(hypervisor_match='%', servers=True)
        images = yield client.nova_images(detailed=True)
        novaservices = yield client.nova_services()
        servers = yield client.nova_servers(detailed=True, search_opts={'all_tenants': 1})
    except (BadRequestError, UnauthorizedError, NotFoundError, APIClientError) as e:
        pprint.pprint(e.message)
    else:
        pprint.pprint(avzones)
        pprint.pprint(public_flavors)
        pprint.pprint(private_flavors)
        pprint.pprint(hosts)
        pprint.pprint(hypervisors)
        pprint.pprint(images)
        pprint.pprint(novaservices)
        pprint.pprint(servers)

    # Neutron
    try:
        neutronagents = yield client.neutron_agents()
        floatingips = yield client.neutron_floatingips()
        networks = yield client.neutron_networks()
        ports = yield client.neutron_ports()
        routers = yield client.neutron_routers()
        security_groups = yield client.neutron_security_groups()
        subnets = yield client.neutron_subnets()
    except (BadRequestError, UnauthorizedError, NotFoundError, APIClientError) as e:
        pprint.pprint(e.message)
    else:
        pprint.pprint(neutronagents)
        pprint.pprint(floatingips)
        pprint.pprint(networks)
        pprint.pprint(ports)
        pprint.pprint(routers)
        pprint.pprint(security_groups)
        pprint.pprint(subnets)

    # Cinder
    try:
        volumes = yield client.cinder_volumes()
        volumetypes = yield client.cinder_volumetypes()
        volumebackups = yield client.cinder_volumebackups()
        volumesnapshots = yield client.cinder_volumesnapshots()
        cinderservices = yield client.cinder_services(detailed=True)
        cinderpools = yield client.cinder_pools(detailed=True)
    except (BadRequestError, UnauthorizedError, NotFoundError, APIClientError) as e:
        pprint.pprint(e.message)
    else:
        pprint.pprint(volumes)
        pprint.pprint(volumetypes)
        pprint.pprint(volumebackups)
        pprint.pprint(volumesnapshots)
        pprint.pprint(cinderservices)
        pprint.pprint(cinderpools)

    if tenants and 'tenants' in tenants:
        for tenant in tenants['tenants']:
            try:
                quotas = yield client.cinder_quotas(tenant=tenant['id'].encode('ascii', 'ignore'), usage=False)
            except (BadRequestError, UnauthorizedError, NotFoundError) as e:
                pprint.pprint(e.message)
            else:
                pprint.pprint(quotas)

    # Neutron
    try:
        neutronagents = yield client.neutron_agents()
        floatingips = yield client.neutron_floatingips()
        networks = yield client.neutron_networks()
        ports = yield client.neutron_ports()
        routers = yield client.neutron_routers()
        security_groups = yield client.neutron_security_groups()
        subnets = yield client.neutron_subnets()
    except (BadRequestError, UnauthorizedError, NotFoundError, APIClientError) as e:
        pprint.pprint(e.message)
    else:
        pprint.pprint(neutronagents)
        pprint.pprint(floatingips)
        pprint.pprint(networks)
        pprint.pprint(ports)
        pprint.pprint(routers)
        pprint.pprint(security_groups)
        pprint.pprint(subnets)

    # Cinder
    try:
        volumes = yield client.cinder_volumes()
        volumetypes = yield client.cinder_volumetypes()
        volumebackups = yield client.cinder_volumebackups()
        volumesnapshots = yield client.cinder_volumesnapshots()
        cinderservices = yield client.cinder_services(detailed=True)
        cinderpools = yield client.cinder_pools(detailed=True)
    except (BadRequestError, UnauthorizedError, NotFoundError, APIClientError) as e:
        pprint.pprint(e.message)
    else:
        pprint.pprint(volumes)
        pprint.pprint(volumetypes)
        pprint.pprint(volumebackups)
        pprint.pprint(volumesnapshots)
        pprint.pprint(cinderservices)
        pprint.pprint(cinderpools)

    if tenants and 'tenants' in tenants:
        for tenant in tenants['tenants']:
            try:
                quotas = yield client.cinder_quotas(tenant=tenant['id'].encode('ascii', 'ignore'), usage=False)
            except (BadRequestError, UnauthorizedError, NotFoundError) as e:
                pprint.pprint(e.message)
            else:
                pprint.pprint(quotas)

    # Ceilometer
    try:
        resources = yield client.ceilometer_resources()
        meters = yield client.ceilometer_meters()
        for meter in meters:
            query = dict(field='resource_id', op='eq', value=meter['resource_id'], type='string')
            stats = yield client.ceilometer_statistics(meter_name=meter['name'], queries=[query])
            print 'meter: %s, stats: %s\n\n' % (meter['name'], str(stats))

            # use with care!
            #Ceilometer samples could spill out an enormous amount of data!
            # samples = yield client.ceilometer_samples(queries=[query])
            # print 'meter: %s, samples: %s\n\n' % (meter['name'], str(samples))

            events = yield client.ceilometer_events(queries=[query])
            print 'meter: %s, events: %s\n\n' % (meter['name'], str(events))

            query = dict(field='meter', op='eq', value=meter['name'], type='string')
            alarms = yield client.ceilometer_alarms(queries=[query])
            print 'meter: %s, alarms: %s\n\n' % (meter['name'], str(alarms))
    except (BadRequestError, UnauthorizedError, NotFoundError, APIClientError) as e:
        pprint.pprint(e.message)
    else:
        resource_ids = [res['resource_id'] for res in resources]
        pprint.pprint(resource_ids)
        pprint.pprint(meters)

    if reactor.running:
        reactor.stop()

if __name__ == '__main__':
    main()
    reactor.run()
