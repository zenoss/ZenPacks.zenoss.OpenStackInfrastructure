##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.NeutronAgentStatus')

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


class NeutronAgentStatusDataSource(PythonDataSource):
    '''
    Datasource used to check the status of Neutron Agents via the neutron API
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack Neutron Agent Status',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 30

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'NeutronAgentStatusDataSource.NeutronAgentStatusDataSourcePlugin'

    # NeutronAgentStatusDataSource

    _properties = PythonDataSource._properties + ()


class INeutronAgentStatusDataSourceInfo(IPythonDataSourceInfo):
    '''
    API Info interface for INeutronAgentStatusDataSource.
    '''

    pass


class NeutronAgentStatusDataSourceInfo(PythonDataSourceInfo):
    '''
    API Info adapter factory for NeutronAgentStatusDataSource.
    '''

    implements(INeutronAgentStatusDataSourceInfo)
    adapts(NeutronAgentStatusDataSource)

    testable = False


class NeutronAgentStatusDataSourcePlugin(PythonDataSourcePlugin):
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
        log.debug("Collect for OpenStack Neutron Agent Status (%s)" % config.id)
        ds0 = config.datasources[0]

        client = APIClient(
            ds0.zCommandUsername,
            ds0.zCommandPassword,
            ds0.zOpenStackAuthUrl,
            ds0.zOpenStackProjectId)

        results = {}

        log.debug('Requesting agent-list')
        result = yield client.neutron_agents()
        results['agents'] = result['agents']

        defer.returnValue(results)

    def onSuccess(self, result, config):
        data = self.new_data()

        for agent in result['agents']:
            agent_id = prepId('agent-{0}'.format(agent['id']))

            data['maps'].append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.NeutronAgent',
                compname='',
                data=dict(
                    id=agent_id,
                    relname='components',
                    enabled=agent['admin_state_up'],
                    operStatus={
                        True: 'UP',
                        False: 'DOWN'
                    }.get(agent['alive'], 'UNKNOWN'),

                )))

            if not agent['admin_state_up']:
                data['events'].append({
                    'device': config.id,
                    'component': agent_id,
                    'summary': 'Neutron Agent %s on host %s is now ADMIN DOWN' %
                               (agent['binary'], agent['host']),
                    'severity': ZenEventClasses.Clear,
                    'eventClassKey': 'openStackNeutronAgentStatus',
                    })

            elif agent['alive']:
                data['events'].append({
                    'device': config.id,
                    'component': agent_id,
                    'summary': 'Neutron Agent %s on host %s is now UP' %
                               (agent['binary'], agent['host']),
                    'severity': ZenEventClasses.Clear,
                    'eventClassKey': 'openStackNeutronAgentStatus',
                    })
            else:

                data['events'].append({
                    'device': config.id,
                    'component': agent_id,
                    'summary': 'Neutron Agent %s on host %s is now DOWN' %
                               (agent['binary'], agent['host']),
                    'severity': ZenEventClasses.Error,
                    'eventClassKey': 'openStackNeutronAgentStatus',
                    })

        # Note: Technically, this event could be related to the neutron-server component(s)
        # for this region
        data['events'].append({
            'device': config.id,
            'summary': 'Neutron Agent Status Collector: successful collection',
            'severity': ZenEventClasses.Clear,
            'eventKey': 'openStackNeutronAgentCollectionError',
            'eventClassKey': 'openStackFailure',
            })

        return data

    def onError(self, result, config):
        errmsg = 'Neutron Agent Status Collector: %s' % result_errmsg(result)
        log.error('%s: %s', config.id, errmsg)

        data = self.new_data()

        # Note: Technically, this event could be related to the neutron-server component(s)
        # for this region
        data['events'].append({
            'device': config.id,
            'summary': errmsg,
            'severity': ZenEventClasses.Error,
            'eventKey': 'openStackNeutronAgentCollectionError',
            'eventClassKey': 'openStackFailure',
            })

        return data
