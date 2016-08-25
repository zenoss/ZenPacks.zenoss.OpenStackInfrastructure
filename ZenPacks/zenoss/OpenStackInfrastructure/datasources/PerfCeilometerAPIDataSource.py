##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.PerfCeilometerAPI')

import os
import ast

from twisted.web import client as txwebclient

from twisted.internet import reactor, defer
from twisted.internet.defer import inlineCallbacks

from zope.component import adapts
from zope.interface import implements

from Products.ZenEvents import ZenEventClasses
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.utils import ZuulMessageFactory as _t

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import (
    PythonDataSource, PythonDataSourcePlugin, PythonDataSourceInfo,
    IPythonDataSourceInfo)

from ZenPacks.zenoss.OpenStackInfrastructure.utils import result_errmsg
from apiclients.txapiclient import APIClient


class ProxyWebClient(object):
    """Provide useful web methods with proxy."""

    def __init__(self, url, username=None, password=None):
        # get scheme used by url
        scheme, host, port, path = txwebclient._parse(url)
        envname = '%s_proxy' % scheme
        self.use_proxy = False
        self.proxy_host = None
        self.proxy_port = None
        if envname in os.environ.keys():
            proxy = os.environ.get('%s_proxy' % scheme)
            if proxy:
                # using proxy server
                # host:port identifies a proxy server
                # url is the actual target
                self.use_proxy = True
                scheme, host, port, path = txwebclient._parse(proxy)
                self.proxy_host = host
                self.proxy_port = port
                self.username = username
                self.password = password
        else:
            self.host = host
            self.port = port
        self.path = url
        self.url = url

    def get_page(self, headers={}, contextFactory=None, *args, **kwargs):
        scheme, _, _, _ = txwebclient._parse(self.url)
        factory = txwebclient.HTTPClientFactory(self.url)
        for k, v in headers.iteritems():
            factory.headers[k] = v.encode("utf-8")

        try:
            if scheme == 'https':
                from twisted.internet import ssl
                if contextFactory is None:
                    contextFactory = ssl.ClientContextFactory()
                if self.use_proxy:
                    reactor.connectSSL(self.proxy_host, self.proxy_port,
                                       factory, contextFactory)
                else:
                    reactor.connectSSL(self.host, self.port,
                                       factory, contextFactory)
            else:
                if self.use_proxy:
                    reactor.connectTCP(self.proxy_host, self.proxy_port, factory)
                else:
                    reactor.connectTCP(self.host, self.port, factory)
        except Exception, ex:
            code = getattr(ex, 'status', None)
            log.error('return code: %s, msg: %s', code, ex.message)

        return factory.deferred.addCallbacks(self.getdata, self.errdata)

    def getdata(self, data):
        return data

    def errdata(self, failure):
        log.error('%s: %s', 'PerfCeilometerAPIError', failure.getErrorMessage())
        return failure.getErrorMessage()


