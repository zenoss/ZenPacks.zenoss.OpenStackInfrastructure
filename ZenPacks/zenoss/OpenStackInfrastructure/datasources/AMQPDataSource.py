##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.AMQP')

import zope.component
from zope.component import adapts
from zope.interface import implements

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSource 

from Products.Zuul.infos.template import RRDDataSourceInfo
from Products.Zuul.interfaces import IRRDDataSourceInfo


class AMQPDataSource(PythonDataSource):
    '''
    Datasource used to capture data and events shipped to us from OpenStack
    Ceilometer via AMQP.
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack Ceilometer AMQP',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 300


class IAMQPDataSourceInfo(IRRDDataSourceInfo):
    '''
    API Info interface for IAMQPDataSource.
    '''


class AMQPDataSourceInfo(RRDDataSourceInfo):
    '''
    API Info adapter factory for AMQPDataSource.
    '''

    implements(IAMQPDataSourceInfo)
    adapts(AMQPDataSource)

    testable = False
