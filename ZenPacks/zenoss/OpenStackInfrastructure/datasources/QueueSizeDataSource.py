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

from zope.component import adapts, getUtility
from zope.interface import implements

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import (
    PythonDataSource, PythonDataSourcePlugin, PythonDataSourceInfo,
    IPythonDataSourceInfo)

from ZenPacks.zenoss.OpenStackInfrastructure.utils import add_local_lib_path
add_local_lib_path()

from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema
from zenoss.protocols.twisted.amqp import AMQPFactory


class QueueSizeDataSource(PythonDataSource):
    '''
    Datasource used to check the number of messages in this device's ceilometer
    queues.
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack AMQP Queue Size',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 30

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'QueueSizeDataSource.QueueSizeDataSourcePlugin'

    # QueueSizeDataSource
    _properties = PythonDataSource._properties + ()


class IQueueSizeDataSourceInfo(IPythonDataSourceInfo):
    '''
    API Info interface for IQueueSizeDataSource.
    '''

    pass


class QueueSizeDataSourceInfo(PythonDataSourceInfo):
    '''
    API Info adapter factory for QueueSizeDataSource.
    '''

    implements(IQueueSizeDataSourceInfo)
    adapts(QueueSizeDataSource)

    testable = False


class QueueSizeDataSourcePlugin(PythonDataSourcePlugin):
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
        )

    @classmethod
    def params(cls, datasource, context):
        return {}

    @inlineCallbacks
    def collect(self, config):
        log.debug("Collect for OpenStack AMQP Queue Size (%s)" % config.id)

        results = {}

        self._amqpConnectionInfo = getUtility(IAMQPConnectionInfo)
        self._queueSchema = getUtility(IQueueSchema)

        amqp = AMQPFactory(self._amqpConnectionInfo, self._queueSchema)
        yield amqp._onConnectionMade

        for queuename in ('$OpenStackInboundPerf', '$OpenStackInboundEvent',):
            queue = self._queueSchema.getQueue(queuename, replacements={'device': config.id})
            info = yield amqp.channel.queue_declare(queue=queue.name,
                                                    passive=True)

            try:
                results[queuename] = info.fields[1]

            except IndexError:
                pass

        defer.returnValue(results)

    def onSuccess(self, result, config):
        data = self.new_data()
        ds0 = config.datasources[0]

        queue_map = {
            'perfQueueCount': '$OpenStackInboundPerf',
            'eventQueueCount': '$OpenStackInboundEvent'
        }

        for point in ds0.points:
            if point.id not in queue_map:
                log.error("Queue datapoint '%s' is not supported" % point.id)
                continue

            if queue_map[point.id] not in result:
                log.error("No queue count available for %s" % queue_map[point.id])
                continue

            value = result[queue_map[point.id]]
            data['values'][ds0.component][point.id] = (value, 'N')

        return data
