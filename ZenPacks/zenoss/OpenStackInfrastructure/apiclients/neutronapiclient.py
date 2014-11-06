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
    >>> c.api.networks()
    {
        "networks": [list of networks ],
    }
    >>> c.api.networks(id='abc-123-ak47')
        (shows the network with specified ID)

    >>> c.api.networks(id='abc-123-ak47', fields=['id', 'name'])
        (shows the network data with restricted fields)

"""

import collections
import httplib
import json

import logging
# logging.basicConfig()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger('zen.OpenStackInfrastructure.apiclients.neutronapiclient.py')

# class NullHandler(logging.Handler):
#     def emit(self, record):
#             pass

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web import client as txwebclient
from twisted.web.error import Error

# import Globals
# from ZenPacks.zenoss.OpenStackInfrastructure.utils import add_local_lib_path
# add_local_lib_path()


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

        self._api = None
        self._neutron_url = None
        self._token = None

    @property
    def api(self):
        """Return entry-point to the API."""
        if not self._api:
            # self._api = API(self, 'api')
            self._api = API(self, '')

        return self._api

    def __getitem__(self, name):
        if name == 'api':
            return self.api

        raise TypeError(
            "%r object is not subscriptable (except for api)",
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
            text = str(e.response)

            if status == httplib.UNAUTHORIZED:
                raise UnauthorizedError(text + " (check username and password)")
            elif status == httplib.BAD_REQUEST:
                raise BadRequestError(text)
            elif status == httplib.NOT_FOUND:

                log.info("\n\tNeutroAPI Error: %s" % request.url)
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

    # def __init__(self, client, path='api'):
    def __init__(self, client, path=''):
        self.client = client
        self.path = path.replace('_','-')
        self._apis = {}

    def __getattr__(self, name):
        # class is a frequently-used API path, but it won't work because
        # it's a Python reserved word. Add aliases for it.
        if name in ('klass', 'cls', '_class'):
            name = 'class'

        if name not in self._apis:
            self._apis[name] = API(self.client, '/'.join((self.path, name)))

        return self._apis[name]

    def __getitem__(self, name):
        return getattr(self, name)

    def __call__(self, data=None, params=None, **kwargs):

        path = self.path

        # log.debug("Entering API.__call__() ")
        # update self.path and filter urls based on kwargs
        if kwargs:

            if 'id' in kwargs and kwargs['id'] is not None:
                path += '/%s' % kwargs['id']

        # update the final path and attache the .json postfix
        path = "v2.0%s.json" % path

        # Testing fields... Must put below more generally
        if 'fields' in kwargs and kwargs['fields'] is not None:
            fields = []
            for f in kwargs['fields']:
                fields.append('fields=%s' % f)

            path += '?%s' % '&'.join(fields)

        # log.debug("Rest Call Path" % path)

        return self.client.api_call(path, data=data, params=params, **kwargs)


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


@inlineCallbacks
def main():
    import pprint
    import sys

    cc = NeutronAPIClient('admin', 'zenoss', 'http://mp8.zenoss.loc:5000/v2.0', 'admin', 'RegionOne')

    try:
        sec = yield cc.api.ity_up_rules()
    except Exception as e:

        log.info("\n\t in_main: NeutroAPI: broken stuff in call")
        # print >> sys.stderr, "main: ERROR : %s" % e
        # print "Error output : %s" % e.message
        # print "Error dir : %s" % e.__class__

    else:
        pprint.pprint(sec)

    try:
        net1 = yield cc.api.networks()
        net2 = yield cc.api.networks(id='af6dbc23-c491-4756-8e01-7dd86e7b44b2',
                fields=['name','id'])
    except Exception as e:
        print >> sys.stderr, "ERROR - networks(<id>): %s" % e
    else:
        print type(net1)
        pprint.pprint(net1)
        print "---------------------------------------------------------------"
        print type(net2)
        pprint.pprint(net2)

    #-- net = c.security_groups(id='c9f928ed-bcda-4698-981e-c07ea22f2eb2')

    reactor.stop()


if __name__ == '__main__':
    from twisted.internet import reactor

    main()
    reactor.run()
