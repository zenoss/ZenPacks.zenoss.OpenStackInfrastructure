##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2024, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################
from zope.component import adapts
from zope.interface import implements

from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.utils import ZuulMessageFactory as _t

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import (
    PythonDataSource, PythonDataSourcePlugin )

from Products.Zuul.infos.template import RRDDataSourceInfo
from Products.Zuul.interfaces import IRRDDataSourceInfo


class PerfAMQPDataSource(PythonDataSource):
    '''
    Datasource used to capture data and events shipped to us from OpenStack
    Ceilometer via AMQP.
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack Ceilometer Perf AMQP',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 300

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'PerfAMQPDataSource.PerfAMQPDataSourcePlugin'

    # PerfAMQPDataSource
    meter = ''

    _properties = PythonDataSource._properties + (
        {'id': 'meter', 'type': 'string'},
    )


class IPerfAMQPDataSourceInfo(IRRDDataSourceInfo):
    '''
    API Info interface for IPerfAMQPDataSource.
    '''

    meter = schema.TextLine(
        group=_t('OpenStack Ceilometer'),
        title=_t('meter Name'))

    cycletime = schema.TextLine(
        group=_t('OpenStack Ceilometer'),
        title=_t('Cycletime')
    )

class PerfAMQPDataSourceInfo(RRDDataSourceInfo):
    '''
    API Info adapter factory for PerfAMQPDataSource.
    '''

    implements(IPerfAMQPDataSourceInfo)
    adapts(PerfAMQPDataSource)

    cycletime = ProxyProperty('cycletime')

    testable = False

    meter = ProxyProperty('meter')


class PerfAMQPDataSourcePlugin(PythonDataSourcePlugin):
    """
    Deprecated. Needed to avoid errors in the log until zenopenstack migrates to its custom datasources.
    """
    proxy_attributes = ('resourceId')
    queue_name = "$OpenStackInboundPerf"
    failure_eventClassKey = 'PerfFailure'

    @classmethod
    def params(cls, datasource, context):
        return {
            'meter': datasource.talesEval(datasource.meter, context),
            'resourceId': context.resourceId,
            'component_meta_type': context.meta_type
        }
