##############################################################################
#
# Copyright (C) Zenoss, Inc. 2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.ApiEndpointStatus')
logging.basicConfig(level=logging.INFO)


import httplib
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.error import Error as TwistedWebError
from twisted.web.client import getPage

from zope.component import adapts
from zope.interface import implements

import Globals
from Products.ZenEvents import ZenEventClasses
from Products.ZenUtils.Utils import unused
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.utils import ZuulMessageFactory as _t
unused(Globals)

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import (
    PythonDataSource, PythonDataSourcePlugin, PythonDataSourceInfo,
    IPythonDataSourceInfo)

from ZenPacks.zenoss.OpenStackInfrastructure import ZenPack
from ZenPacks.zenoss.OpenStackInfrastructure.utils import result_errmsg
from ZenPacks.zenoss.OpenStackInfrastructure.apiclients.txapiclient import SessionManager


class APIClient(object):
    # Ideally, this could use proper APIClient classes from txapiclient, but
    # for now, we only use the SessionManager (for keystone auth only), and then do
    # our own basic GET requests with the resulting token.

    session_manager = None

    def __init__(self, username, password, auth_url, project_id, user_domain_name, project_domain_name, region_name):
        self.session_manager = SessionManager(username, password, auth_url, project_id, user_domain_name, project_domain_name, region_name)

    @inlineCallbacks
    def authenticated_get(self, url):
        if not self.session_manager.token_id:
            yield self.session_manager.authenticate()
        headers = {'X-Auth-Token': self.session_manager.token_id}

        try:
            result = yield self.get(url, extra_headers=headers)
            returnValue(result)
        except TwistedWebError, e:
            if int(e.status) == httplib.UNAUTHORIZED:
                # Could be caused by expired token. Try to login.
                log.debug("Unauthorized request- logging in")
                yield self.session_manager.login()

                # Then try the call again.
                result = yield self.get(url, extra_headers=headers)
                returnValue(result)
            else:
                raise

    @inlineCallbacks
    def get(self, url, extra_headers=None):
        user_agent = 'zenoss-endpointstatus'
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': user_agent,
        }
        if extra_headers:
            headers.update(extra_headers)

        log.debug("Request URL=%s", url)
        log.debug("headers=%s" % str(headers))
        try:
            response = yield getPage(
                url,
                method='GET',
                agent=user_agent,
                headers=headers
            )
        except TwistedWebError, e:
            if int(e.status) == httplib.MULTIPLE_CHOICES:
                # handle a 300 response as a normal valid response, not an error.
                # return the body.
                response = e.response
            else:
                raise

        log.debug("Response=%s", response)

        returnValue(response)


