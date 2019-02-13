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

import re

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks

from zope.component import adapts
from zope.interface import implements

from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.ZenEvents import ZenEventClasses
from Products.ZenUtils.Utils import prepId

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import (
    PythonDataSource, PythonDataSourcePlugin, PythonDataSourceInfo,
    IPythonDataSourceInfo)

from ZenPacks.zenoss.OpenStackInfrastructure.apiclients.exceptions import APIClientError
from ZenPacks.zenoss.OpenStackInfrastructure.hostmap import HostMap
from ZenPacks.zenoss.OpenStackInfrastructure.utils import result_errmsg, add_local_lib_path
add_local_lib_path()

from apiclients.txapiclient import NovaClient


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

    _properties = PythonDataSource._properties + ()


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
        'zOpenStackUserDomainName',
        'zOpenStackProjectDomainName',
        'zOpenStackAuthUrl',
        'zOpenStackHostMapToId',
        'zOpenStackHostMapSame',
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
        return {
            'host_mappings': dict(context.host_mappings)
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug("Collect for OpenStack Nova Service Status (%s)" % config.id)
        ds0 = config.datasources[0]

        nova = NovaClient(
            ds0.zCommandUsername,
            ds0.zCommandPassword,
            ds0.zOpenStackAuthUrl,
            ds0.zOpenStackProjectId,
            ds0.zOpenStackUserDomainName,
            ds0.zOpenStackProjectDomainName,
            ds0.zOpenStackRegionName)

        results = {}

        log.debug('Requesting services')
        # ---------------------------------------------------------------------
        # ZPS-5043
        # Skip over API errors if user has restricted access, else raise.
        # ---------------------------------------------------------------------
        try:
            result = yield nova.services()
        except APIClientError as ex:
            if "403 Forbidden" in ex.message:
                log.debug("OpenStack API: user lacks access to call: nova.services.")
                defer.returnValue(results)
            else:
                log.warning("OpenStack API: access issue: {}".format(ex))
                raise
        except Exception as ex:
            log.error("OpenStack API Error: {}".format(ex))
            raise
        else:
            results['services'] = result['services']
            yield self.preprocess_hosts(config, results)
            defer.returnValue(results)

    @inlineCallbacks
    def preprocess_hosts(self, config, results):
        # spin through the collected data, pre-processing all the fields
        # that reference hosts to have consistent host IDs, so that the
        # process() method does not have to worry about hostname -> ID
        # mapping at all.

        hostmap = HostMap()
        results['hostmap'] = hostmap

        ds0 = config.datasources[0]

        # load in previously modeled mappings..
        hostmap.thaw_mappings(ds0.params['host_mappings'])

        for service in results['services']:
            if 'host' in service:
                hostmap.add_hostref(service['host'], source="nova services")

        for mapping in ds0.zOpenStackHostMapToId:
            try:
                hostref, hostid = mapping.split("=")
                hostmap.assert_host_id(hostref, hostid)
            except Exception:
                log.error("Invalid value in zOpenStackHostMapToId: %s", mapping)

        for mapping in ds0.zOpenStackHostMapSame:
            try:
                hostref1, hostref2 = mapping.split("=")
                hostmap.assert_same_host(hostref1, hostref2, source='zOpenStackHostMapSame')
            except Exception:
                log.error("Invalid value in zOpenStackHostMapSame: %s", mapping)

        # generate host IDs
        yield hostmap.perform_mapping()

        # replace all references to hosts with their host IDs, so
        # process() doesn't have to think about this stuff.
        for service in results['services']:
            if 'host' in service:
                service['host'] = hostmap.get_hostid(service['host'])

        # Note: Normally, whenever using hostmap, we store the output of
        # freeze_mappings, so that any new mappings are persisted.  This
        # is not necessary in this case, because any new components found
        # by this task will not be stored in the database (because _add=False),
        # so their IDs don't especially matter.  The new full model run
        # will establish and store their proper IDs.

    def onSuccess(self, result, config):
        data = self.new_data()

        for service in result.get('services', {}):
            host_id = service['host']
            hostname = result['hostmap'].get_hostname_for_hostid(host_id)
            host_base_id = re.sub(r'^host-', '', host_id)

            service_id = prepId('service-{0}-{1}-{2}'.format(
                service.get('binary', ''),
                host_base_id,
                service.get('zone', '')))

            data['maps'].append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.NovaService',
                compname='',
                data=dict(
                    id=service_id,
                    _add=False,
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
                               (service['binary'], hostname, service['zone']),
                    'severity': ZenEventClasses.Clear,
                    'eventClassKey': 'openStackNovaServiceStatus',
                    })

            elif service['state'] == 'up':
                data['events'].append({
                    'device': config.id,
                    'component': service_id,
                    'summary': 'Service %s on host %s (Availabilty Zone %s) is now UP' %
                               (service['binary'], hostname, service['zone']),
                    'severity': ZenEventClasses.Clear,
                    'eventClassKey': 'openStackNovaServiceStatus',
                    })
            else:

                data['events'].append({
                    'device': config.id,
                    'component': service_id,
                    'summary': 'Service %s on host %s (Availabilty Zone %s) is now DOWN' %
                               (service['binary'], hostname, service['zone']),
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
            'eventClassKey': 'openstack-Failure',
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
            'eventClassKey': 'openstack-Failure',
            })

        return data
