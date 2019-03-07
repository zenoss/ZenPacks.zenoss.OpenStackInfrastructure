##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.QueueSizeStatus')

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks

from zope.component import adapts, getUtility
from zope.interface import implements

from Products.ZenEvents import ZenEventClasses

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import (
    PythonDataSource, PythonDataSourcePlugin, PythonDataSourceInfo,
    IPythonDataSourceInfo)

from ZenPacks.zenoss.OpenStackInfrastructure.utils import add_local_lib_path, result_errmsg
add_local_lib_path()

from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema
from zenoss.protocols.twisted.amqp import AMQPFactory
import txamqp.client

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


# Persistent state
# Technically, we could share the same client for all devices, but
# in the interest of keeping things simple and consistent with the
# other datasources..
amqp_client = {}                     # amqp_client[device.id] = AMQClient object


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

        # reuse existing connectio if there is one.
        if config.id in amqp_client and amqp_client[config.id]:
            amqp = amqp_client[config.id]
        else:
            amqp = AMQPFactory(self._amqpConnectionInfo, self._queueSchema)
            yield amqp._onConnectionMade
            amqp_client[config.id] = amqp

        for queuename in ('$OpenStackInboundPerf', '$OpenStackInboundEvent',):
            queue = self._queueSchema.getQueue(queuename, replacements={'device': config.id})
            try:
                info = yield amqp.channel.queue_declare(queue=queue.name,
                                                        passive=True)
                results[queuename] = info.fields[1]

            except txamqp.client.Closed, e:
                log.info("Unable to determine queue size for %s (queue does not exist)" % queue.name)
                pass

            except Exception, e:
                log.info("Unable to determine queue size for %s (%s)" % (queue.name, e))
                pass

        defer.returnValue(results)

    def _disconnect_amqp_client(self, config_id):
        if config_id in amqp_client and amqp_client[config_id]:
            amqp = amqp_client[config_id]
            amqp.disconnect()
            amqp.shutdown()
            del amqp_client[config_id]

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
                log.error("No queue count available for %s %s" % (config.id, queue_map[point.id]))
                continue

            value = result[queue_map[point.id]]
            data['values'][ds0.component][point.id] = (value, 'N')

        if len(data['values']):
            data['events'].append({
                'device': config.id,
                'component': ds0.component,
                'summary': 'OpenStack AMQP QueueSize: successful collection',
                'severity': ZenEventClasses.Clear,
                'eventKey': 'openstackCeilometerAMQPCollection',
                'eventClassKey': 'openstack-QueueSize',
                })

        return data

    def onError(self, result, config):
        # just in case some error we don't recover from is occurring, throw
        # out the connection.
        self._disconnect_amqp_client(config.id)

        errmsg = 'OpenStack AMQP QueueSize: %s' % result_errmsg(result)
        log.error('%s: %s', config.id, errmsg)

        data = self.new_data()
        data['events'].append({
            'device': config.id,
            'summary': errmsg,
            'severity': ZenEventClasses.Error,
            'eventKey': 'openstackCeilometerAMQPCollection',
            'eventClassKey': 'openstack-QueueSize',
            })

        return data

    def cleanup(self, config):
        log.info("Disconnecting any open AMQP connections for OpenStack AMQP QueueDataSource (%s)" % config.id)

        self._disconnect_amqp_client(config.id)
