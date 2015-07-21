##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""keystoneapiclient - Client library for the OpenStack Keystone API.

Example usage:

    >>> c = keystoneapiclient.Client(username, password, auth_url, project_id)
    >>> c.endpoints()
    {
        "endpoints": [list of endpoints ],
    }

"""

import collections
import httplib
import json

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web import client as txwebclient
from twisted.web.error import Error
from twisted.internet import reactor

import logging
log = logging.getLogger('zen.OpenStack.keystoneapiclient')


__all__ = [
    # Exceptions
    'KeystoneError',
    'BadRequestError',
    'UnauthorizedError',
    ]


USER_AGENT = 'zenoss-keystoneclient'


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


class KeystoneAPIClient(object):

    """Twisted asynchronous Keystone client."""

    def __init__(self, username, password, auth_url, project_id, admin=False):
        """Create Keystone API client."""
        self.username = username
        self.password = password
        self.auth_url = auth_url
        self.project_id = project_id
        self.admin = admin

        self._apis = {}
        self._keystone_url = None
        self._token = None
        self._serviceCatalog = None

    def _admin_only(self, api_method):
        if self.admin is False:
            raise BadRequestError("'%s' is only available in the Identity admin API v2.0" % api_method)

    @property
    def endpoints(self):
        """Return entry-point to the API."""
        self._admin_only()
        return self._apis.setdefault('endpoints', API(self, '/endpoints'))

    @property
    def roles(self):
        """Return entry-point to the API."""
        self._admin_only()
        return self._apis.setdefault('roles', API(self, '/OS-KSADM/roles'))

    @property
    def services(self):
        """Return entry-point to the API."""
        self._admin_only()
        return self._apis.setdefault('services',
                                     API(self, '/OS-KSADM/services'))

    @property
    def tenants(self):
        """Return entry-point to the API."""
        return self._apis.setdefault('tenants', API(self, '/tenants'))

    @property
    def users(self):
        """Return entry-point to the API."""
        self._admin_only()
        return self._apis.setdefault('users', API(self, '/users'))

    def __getitem__(self, name):
        if name == 'endpoints':
            return self.endpoints
        elif name == 'roles':
            return self.roles
        elif name == 'services':
            return self.services
        elif name == 'tenants':
            return self.tenants
        elif name == 'users':
            return self.users

        raise TypeError(
            "%r object is not subscriptable (except for endpoints" +
            ", roles, services, tenants, users",
            self.__class__.__name__)

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

        self._token = r['access']['token']['id'].encode('ascii', 'ignore')
        self._serviceCatalog = r['access']['serviceCatalog']

        if self.admin is True:
            # switch from the Identity API (usually port 5000) to the Identity
            # Admin API (usually port 35357)
            for sc in r['access']['serviceCatalog']:
                if sc['type'] == 'identity' and sc['name'] == 'keystone':
                    self._keystone_url = sc['endpoints'][0]['adminURL'].encode(
                        'ascii', 'ignore')

        self._serviceCatalog = r['access']['serviceCatalog']

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
        """Return result of Keystone request.

        Typically this is not meant to be called directly. It is meant
        to be used through the api property as follows:

            client.endpoints({'data': 'value'})

        However, it can be used directly as follows:

            client.api_call('/endpoints', data={'data': 'value'})

        """
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
            response = json.loads(e.response)
            text = response['error']['message']

            if status == httplib.UNAUTHORIZED:
                raise UnauthorizedError(text + " (check username & password)")
            elif status == httplib.BAD_REQUEST:
                raise BadRequestError(text)
            elif status == httplib.NOT_FOUND:
                raise NotFoundError(text)

            raise KeystoneError(text)

        except Exception as e:
            raise KeystoneError(e)

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

        if self._keystone_url is not None and method == 'GET':
            auth_url = self._keystone_url
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
        return self.client.api_call(
            self.path, data=data, params=params, **kwargs)


# Exceptions #########################################################

class KeystoneError(Exception):

    """Parent class of all exceptions raised by txciscoapic."""

    pass


class BadRequestError(KeystoneError):

    """Wrapper for HTTP 400 Bad Request error."""

    pass


class UnauthorizedError(KeystoneError):

    """Wrapper for HTTP 401 Unauthorized error."""

    pass


class NotFoundError(KeystoneError):

    """Wrapper for HTTP 400 Bad Request error."""

    pass


def main():
#   c = KeystoneAPIClient('admin',
#                         'password',
#                         'http://192.168.56.104:5000/v2.0',
#                         'demo')
#   c = KeystoneAPIClient('admin',
#                         '8a041d9c59dd403a',
#                         'http://10.87.208.184:5000/v2.0',
#                         'admin')
    c = KeystoneAPIClient('admin',
                          'c96e7977c18748e8',
                          'http://192.168.56.122:5000/v2.0',
                          'admin')
    ret = c.endpoints()
#   ret = c.roles()
#   ret = c.services()
#   ret = c.tenants()
#   ret = c.users()
    reactor.run()
    print ret.result

if __name__ == '__main__':
    main()
