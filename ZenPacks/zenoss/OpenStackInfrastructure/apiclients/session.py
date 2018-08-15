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

import json

from twisted.internet import reactor
from twisted.internet.error import TimeoutError
from twisted.internet.defer import inlineCallbacks, returnValue, succeed
from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.web.client import ProxyAgent, Agent, HTTPConnectionPool, readBody, BrowserLikePolicyForHTTPS
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer, IPolicyForHTTPS
from twisted.internet.ssl import CertificateOptions
from twisted.internet._sslverify import ClientTLSOptions

import urllib
from urllib import getproxies, urlencode
from urlparse import urlparse, urlunparse, parse_qsl

from zope.interface import implements
from zope.interface.declarations import implementer

from .utils import getDeferredSemaphore, add_timeout, zenpack_version
from .exceptions import APIClientError, UnauthorizedError, BadRequestError, NotFoundError
from .ssl import PermissiveBrowserLikePolicyForHTTPS, CertificateError


CONNECT_TIMEOUT = 30
READ_TIMEOUT = 30
MAX_POOL_CONNECTIONS = 10
MAX_PARALLEL = 250


def base_url(url):
    # strip trailing /
    if url.endswith('/'):
        url = url[:-1]
    return url


class StringProducer(object):
    implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


# These classes are used to tweak the SSL policy so that we ignore SSL host
# verification errors that occur with a self-signed certificate.
class PermissiveClientTLSOptions(ClientTLSOptions):
    def _identityVerifyingInfoCallback(self, connection, where, ret):
        try:
            super(PermissiveClientTLSOptions, self)._identityVerifyingInfoCallback(connection, where, ret)
        except (ValueError, CertificateError) as e:
            log.debug("Ignoring SSL hostname verification error for %s: %s", self._hostnameASCII, e)


@implementer(IPolicyForHTTPS)
class PermissiveBrowserLikePolicyForHTTPS(BrowserLikePolicyForHTTPS):
    def creatorForNetloc(self, hostname, port):
        certificateOptions = CertificateOptions(
            trustRoot=self._trustRoot)

        return PermissiveClientTLSOptions(
            hostname.decode("ascii"),
            certificateOptions.getContext())