class PerfCeilometerAPIDataSource(PythonDataSource):
    '''
    Datasource used to capture datapoints from OpenStack Ceilometer.
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack Ceilometer Perf API',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 300

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'PerfCeilometerAPIDataSource.PerfCeilometerAPIDataSourcePlugin'

    # PerfCeilometerAPIDataSource
    metric = ''
    statistic = 'Average'

    _properties = PythonDataSource._properties + (
        {'id': 'metric', 'type': 'string'},
        {'id': 'statistic', 'type': 'string'},
        )


class IPerfCeilometerAPIDataSourceInfo(IPythonDataSourceInfo):
    '''
    API Info interface for PerfCeilometerAPI.
    '''

    metric = schema.TextLine(
        group=_t('OpenStack Ceilometer Perf API'),
        title=_t('Metric Name'))

    statistic = schema.TextLine(
        group=_t('OpenStack Ceilometer Perf API'),
        title=_t('Statistic'))


class PerfCeilometerAPIDataSourceInfo(PythonDataSourceInfo):
    '''
    API Info adapter factory for PerfCeilometerAPIDataSource.
    '''

    implements(IPerfCeilometerAPIDataSourceInfo)
    adapts(PerfCeilometerAPIDataSource)

    testable = False

    statistic = ProxyProperty('statistic')


class PerfCeilometerAPIDataSourcePlugin(PythonDataSourcePlugin):
    proxy_attributes = ('zCommandUsername',
                        'zCommandPassword',
                        'zOpenStackAuthUrl',
                        'zPerfCeilometerAPIUrl',
                        'zOpenStackProjectId',
                        'zOpenStackRegionName',
                        'resourceId')

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
            datasource.rrdTemplate().id,
            datasource.plugin_classname,
            )

    @classmethod
    def params(cls, datasource, context):
        return {
            'metric':    datasource.talesEval(datasource.metric, context),
            'statistic': datasource.talesEval(datasource.statistic, context),
            }

    @inlineCallbacks
    def collect(self, config):
        log.debug("Collect for OpenStack")

        ds0 = config.datasources[0]

        client = APIClient(
            username=ds0.zCommandUsername,
            password=ds0.zCommandPassword,
            auth_url=ds0.zOpenStackAuthUrl,
            project_id=ds0.zOpenStackProjectId,
        )

        results = []
        for ds in config.datasources:
            query = dict(
                field='resource_id',
                op='eq',
                value=ds.resourceId,
                type='string'
            )
            result = yield client.ceilometer_statistics(
                meter_name=ds.params['metric'],
                queries=[query]
            )
            results.append((ds, result))

        defer.returnValue(results)

    def onSuccess(self, results, config):
        data = self.new_data()

        for ds, result in results:

            if len(result) == 0:
                value = '0'
            elif ds.params['metric'] == 'cpu_util':
                value = str(round(result[0]['avg'], 2))
            elif ds.params['metric'] == 'cpu':
                # convert nano seconds to seconds
                value = str(float(result[0]['avg']) * 1.0e-9)
            elif ds.params['metric'] == 'disk.read.requests':
                value = str(result[0]['avg'])
            elif ds.params['metric'] == 'disk.write.requests':
                value = str(result[0]['avg'])
            elif ds.params['metric'] == 'disk.read.requests.rate':
                value = str(result[0]['avg'])
            elif ds.params['metric'] == 'disk.write.requests.rate':
                value = str(result[0]['avg'])
            elif ds.params['metric'] == 'disk.read.bytes':
                # convert B to KB
                value = str(result[0]['avg'] * 1.0e-3)
            elif ds.params['metric'] == 'disk.write.bytes':
                # convert B to KB
                value = str(result[0]['avg'] * 1.0e-3)
            elif ds.params['metric'] == 'disk.read.bytes.rate':
                # convert B to KB
                value = str(result[0]['avg'] * 1.0e-3)
            elif ds.params['metric'] == 'disk.write.bytes.rate':
                value = str(result[0]['avg'] * 1.0e-3)
            elif ds.params['metric'] == 'network.incoming.packets':
                value = str(result[0]['avg'] * 1.0e-3)
            elif ds.params['metric'] == 'network.outpoing.packets':
                value = str(result[0]['avg'] * 1.0e-3)
            elif ds.params['metric'] == 'network.incoming.packets.rate':
                value = str(result[0]['avg'] * 1.0e-3)
            elif ds.params['metric'] == 'network.outpoing.packets.rate':
                value = str(result[0]['avg'] * 1.0e-3)
            elif ds.params['metric'] == 'network.incoming.bytes':
                # convert B to KB
                value = str(result[0]['avg'] * 1.0e-3)
            elif ds.params['metric'] == 'network.outpoing.bytes':
                # convert B to KB
                value = str(result[0]['avg'] * 1.0e-3)
            elif ds.params['metric'] == 'network.incoming.bytes.rate':
                value = str(result[0]['avg'] * 1.0e-3)
            elif ds.params['metric'] == 'network.outpoing.bytes.rate':
                value = str(result[0]['avg'] * 1.0e-3)
            else:
                value = '0'
            data['values'][ds.component][ds.datasource] = (value, 'N')

        data['events'].append({
            'device': config.id,
            'component': ds.component,
            'summary': 'OpenStack Ceilometer: successful %s collection' % ds.params['metric'],
            'severity': ZenEventClasses.Clear,
            'eventKey': 'PerfCeilometerAPICollection',
            'eventClassKey': 'PerfCeilometerAPISuccess',
            })
        return data

    def onError(self, result, config):
        errmsg = 'OpenStack: %s' % result_errmsg(result)
        log.error('%s: %s', config.id, errmsg)

        data = self.new_data()
        data['events'].append({
            'device': config.id,
            'summary': errmsg,
            'severity': ZenEventClasses.Error,
            'eventKey': 'PerfCeilometerAPICollection',
            'eventClassKey': 'PerfCeilometerAPIError',
            })

        return data
