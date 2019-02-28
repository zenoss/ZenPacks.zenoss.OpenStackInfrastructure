##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.HeartbeatsAMQP')

from twisted.internet.defer import succeed

from zope.component import adapts
from zope.interface import implements

from ZenPacks.zenoss.OpenStackInfrastructure.datasources.AMQPDataSource import (
    AMQPDataSource, AMQPDataSourcePlugin, AMQPDataSourceInfo,
    IAMQPDataSourceInfo)


class HeartbeatsAMQPDataSource(AMQPDataSource):
    '''This datasource is deprecated and does nothing.'''
    enabled = False

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack Ceilometer Heartbeats AMQP',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 30

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'HeartbeatsAMQPDataSource.HeartbeatsAMQPDataSourcePlugin'

    # HeartbeatsAMQPDataSource

    _properties = AMQPDataSource._properties + ()


class IHeartbeatsAMQPDataSourceInfo(IAMQPDataSourceInfo):
    '''
    API Info interface for IHeartbeatsAMQPDataSource.
    '''

    pass


class HeartbeatsAMQPDataSourceInfo(AMQPDataSourceInfo):
    '''
    API Info adapter factory for HeartbeatsAMQPDataSource.
    '''

    implements(IHeartbeatsAMQPDataSourceInfo)
    adapts(HeartbeatsAMQPDataSource)

    testable = False


class HeartbeatsAMQPDataSourcePlugin(AMQPDataSourcePlugin):
    failure_eventClassKey = 'openStackCeilometerHeartbeat'

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
            datasource.plugin_classname
        )

    def collect(self, config):
        return succeed(None)

    def processMessage(self, device_id, message, contentbody):
        return
