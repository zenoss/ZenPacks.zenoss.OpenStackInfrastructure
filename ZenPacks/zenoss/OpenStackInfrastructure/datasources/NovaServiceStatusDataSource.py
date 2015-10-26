##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.NovaServiceStatus')

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks

from zope.component import adapts
from zope.interface import implements

from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.ZenEvents import ZenEventClasses

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import (
    PythonDataSource, PythonDataSourcePlugin, PythonDataSourceInfo,
    IPythonDataSourceInfo)

from Products.ZenUtils.Utils import prepId
from ZenPacks.zenoss.OpenStackInfrastructure.utils import result_errmsg, add_local_lib_path
add_local_lib_path()

from apiclients.txapiclient import APIClient


class NovaServiceStatusDataSource(PythonDataSource):
    '''
    Datasource used to check the status of nova services via the nova API
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack Nova Service Status',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 30

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'NovaServiceStatusDataSource.NovaServiceStatusDataSourcePlugin'

    # NovaServiceStatusDataSource

    _properties = PythonDataSource._properties + ( )


class INovaServiceStatusDataSourceInfo(IPythonDataSourceInfo):
    '''
    API Info interface for INovaServiceStatusDataSource.
    '''

    pass


class NovaServiceStatusDataSourceInfo(PythonDataSourceInfo):
    '''
    API Info adapter factory for NovaServiceStatusDataSource.
    '''

    implements(INovaServiceStatusDataSourceInfo)
    adapts(NovaServiceStatusDataSource)

    testable = False


class NovaServiceStatusDataSourcePlugin(PythonDataSourcePlugin):
    proxy_attributes = (
        'zOpenStackRegionName',
        'zCommandUsername',
        'zCommandPassword',
        'zOpenStackProjectId',
        'zOpenStackAuthUrl',
    )

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
        )

    @classmethod
    def params(cls, datasource, context):
        return {}

    @inlineCallbacks
    def collect(self, config):
        log.debug("Collect for OpenStack Nova Service Status (%s)" % config.id)
        ds0 = config.datasources[0]

        client = APIClient(
            ds0.zCommandUsername,
            ds0.zCommandPassword,
            ds0.zOpenStackAuthUrl,
            ds0.zOpenStackProjectId,
            ds0.zOpenStackRegionName)

        results = {}

        log.debug('Requesting services')
        result = yield client.nova_services()
        results['services'] = result['services']

        defer.returnValue(results)

    def onSuccess(self, result, config):
        data = self.new_data()

        for service in result['services']:
            service_id = prepId('service-{0}-{1}-{2}'.format(
                service['binary'], service['host'], service['zone']))

            data['maps'].append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.NovaService',
                compname='',
                data=dict(
                    id=service_id,
                    relname='components',
                    enabled={
                        'enabled': True,
                        'disabled': False
                    }.get(service['status'], False),
                    operStatus={
                        'up': 'UP',
                        'down': 'DOWN'
                    }.get(service['state'], 'UNKNOWN'),
                )))

            if service['status'] == 'disabled':
                data['events'].append({
                    'device': config.id,
                    'component': service_id,
                    'summary': 'Service %s on host %s (Availabilty Zone %s) is now DISABLED' %
                               (service['binary'], service['host'], service['zone']),
                    'severity': ZenEventClasses.Clear,
                    'eventClassKey': 'openStackNovaServiceStatus',
                    })

            elif service['state'] == 'up':
                data['events'].append({
                    'device': config.id,
                    'component': service_id,
                    'summary': 'Service %s on host %s (Availabilty Zone %s) is now UP' %
                               (service['binary'], service['host'], service['zone']),
                    'severity': ZenEventClasses.Clear,
                    'eventClassKey': 'openStackNovaServiceStatus',
                    })
            else:

                data['events'].append({
                    'device': config.id,
                    'component': service_id,
                    'summary': 'Service %s on host %s (Availabilty Zone %s) is now DOWN' %
                               (service['binary'], service['host'], service['zone']),
                    'severity': ZenEventClasses.Error,
                    'eventClassKey': 'openStackNovaServiceStatus',
                    })

        # Note: Technically, this event could be related to the nova-api component(s)
        # for this region
        data['events'].append({
            'device': config.id,
            'summary': 'Nova Status Collector: successful collection',
            'severity': ZenEventClasses.Clear,
            'eventKey': 'openStackNovaServiceCollectionError',
            'eventClassKey': 'openstackRestored',
            })

        return data

    def onError(self, result, config):
        errmsg = 'Nova Status Collector: %s' % result_errmsg(result)
        log.error('%s: %s', config.id, errmsg)

        data = self.new_data()

        # Note: Technically, this event could be related to the nova-api component(s)
        # for this region
        data['events'].append({
            'device': config.id,
            'summary': errmsg,
            'severity': ZenEventClasses.Error,
            'eventKey': 'openStackNovaServiceCollectionError',
            'eventClassKey': 'openStackFailure',
            })

        return data
