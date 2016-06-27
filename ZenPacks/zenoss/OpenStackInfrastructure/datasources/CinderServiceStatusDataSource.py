##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.CinderServiceStatus')

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


class CinderServiceStatusDataSource(PythonDataSource):
    '''
    Datasource used to check the status of Cinder services via the Cinder API
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack Cinder Service Status',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 30

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'CinderServiceStatusDataSource.CinderServiceStatusDataSourcePlugin'

    # CinderServiceStatusDataSource

    _properties = PythonDataSource._properties + ()


class ICinderServiceStatusDataSourceInfo(IPythonDataSourceInfo):
    '''
    API Info interface for ICinderServiceStatusDataSource.
    '''

    pass


class CinderServiceStatusDataSourceInfo(PythonDataSourceInfo):
    '''
    API Info adapter factory for CinderServiceStatusDataSource.
    '''

    implements(ICinderServiceStatusDataSourceInfo)
    adapts(CinderServiceStatusDataSource)

    testable = False


class CinderServiceStatusDataSourcePlugin(PythonDataSourcePlugin):
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
        log.debug("Collect for OpenStack Cinder Service Status (%s)" % config.id)
        ds0 = config.datasources[0]

        client = APIClient(
            ds0.zCommandUsername,
            ds0.zCommandPassword,
            ds0.zOpenStackAuthUrl,
            ds0.zOpenStackProjectId,
            ds0.zOpenStackRegionName)

        results = {}

        log.debug('Requesting services')
        result = yield client.cinder_services()
        results['services'] = result['services']

        results['nova_url'] = yield client.nova_url()

        defer.returnValue(results)

    def onSuccess(self, result, config):
        data = self.new_data()

        for service in result['services']:
            # on some OpenStack hosts, the host for
            # cinder-volume has pool name, lvm, attached to it, like:
            # u'host': u'liberty-allinone.zenoss.loc@lvm', which isn't correct
            # whereas for cinder-backup and cinder-scheduler host looks like:
            # u'host': u'liberty-allinone.zenoss.loc', which is correct
            # remove '@lvm' from host name only if hostname has it
            host = service['host']
            if host.endswith('@lvm'):
                host = host[:host.index('@lvm')]
            service_id = prepId('service-{0}-{1}-{2}'.format(
                service['binary'], host, service['zone']))

            data['maps'].append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.CinderService',
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
                    'eventClassKey': 'openStackCinderServiceStatus',
                    })

            elif service['state'] == 'up':
                data['events'].append({
                    'device': config.id,
                    'component': service_id,
                    'summary': 'Service %s on host %s (Availabilty Zone %s) is now UP' %
                               (service['binary'], service['host'], service['zone']),
                    'severity': ZenEventClasses.Clear,
                    'eventClassKey': 'openStackCinderServiceStatus',
                    })
            else:

                data['events'].append({
                    'device': config.id,
                    'component': service_id,
                    'summary': 'Service %s on host %s (Availabilty Zone %s) is now DOWN' %
                               (service['binary'], service['host'], service['zone']),
                    'severity': ZenEventClasses.Error,
                    'eventClassKey': 'openStackCinderServiceStatus',
                    })

        # Note: Technically, this event could be related to the Cinder-api component(s)
        # for this region
        data['events'].append({
            'device': config.id,
            'summary': 'Cinder Status Collector: successful collection',
            'severity': ZenEventClasses.Clear,
            'eventKey': 'openStackCinderServiceCollectionError',
            'eventClassKey': 'openStackFailure',
            })

        return data

    def onError(self, result, config):
        errmsg = 'Cinder Status Collector: %s' % result_errmsg(result)
        log.error('%s: %s', config.id, errmsg)

        data = self.new_data()

        # Note: Technically, this event could be related to the Cinder-api component(s)
        # for this region
        data['events'].append({
            'device': config.id,
            'summary': errmsg,
            'severity': ZenEventClasses.Error,
            'eventKey': 'openStackCinderServiceCollectionError',
            'eventClassKey': 'openStackFailure',
            })

        return data