class ApiEndpointStatusDataSource(PythonDataSource):
    '''
    Datasource used to check the status of nova services via the nova API
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack API Endpoint Status',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 30

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'ApiEndpointStatusDataSource.ApiEndpointStatusDataSourcePlugin'

    # ApiEndpointStatusDataSource

    _properties = PythonDataSource._properties + (
        {'id': 'auth_required', 'type': 'boolean'},
        {'id': 'ok_result', 'type': 'string'},
        {'id': 'sample_url', 'type': 'string'},
    )

    # These workarounds should be removed once this zenpack is updated to
    # use ZPL2.
    def __setattr__(self, name, value):
        # force auth_required to be a boolean (it appears that ZPL loader
        # will set unknown properties (extra_params) as strings otherwise.
        if name == 'auth_required':
            value = bool(str(value).lower() == 'true')
        super(ApiEndpointStatusDataSource, self).__setattr__(name, value)

    def __getattribute__(self, name):
        value = super(ApiEndpointStatusDataSource, self).__getattribute__(name)
        # while the zenpack is being uninstalled, temporarily return this
        # boolean as a string, to fool the ZPL change detection (it thinks
        # the value in the file is a string..)
        if ZenPack.UNINSTALLING and name == 'auth_required':
            return unicode(value).lower()
        else:
            return value


class IApiEndpointStatusDataSourceInfo(IPythonDataSourceInfo):
    '''
    API Info interface for IApiEndpointStatusDataSource.
    '''

    auth_required = schema.Bool(
        group=_t('OpenStack API Endpoint Status'),
        title=_t('Authentication Required?'))

    ok_result = schema.TextLine(
        group=_t('OpenStack API Endpoint Status'),
        title=_t('Required Result'))

    sample_url = schema.TextLine(
        group=_t('OpenStack API Endpoint Status'),
        title=_t('Example URL'))


class ApiEndpointStatusDataSourceInfo(PythonDataSourceInfo):
    '''
    API Info adapter factory for ApiEndpointStatusDataSource.
    '''

    implements(IApiEndpointStatusDataSourceInfo)
    adapts(ApiEndpointStatusDataSource)

    testable = False

    auth_required = ProxyProperty('auth_required')
    ok_result = ProxyProperty('ok_result')
    sample_url = ProxyProperty('sample_url')


class ApiEndpointStatusDataSourcePlugin(PythonDataSourcePlugin):
    proxy_attributes = ()

    @classmethod
    def config_key(cls, datasource, context):
        """
        Return list that is used to split configurations at the collector.

        This is a classmethod that is executed in zenhub. The datasource and
        context parameters are the full objects.
        """
        return (
            context.device().id,
            datasource.getCycleTime(context),
            datasource.plugin_classname,
            context.id
        )

    @classmethod
    def params(cls, datasource, context):

        return {
            'service_type': context.service_type,
            'url': context.url,
            'username': context.zCommandUsername,
            'password': context.zCommandPassword,
            'project_id': context.zOpenStackProjectId,
            'auth_url': context.zOpenStackAuthUrl,
            'user_domain_name': context.zOpenStackUserDomainName,
            'project_domain_name': context.zOpenStackProjectDomainName,
            'region_name': context.zOpenStackRegionName,
            'auth_required': datasource.auth_required,
            'ok_result': datasource.ok_result
        }

    def _get_ds0(self, config):
        # the monitoring template for this datasource contains multiple
        # datasources, one for each supported service type.
        #
        # For the component being monitored (there will be only one in the
        # config for each invocation of collect, because the component id is
        # part of the config_key above), find the datasource whose name
        # matches the modeled service type for this api endpoint.

        datasources = [x for x in config.datasources
                       if x.datasource == x.params['service_type']]
        if datasources:
            return datasources[0]

    @inlineCallbacks
    def collect(self, config):
        ds0 = self._get_ds0(config)
        if not ds0:
            returnValue(None)

        service_type = ds0.params['service_type']
        url = ds0.params['url']

        log.debug("Collect for OpenStack API Endpoint Status (%s / %s  (%s endpoint))" % (config.id, url, service_type))

        client = APIClient(
            ds0.params['username'],
            ds0.params['password'],
            ds0.params['auth_url'],
            ds0.params['project_id'],
            ds0.params.get('user_domain_name', 'default'),
            ds0.params.get('project_domain_name', 'default'),
            ds0.params['region_name']
        )

        if ds0.params['auth_required']:
            result = yield client.authenticated_get(url)
        else:
            result = yield client.get(url)
        returnValue(result)

    def onSuccess(self, result, config):
        data = self.new_data()
        ds0 = self._get_ds0(config)
        if not ds0:
            return data

        summary = '%s API Status: successful collection' % ds0.params['service_type'].title()
        data['events'].append({
            'device': config.id,
            'component': ds0.component,
            'summary': summary,
            'severity': ZenEventClasses.Clear,
            'eventClassKey': 'openStackApiEndpointStatus',
            'eventKey': ds0.params['url']
        })

        return data

    def onError(self, result, config):
        data = self.new_data()
        ds0 = self._get_ds0(config)
        if not ds0:
            return data

        summary = '%s API Status: %s' % (ds0.params['service_type'].title(), result_errmsg(result))
        data['events'].append({
            'device': config.id,
            'component': ds0.component,
            'summary': summary,
            'severity': ZenEventClasses.Error,
            'eventClassKey': 'openStackApiEndpointStatus',
            'eventKey': ds0.params['url']
        })

        log.error('%s: %s', config.id, summary)

        return data


@inlineCallbacks
def main():
    client = APIClient('admin', 'adminpassword', 'http://192.168.2.15:5000/v2.0', 'admin', 'default', 'default', 'RegionOne')

    @inlineCallbacks
    def _check_unauthenticated(name, url):
        try:
            result = yield client.get(url)
        except Exception, e:
            print "%s FAIL: %s" % (name, e)
            return

        if "version" in result:
            print "%s OK" % name
        else:
            print "%s FAIL: %s" % (name, result)

    @inlineCallbacks
    def _check_authenticated(name, url):
        try:
            result = yield client.authenticated_get(url)
        except Exception, e:
            print "%s FAIL: %s" % (name, e)
            return

        if "version" in result:
            print "%s OK" % name
        else:
            print "%s FAIL: %s" % (name, result)
    # identity (keystone)
    yield _check_unauthenticated("identity", "http://192.168.2.15:5000/v2.0")

    yield _check_unauthenticated("identity", "http://192.168.2.15:5000")

    # compute (nova)
    # (not http://192.168.2.15:8774/v2.1/45f0ab9a4d35441fbbda2cf667f89404 as reported by keystone)
    yield _check_authenticated("compute", "http://192.168.2.15:8774/v2.1")

    # image (glance)
    yield _check_unauthenticated("image", "http://192.168.2.15:9292")

    # network (neutron)
    yield _check_unauthenticated("network", "http://192.168.2.15:9696")

    # volume (cinder v1)
    # (not http://192.168.2.15:8776/v1/45f0ab9a4d35441fbbda2cf667f89404 as reported by keystone)
    yield _check_authenticated("volume", "http://192.168.2.15:8776/v1")

    # volumev2 (cinder v2)
    # (not http://192.168.2.15:8776/v2/45f0ab9a4d35441fbbda2cf667f89404 as reported by keystone)
    yield _check_authenticated("volumev2", "http://192.168.2.15:8776/v2")

    # volumev3 (cinder v3)
    # (not http://192.168.2.15:8776/v3/45f0ab9a4d35441fbbda2cf667f89404 as reported by keystone)
    yield _check_authenticated("volumev3", "http://192.168.2.15:8776/v3")

    # metric (gnocchi)
    yield _check_unauthenticated("metric", "http://192.168.2.15:9696")

    # alarming (aodh)
    yield _check_authenticated("alarming", "http://192.168.2.15:8042")

    # metering (ceilometer)
    yield _check_authenticated("metering", "http://192.168.2.15:8777")

    # object-store (swift)
    # (not http://192.168.2.15:8080/v1/AUTH_45f0ab9a4d35441fbbda2cf667f89404 as reported by keystone)
    yield _check_authenticated("object-store", "http://192.168.2.15:8080/v1")

if __name__ == '__main__':
    main()
    reactor.run()
