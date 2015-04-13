##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""neutronapiclient - Client library for the OpenStack Neutron API.

Example usage:

    >>> c = neutronapiclient.Client(username, password, auth_url, project_id, region)
    >>> c.networks()
    {
        "networks": [list of networks ],
    }

"""

import collections
import httplib
import json

import logging
log = logging.getLogger('zen.OpenStack.neutronapiclient')

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web import client as txwebclient
from twisted.web.error import Error
from twisted.internet import reactor
import urllib

__all__ = [

    # Exceptions
    'NeutronError',
    'BadRequestError',
    'UnauthorizedError',
    ]


USER_AGENT = 'zenoss-neutronclient'


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


class NeutronAPIClient(object):

    """Twisted asynchronous Neutron client."""

    def __init__(self, username, password, auth_url, project_id, region_name):
        """Create Neutron API client."""
        self.username = username
        self.password = password
        self.auth_url = auth_url
        self.project_id = project_id
        self.region_name = region_name

        self._apis = {}
        self._neutron_url = None
        self._token = None

    @property
    def agents(self):
        """Return entry-point to the API."""
        return self._apis.setdefault('agents', API(self, "/agents"))

    @property
    def floatingips(self):
        """Return entry-point to the API."""
        return self._apis.setdefault('floatingips', API(self, '/floatingips'))

    @property
    def networks(self):
        """Return entry-point to the API."""
        return self._apis.setdefault('networks', API(self, '/networks'))

    @property
    def ports(self):
        """Return entry-point to the API."""
        return self._apis.setdefault('ports', API(self, '/ports'))

    @property
    def routers(self):
        """aka instances."""
        return self._apis.setdefault('routers', API(self, "/routers"))

    @property
    def security_groups(self):
        """Return entry-point to the API."""
        return self._apis.setdefault('security_groups', API(self, "/security-groups"))

    @property
    def subnets(self):
        """Return entry-point to the API."""
        return self._apis.setdefault('subnets', API(self, "/subnets"))

    def __getitem__(self, name):
        if name == 'agents':
            return self.agents
        elif name == 'networks':
            return self.networks
        elif name == 'ports':
            return self.ports
        elif name == 'routers':
            return self.routers
        elif name == 'security_groups':
            return self.security_groups
        elif name == 'subnets':
            return self.subnets
        elif name == 'floatingips':
            return self.floatingips

        raise TypeError(
            "%r object is not subscriptable (except for agents" +
            ", floatingips, networks, ports, routers, securitygroups" +
            ", subnets",
            self.__class__.__name__)

    @inlineCallbacks
    def login(self):
        """Login to Neutron.

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

        r = {}
        try:
            r = yield self.direct_api_call('/tokens', data=body)
        except Error:
            log.error("Error from login: %s" % str(Error))

        except Exception as ex:
            log.error("Exception from login: %s" % str(ex))

        if 'access' in r.keys():
            self._token = r['access']['token']['id'].encode('ascii', 'ignore')
            self._service_catalog = r['access']['serviceCatalog']
            for sc in self._service_catalog:
                if sc['type'] == 'network' and sc['name'] == 'neutron':
                    self._neutron_url = sc['endpoints'][0]['adminURL'].encode('ascii', 'ignore')
                    break

        returnValue(r)

    @inlineCallbacks
    def api_call(self, path, data=None, params=None, **kwargs):
        """Wrap direct_api_call for convenience purposes.

        Will authenticate prior to making an API call if necessary, and
        reauthenticate and retry the API call if an unauthorized error
        is encountered during the first API call attempt.

        """
        if not self._token:
            yield self.login()

        try:
            r = yield self.direct_api_call(
                path, data=data, params=params, **kwargs)
        except UnauthorizedError:
            # Could be caused by expired token. Try to login.
            yield self.login()

            # Then try the call again.
            r = yield self.direct_pi_call(
                path, data=data, params=params, **kwargs)

        returnValue(r)

    @inlineCallbacks
    def direct_api_call(self, path, data=None, params=None, **kwargs):
        """Return result of Neutron request.

        Typically this is not meant to be called directly. It is meant
        to be used through the api property as follows:

            client.networks({'data': 'value'})

        However, it can be used directly as follows:

            client.api_call('/networks', data={'data': 'value'})

        """

        # it could happen that OpenStack's Endpoints do not have '/'
        # in front of 'v2.0/xxx', which will be OpenStack bug.
        # add '/' if this is the case
        if path[0] != '/':
            path = '/' + path
        request = self._get_request(path, data=data, params=params, **kwargs)
        log.debug("Request URL: %s" % request.url)

        try:
            response = yield getPageAndHeaders(
                request.url,
                method=request.method,
                agent=request.agent,
                headers=request.headers,
                postdata=request.postdata)

        except Error as e:
            status = int(e.status)
            response = e.response
            text = str(response)

            if status == httplib.UNAUTHORIZED:
                raise UnauthorizedError(text + " (check username and password)")
            elif status == httplib.BAD_REQUEST:
                raise BadRequestError(text)
            elif status == httplib.NOT_FOUND:
                raise NotFoundError(text)

            raise NeutronError(text)

        except Exception as e:
            raise NeutronError(e)

        returnValue(json.loads(response[0]))

    def _get_request(self, path, data=None, params=None, **kwargs):
        # Process data. Supports a variety of input types.
        # /tokens uses POST; all others use GET
        postdata = json.dumps(data) if data else None

        method = 'POST' if postdata else 'GET'

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': USER_AGENT,
            }

        if self._token:
            headers['X-Auth-Token'] = self._token

        if self._neutron_url is not None and method == 'GET':
            auth_url = self._neutron_url
        else:
            auth_url = self.auth_url
        return Request(
            auth_url + path,
            method=method,
            agent=USER_AGENT,
            headers=headers,
            postdata=postdata)


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
        # update self.path based on kwargs
        if kwargs:
            qparams = {}
            if kwargs.has_key('detailed') and kwargs['detailed']:
                detail = '/detail' if kwargs['detailed'] else ""
                self.path += '%s' % detail

        #     # is_public is ternary - None means give all flavors.
        #     # By default Nova assumes True and gives admins public flavors
        #     # and flavors from their own projects only.
            if self.path.find('agents') > -1 and \
                kwargs.has_key('is_public') and \
                kwargs['is_public'] is not None:
                qparams['is_public'] = kwargs['is_public']
                if qparams:
                    self.path += '?%s' % urllib.urlencode(qparams)

            if self.path.find('networks') > -1 and \
                kwargs.has_key('zone') and \
                kwargs['zone'] is not None:
                self.path += '?zone=%s' % kwargs['zone']

            if self.path.find('subnets') > -1 and \
                kwargs.has_key('limit') and \
                kwargs['limit'] is not None:
                self.path += '?limit=%d' % int(kwargs['limit'])

            if self.path.find('ports') > -1:
                params = {}
                if kwargs.has_key('search_opts') and \
                   kwargs['search_opts'] is not None:
                    for opt, val in kwargs['search_opts'].iteritems():
                        if val:
                            params[opt] = val
                if kwargs.has_key('marker'):
                    params['marker'] = kwargs['marker']
                if kwargs.has_key('limit'):
                    params['limit'] = int(kwargs['limit'])
                query_string = "?%s" % urllib.urlencode(params) if params else ""
                self.path += '%s' % query_string

            if self.path.find('security-groups') > -1:
                filters = []
                if kwargs.has_key('host') and \
                    kwargs['host'] is not None:
                    filters.append("router=%s" % kwargs['router'])
                if kwargs.has_key('binary') and \
                    kwargs['binary'] is not None:
                    filters.append("binary=%s" % kwargs['binary'])
                if filters:
                    self.path += "?%s" % "&".join(filters)

            if self.path.find('routers') > -1 and \
                kwargs.has_key('router_match') and \
                kwargs['router_match'] is not None and \
                kwargs.has_key('routers'):
                target = 'routers' if kwargs['routers'] else 'search'
                self.path += '/%s/%s' % (
                    urllib.quote(kwargs['router_match'], safe=''),
                    target)

        # update self.path again
        self.path = "v2.0%s.json" % self.path

        return self.client.api_call(
            self.path, data=data, params=params, **kwargs)


# Exceptions #########################################################

class NeutronError(Exception):

    """Parent class of all exceptions raised by txciscoapic."""
    pass


class BadRequestError(NeutronError):

    """Wrapper for HTTP 400 Bad Request error."""

    pass


class UnauthorizedError(NeutronError):

    """Wrapper for HTTP 401 Unauthorized error."""

    pass


class NotFoundError(NeutronError):

    """Wrapper for HTTP 400 Bad Request error."""

    pass


def main():
    import json
    import sys

    c = NeutronAPIClient('admin', 'zenoss', 'http://mp8.zenoss.loc:5000/v2.0', 'admin', 'RegionOne')
    try:
        net = yield c.networks()
    except Exception as e:
        print >> sys.stderr, "ERROR - networks(): %s" % e
    else:
        json.dumps(net.result, sort_keys=True, indent=4)

    reactor.stop()

if __name__ == '__main__':
    from twisted.internet import reactor

    main()
    reactor.run()
