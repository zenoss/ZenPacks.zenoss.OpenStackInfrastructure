##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013-2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


from . import schema

import logging
LOG = logging.getLogger('zen.OpenStackInfrastructureEndpoint')

from zope.component import getUtility
from zenoss.protocols.queueschema import substitute_replacements
from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema
from zenoss.protocols.amqp import Publisher as BlockingPublisher
from amqplib.client_0_8.exceptions import AMQPChannelException
from OFS.interfaces import IObjectWillBeAddedEvent
from BTrees.OOBTree import OOBTree


class Endpoint(schema.Endpoint):

    neutron_ini = {}

    def hosts(self):
        return self.getDeviceComponents(type="OpenStackInfrastructureHost")

    def region(self):
        return self.getDeviceComponents(type="OpenStackInfrastructureRegion")[0]

    def get_maintain_proxydevices(self):
        from ZenPacks.zenoss.OpenStackInfrastructure.DeviceProxyComponent \
            import DeviceProxyComponent
        for meta_type in DeviceProxyComponent.deviceproxy_meta_types():
            for component in self.getDeviceComponents(type=meta_type):
                if component.need_maintenance():
                    return False

        return True

    def set_maintain_proxydevices(self, arg):
        from ZenPacks.zenoss.OpenStackInfrastructure.DeviceProxyComponent \
            import DeviceProxyComponent
        for meta_type in DeviceProxyComponent.deviceproxy_meta_types():
            for component in self.getDeviceComponents(type=meta_type):
                component.maintain_proxy_device()

        return True

    def set_neutron_ini(self, values):
        if type(self.neutron_ini) == dict:
            self.neutron_ini = OOBTree()

        changed = set()
        for k, v in values.iteritems():
            if k not in self.neutron_ini or self.neutron_ini[k] != v:
                self.neutron_ini[k] = v
                changed.add(k)

        if changed:
            LOG.info("The following INI values have changed: %s" % changed)
            LOG.info("Rebuilding neutron core integration keys.")
            from ZenPacks.zenoss.OpenStackInfrastructure.neutron_integration \
                import reindex_core_components
            reindex_core_components(self.dmd)

    def get_neutron_ini(self):
        return dict(self.neutron_ini)

    def ini_get(self, *args):
        return self.neutron_ini.get(*args)


# Clean up any AMQP queues we may have created for this device.
def onDeviceDeleted(object, event):
    if not IObjectWillBeAddedEvent.providedBy(event):
        connectionInfo = getUtility(IAMQPConnectionInfo)
        queueSchema = getUtility(IQueueSchema)

        # For some reason, if an error gets thrown by queue_delete, it seems
        # to break the connection, so we'll just use a separate connection
        # for each call to it.
        for queue in ('$OpenStackInboundEvent', '$OpenStackInboundPerf'):
            queueName = substitute_replacements(queueSchema._queue_nodes[queue].name,
                                                {'device': object.id})

            amqpClient = BlockingPublisher(connectionInfo, queueSchema)
            channel = amqpClient.getChannel()
            try:
                LOG.debug("Removing AMQP queue %s" % queueName)
                channel.queue_delete(queueName)
                LOG.info("Removed AMQP queue %s successfully." % queueName)
            except AMQPChannelException, e:
                # if the queue doesn't exist, don't worry about it.
                if e.amqp_reply_code == 404:
                    LOG.debug('Queue %s did not exist', queueName)
                else:
                    LOG.exception(e)

            amqpClient.close()