class SessionManager(object):
    """
    Responsible for using the openstack identity API to acquire an
    authentication token, and for making API (http) requests using that token.

    Also collects the service catalog as part of the token, and makes that
    available.

    By channeling these HTTP requests from the various API clients through
    this object, it can (optionally, but by default) catches
    Invalid Authentication errors from the openstack API being called and
    re-authenticate, then retry the original API call.
    """

    _agents = {}

    def __init__(self, username=None, password=None, auth_url=None, project_id=None, region_name=None):
        self.username = username
        self.password = password
        self.auth_url = auth_url
        self.auth_api_version = None
        self.project_id = project_id
        self.region_name = region_name
        # Note, region_name is optional, but if it is not specified here,
        # it will need to be passed in to get_service_url()

        for required in ('username', 'password', 'auth_url', 'project_id'):
            if getattr(self, required, None) is None:
                raise APIClientError("Required parameter '%s' not specified" % required)

        self.token_id = None
        self.api_version = None

        self._service_url = {}

    def agent(self, scheme='http'):
        if not self._agents:
            pool = HTTPConnectionPool(reactor)
            pool.maxPersistentPerHost = 10
            pool.cachedConnectionTimeout = 15

            contextFactory = PermissiveBrowserLikePolicyForHTTPS()
            proxies = getproxies()

            if 'http' in proxies or 'https' in proxies:
                # I've noticed some intermittent failures (ResponseNeverReceived) to
                # POST request through a proxy when persistent connections are enabled.
                pool.persistent = False

            if 'https' in proxies:
                proxy = urlparse(proxies.get('https'))
                if proxy:
                    # Note- this isn't going to work completely.  It's not being
                    # passed the modified contextFactory, and in fact it doesn't
                    # even work properly for other reasons (ZPS-2061)
                    log.info("Creating https proxy (%s:%s)" % (proxy.hostname, proxy.port))
                    endpoint = TCP4ClientEndpoint(reactor, proxy.hostname, proxy.port, timeout=CONNECT_TIMEOUT)
                    SessionManager._agents['https'] = \
                        ProxyAgent(endpoint, reactor, pool=pool)
            else:
                SessionManager._agents['https'] = \
                    Agent(reactor, pool=pool, connectTimeout=CONNECT_TIMEOUT, contextFactory=contextFactory)

            if 'http' in proxies:
                proxy = urlparse(proxies.get('http'))
                if proxy:
                    log.info("Creating http proxy (%s:%s)" % (proxy.hostname, proxy.port))
                    endpoint = TCP4ClientEndpoint(reactor, proxy.hostname, proxy.port, timeout=CONNECT_TIMEOUT)
                    SessionManager._agents['http'] = \
                        ProxyAgent(endpoint, reactor, pool=pool)
            else:
                SessionManager._agents['http'] = \
                    Agent(reactor, pool=pool, connectTimeout=CONNECT_TIMEOUT)

        return SessionManager._agents[scheme]

    def default_headers(self):
        return Headers({
            'Accept': ['application/json'],
            'Content-Type': ['application/json'],
            'User-Agent': ['Zenoss/%s' % zenpack_version()]
        })

    def handle_error_response(self, response, body):
        if response.code == 401:
            raise UnauthorizedError("%s %s (check username and password)" % (response.code, response.phrase))
        elif response.code == 400:
            raise BadRequestError("%s %s (check headers and/or data)" % (response.code, response.phrase))
        elif response.code == 404:
            raise NotFoundError("%s %s: %s" % (response.code, response.phrase, response.request.absoluteURI))
        elif int(response.code) >= 400:
            # some other unrecognized error
            try:
                data = json.loads(body)
                error = data['error']['message']
            except Exception:
                error = body
            raise APIClientError("%s %s: %s" % (response.code, response.phrase, error))

    def _apply_params(self, url, params):
        """
        Take the supplied parameters and substitute them into the URL-
        Any that match placeholders (of the form {param[paramname]) in the url
        path will be plugged in, and any remaining ones will be merged with
        any existing query parameters.

        Note that multi-valued query params are not supported.
        """

        class apiparams(dict):
            # a dictionary that removes keys when they are accessed (in this
            # case, by url.format()), leaving only unused keys present.
            def __getitem__(self, key):
                value = dict.__getitem__(self, key)
                del self[key]
                return urllib.quote(str(value))

        q = apiparams(params)
        try:
            url = url.format(param=q)
        except AttributeError, e:
            raise AttributeError("%s: %s" % (url, e))

        p = urlparse(url)
        query = {}
        for k, v in parse_qsl(p.query):
            query[k] = v

        # merge user-specified params into any that are pre-existing
        query.update(q)

        return urlunparse(
            (p.scheme, p.netloc, p.path, p.params, urlencode(query), p.fragment))

    @inlineCallbacks
    def GET_request(self, url, headers=None, params=None):
        scheme = urlparse(url).scheme
        agent = self.agent(scheme)
        if headers is None:
            headers = self.default_headers()
        if params is None:
            params = {}

        url = self._apply_params(url, params)

        semaphore = getDeferredSemaphore(self.auth_url, MAX_PARALLEL)

        log.debug("GET %s", url)
        headerargs = " ".join(["-H \"%s: %s\"" % (x[0], x[1][0]) for x in headers.getAllRawHeaders()])
        log.debug('curl "{url}" {headerargs}'.format(
            url=url,
            headerargs=headerargs
        ))

        try:
            response = yield semaphore.run(
                add_timeout,
                agent.request(
                    'GET',
                    url,
                    headers=headers
                ),
                READ_TIMEOUT
            )
        except TimeoutError:
            raise TimeoutError("GET %s" % url)
        body = yield readBody(response)
        log.debug("GET %s => %s", url, body)

        # If the request resulted in an error, raise an exception
        self.handle_error_response(response, body)

        returnValue((body, response.headers))

    @inlineCallbacks
    def authenticated_GET_request(self, url, headers=None, params=None):
        if headers is None:
            headers = self.default_headers()

        if self.token_id is None:
            yield self.authenticate()
        headers.setRawHeaders('X-Auth-Token', [self.token_id])

        try:
            result = yield self.GET_request(url, headers=headers, params=params)
            returnValue(result)
        except UnauthorizedError:
            log.info("Received unauthorized response to http request, re-authenticating.  (%s)", url)
            yield self.authenticate()
            headers.setRawHeaders('X-Auth-Token', [self.token_id])

        result = yield self.GET_request(url, headers=headers, params=params)
        returnValue(result)

    @inlineCallbacks
    def POST_request(self, url, headers=None, body=None):
        scheme = urlparse(url).scheme
        agent = self.agent(scheme)
        if headers is None:
            headers = self.default_headers()

        if body is None:
            body = ""

        semaphore = getDeferredSemaphore(self.auth_url, MAX_PARALLEL)

        log.debug("POST %s", url)

        try:
            response = yield semaphore.run(
                add_timeout,
                agent.request(
                    'POST',
                    url,
                    headers=headers,
                    bodyProducer=StringProducer(body)
                ),
                READ_TIMEOUT
            )
        except TimeoutError:
            raise TimeoutError("POST %s" % url)

        body = yield readBody(response)
        log.debug("POST %s => %s", url, body)

        # If the request resulted in an error, raise an exception
        self.handle_error_response(response, body)

        returnValue((body, response.headers))

    @inlineCallbacks
    def authenticated_POST_request(self, url, headers=None, body=None):
        if self.token_id is None:
            yield self.authenticate()
        headers.setRawHeaders('X-Auth-Token', [self.token_id])

        try:
            result = yield self.POST_request(url, headers=headers, body=body)
            returnValue(result)
        except UnauthorizedError:
            log.info("Received unauthorized response to http request, re-authenticating.  (%s)", url)
            yield self.authenticate()
            headers.setRawHeaders('X-Auth-Token', [self.token_id])

        result = yield self.POST_request(url, headers=headers, body=body)
        returnValue(result)

    @inlineCallbacks
    def _detect_api_version(self):
        """
        Based on the auth_url that this SessionManager was initialized with,
        determine which API version it is (by querying it if necessary) and
        return the base url (essentially the auth url with no trailing /)
        and the api version (as a string, "v2.0" or "v3.0").

        This is an internal method.  External callers should use get_api_version().
        """

        url = urlparse(self.auth_url)
        path = base_url(url.path)

        # new url, with the trailing / removed.
        auth_url_base = urlunparse(
            (url.scheme, url.netloc, path, url.params, url.query, url.fragment))

        if path == "":
            # Unversioned URL- Let's see what is available.
            response_body, response_headers = yield self.GET_request(self.auth_url)
            try:
                data = json.loads(response_body)
                version_url = {}
                for version in data['versions']['values']:
                    if version['status'] != 'stable':
                        continue
                    for url in [x['href'] for x in version['links'] if x['rel'] == 'self']:
                        version_url[str(version['id'])] = base_url(str(url))

                v3_url = None
                v2_url = None
                for k, v in version_url.iteritems():
                    if k.startswith('v3.'):
                        v3_url = v
                        break   #prefer v3
                    elif k.startswith('v2.'):
                        v2_url = v

                if v3_url:
                    returnValue((v3_url, 'v3.0'))
                elif v2_url:
                    returnValue((v2_url, 'v2.0'))
                else:
                    log.error("No recognized API versions.  The following were found: %s", ", ".join(version_url.keys()))
                    raise ValueError("No recognized API versions")

            except Exception:
                raise APIClientError("Unable to determine identity API version from %s", self.auth_url)

        elif path.endswith("/v2.0"):
            # v2.0 isn't especially self-documenting via http.  We could
            # query it and look at the media-types, but that's no more
            # reliable than looking at the URL anyway.
            api_version = "v2.0"
        else:
            response_body, response_headers = yield self.GET_request(self.auth_url)
            try:
                data = json.loads(response_body)
                api_version = str(data['version']['id'])
            except Exception:
                raise APIClientError("Unable to determine identity API version from %s", self.auth_url)

        returnValue((auth_url_base, api_version))

    @inlineCallbacks
    def authenticate(self):
        auth_url_base, api_version = yield self._detect_api_version()
        self.auth_url_base = auth_url_base

        if api_version.startswith("v2"):
            self.api_version = api_version

            body = json.dumps({
                "auth": {
                    "tenantName": self.project_id,
                    "passwordCredentials": {
                        "username": self.username,
                        "password": self.password
                    }
                }
            })

            response_body, response_headers = yield self.POST_request(auth_url_base + '/tokens', body=body)
            data = json.loads(response_body)

            try:
                self.token_id = str(data['access']['token']['id'])
                log.debug("Acquired token: %s", self.token_id)
            except KeyError:
                self.token_id = None
                raise APIClientError("Unable to identify token ID in response: %s" % response_body)

            service_url = {}
            for entry in data['access']['serviceCatalog']:
                service_type = entry['type']
                for endpoint in entry['endpoints']:
                    region = endpoint['region']
                    service_url[(region, service_type, 'admin')] = str(endpoint['adminURL'])
                    service_url[(region, service_type, 'public')] = str(endpoint['publicURL'])

            self._service_url = service_url

        elif api_version.startswith("v3"):
            self.api_version = api_version

            body = json.dumps({
                "auth": {
                    "scope": {
                        "project": {
                            "domain": {
                                "id": "default"
                            },
                            "name": self.project_id
                        }
                    },
                    "identity": {
                        "password": {
                            "user": {
                                "domain": {
                                    "id": "default"
                                },
                                "password": self.password,
                                "name": self.username
                            }
                        },
                        "methods": ["password"]
                    }
                }
            })

            response_body, response_headers = yield self.POST_request(auth_url_base + '/auth/tokens', body=body)
            data = json.loads(response_body)

            if response_headers.hasHeader('x-subject-token'):
                self.token_id = str(response_headers.getRawHeaders('x-subject-token')[0])
                log.debug("Acquired token: %s", self.token_id)
            else:
                self.token_id = None
                raise APIClientError("Unable to identify token ID in response: %s" % response_body)

            service_url = {}
            for entry in data['token']['catalog']:
                service_type = entry['type']
                for endpoint in entry['endpoints']:
                    region = endpoint['region_id']
                    if endpoint['interface'] in ['admin', 'public']:
                        service_url[(region, service_type, endpoint['interface'])] = str(endpoint['url'])

            self._service_url = service_url

        else:
            raise APIClientError("[Authenticate] Unsupported identity API version: %s" % self.api_version)

    @inlineCallbacks
    def get_service_url(self, service_type, interface='public', region_name=None):
        # Return the URL for a service in the current region.  Returns None
        # if no such URL was defined in the service catalog.

        # Populate the service catalog if we haven't already done so.
        if not self._service_url:
            yield self.authenticate()

        if region_name is None:
            region_name = self.region_name

        if region_name is None:
            raise APIClientError("Region not specified")

        url = self._service_url.get((region_name, service_type, interface))

        if url is None:
            log.error("No URL found for service type '%s', region '%s'", service_type, region_name)

        # Sometimes we're using a different URL to access the identity API than
        # the one that is reported in the keystone endpoint list.  In particular,
        # if we're connecting to the v3 keystone endpoint, but it's returning
        # v2 urls, we want to stick with the v3 one and ignore what it says.
        if service_type == 'identity':
            if self.api_version.startswith("v3"):
                if base_url(url) != self.auth_url_base:
                    log.debug("Keystone catalog reports %s as %s %s endpoint, "
                              "which disagrees with the value derived from "
                              "auth_url.  Using %s", base_url(url), service_type,
                              interface, self.auth_url_base)
                    returnValue(self.auth_url_base)
            elif self.api_version.startswith("v2"):
                if interface == 'public':
                    if base_url(url) != self.auth_url_base:
                        log.debug("Keystone catalog reports %s as %s %s endpoint, "
                                  "which disagrees with the value derived from "
                                  "auth_url.  Using %s", base_url(url), service_type,
                                  interface, self.auth_url_base)
                        returnValue(self.auth_url_base)
                else:
                    # In the v2.0 case, we have to honor the admin URL from the
                    # keystone catalog unconditionally, since deriving it from
                    # the auth_url (changing the port, etc) is not completely
                    # safe.
                    returnValue(base_url(url))
            else:
                raise APIClientError("[URL] Unsupported identity API version: %s" % self.api_version)

        returnValue(base_url(url))

    @inlineCallbacks
    def get_regions(self):
        if not self._service_url:
            yield self.authenticate()

        regions = set()
        for x in self._service_url.keys():
            regions.add(x[0])
        returnValue(sorted(list(regions)))

    @inlineCallbacks
    def get_api_version(self):
        if self.api_version is None:
            self.auth_url_base, self.api_version = yield self._detect_api_version()

        returnValue(self.api_version)
