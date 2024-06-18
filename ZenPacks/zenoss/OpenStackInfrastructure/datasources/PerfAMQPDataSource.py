##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.PerfAMQP')

from zope.component import adapts
from zope.interface import implements

from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.utils import ZuulMessageFactory as _t

from ZenPacks.zenoss.OpenStackInfrastructure.datasources.AMQPDataSource import (
    AMQPDataSource, AMQPDataSourceInfo,
    IAMQPDataSourceInfo)


class PerfAMQPDataSource(AMQPDataSource):
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

    # PerfAMQPDataSource
    meter = ''

    _properties = AMQPDataSource._properties + (
        {'id': 'meter', 'type': 'string'},
    )


class IPerfAMQPDataSourceInfo(IAMQPDataSourceInfo):
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

class PerfAMQPDataSourceInfo(AMQPDataSourceInfo):
    '''
    API Info adapter factory for PerfAMQPDataSource.
    '''

    implements(IPerfAMQPDataSourceInfo)
    adapts(PerfAMQPDataSource)

    cycletime = ProxyProperty('cycletime')

    testable = False

    meter = ProxyProperty('meter')
