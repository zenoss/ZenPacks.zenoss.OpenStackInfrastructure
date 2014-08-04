#!/usr/bin/env python
###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2014, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

import json
import logging
log = logging.getLogger('ZenPacks.zenoss.OpenStack.poll_openstack_amqp')

from collections import defaultdict

import Globals
from Products.ZenUtils.Utils import unused
unused(Globals)

from ZenPacks.zenoss.OpenStack.utils import add_local_lib_path
add_local_lib_path()

from os.path import join as pathjoin, dirname
from Products.Five import zcml
from twisted.internet import defer, reactor, protocol
from zope.component import getUtility
from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema
from zenoss.protocols.twisted.amqp import AMQPFactory
from pprint import pprint

import txamqp
from txamqp.protocol import AMQClient, TwistedDelegate


class OpenStackAMQPPoller(object):

    def __init__(self):
        self.connnector = None

        import zope.component
        zcml.load_config('configure.zcml', zope.component)
        import Products.ZenMessaging.queuemessaging
        zcml.load_config('configure.zcml', Products.ZenMessaging.queuemessaging)
        self._amqpConnectionInfo = getUtility(IAMQPConnectionInfo)
        self._queueSchema = getUtility(IQueueSchema)

    # @defer.inlineCallbacks
    # def connect(self, host=None, port=None, user=None, password=None, vhost=None,
    #             heartbeat=None):
    #     host = host or self.host
    #     port = port or self.port
    #     user = user or self.user
    #     password = password or self.password
    #     vhost = vhost or self.vhost
    #     heartbeat = heartbeat or self.heartbeat

    #     import zenoss.protocols.twisted.amqp
    #     amqp_specfile = pathjoin(dirname(zenoss.protocols.twisted.amqp.__file__), 'amqp0-9-1.xml')

    #     delegate = TwistedDelegate()
    #     onConn = defer.Deferred()
    #     p = AMQClient(delegate, vhost, txamqp.spec.load(amqp_specfile), heartbeat=heartbeat)
    #     f = protocol._InstanceFactory(reactor, p, onConn)
    #     c = reactor.connectTCP(host, port, f)

    #     def errb(thefailure):
    #         log.error("failed to connect to AMQP host: %s, port: %s"
    #                   " of the %s AMQP broker.  failure: %r" %
    #                   (host, port, self.broker, thefailure,))
    #         thefailure.raiseException()
    #     onConn.addErrback(errb)

    #     self.connector = (c)
    #     client = yield onConn

    #     yield client.authenticate(user, password, mechanism='PLAIN')

    #     defer.returnValue(client)

    @defer.inlineCallbacks
    def disconnect(self):
        self.connector.disconnect()

    @defer.inlineCallbacks
    def getData(self):
        data = {}
        data['events'] = []
        data['values'] = defaultdict(dict)

        print "Connecting..."

        self.client = AMQPFactory(self._amqpConnectionInfo, self._queueSchema)
        queue = self._queueSchema.getQueue('$OpenStackInbound', replacements={'device': 'packstack1'})
        self.client.listen(queue, callback=self.processMessage)
        print "Listening..."

#       print "Disconnecting..."

#        yield self.disconnect()

        defer.returnValue(data)
        yield

    def processMessage(self, message):
        pprint(json.loads(message.content.body))

    # @defer.inlineCallbacks
    # def getData2(self):
    #     data = {}
    #     data['events'] = []
    #     data['values'] = defaultdict(dict)

    #     print "Connecting..."

    #     self.client = yield self.connect(host=self._amqpConnectionInfo.host,
    #                                      port=self._amqpConnectionInfo.port,
    #                                      user=self._amqpConnectionInfo.user,
    #                                      password=self._amqpConnectionInfo.password,
    #                                      vhost=self._amqpConnectionInfo.vhost,
    #                                      heartbeat=self._amqpConnectionInfo.amqpconnectionheartbeat)

    #     self.channel = yield self.client.channel(1)
    #     yield self.channel.channel_open()

    #     reply = yield channel.exchange_declare(ticket, exchange, type, passive, durable, auto_delete, internal, nowait, arguments)
    #     self.exchanges.append((channel,exchange))

    #     import pdb; pdb.set_trace()

    #     print "Disconnecting..."

    #     yield self.disconnect()

    #     defer.returnValue(data)
    #     yield

    @defer.inlineCallbacks
    def run(self):
        data = None
        try:
            data = yield self.getData()
            data['events'].append(dict(
                severity=0,
                summary='OpenStack AMQP connectivity restored',
                eventKey='openStackAMQPFailure',
                eventClassKey='openStackAMQPRestored',
            ))
        except Exception, ex:
            data = dict(
                events=[dict(
                    severity=5,
                    summary='OpenStack AMQP failure: %s' % ex,
                    eventKey='openStackAMQPFailure',
                    eventClassKey='openStackAMQPFailure',
                )]
            )

        print json.dumps(data)

if __name__ == '__main__':

    poller = OpenStackAMQPPoller()

    def finished(result):
        log.debug(result)
        if reactor.running:
            reactor.stop()

    poller.run().addBoth(finished)
    reactor.run()
