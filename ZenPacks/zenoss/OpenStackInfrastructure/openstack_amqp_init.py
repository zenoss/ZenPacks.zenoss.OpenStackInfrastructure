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

import logging
log = logging.getLogger('zen.OpenStack.amqp_init')

import Globals
from Products.ZenUtils.Utils import unused
unused(Globals)

import zope.component
from zope.component import getUtility, getAdapter
from twisted.internet.defer import inlineCallbacks
from Products.Five import zcml

import Products.ZenMessaging.queuemessaging
from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema, IAMQPChannelAdapter
from zenoss.protocols.twisted.amqp import AMQPFactory


class OpenStackAMQPInit(object):

    # Create all the AMQP exchanges we require.   This should be run before we try
    # to have ceilometer send zenoss any events.

    @inlineCallbacks
    def go(self):

        zcml.load_config('configure.zcml', zope.component)
        zcml.load_config('configure.zcml', Products.ZenMessaging.queuemessaging)

        amqpConnectionInfo = getUtility(IAMQPConnectionInfo)
        queueSchema = getUtility(IQueueSchema)

        amqp = AMQPFactory(amqpConnectionInfo, queueSchema)
        yield amqp._onConnectionMade

        channel = amqp.channel

        for exchange in ('$OpenStackInbound', '$OpenStackInboundHeartbeats',):
            exchangeConfig = queueSchema.getExchange(exchange)
            print "Verifying configuration of exchange '%s' (%s)" % (exchange, exchangeConfig.name) 

            # Declare the exchange to which the message is being sent
            yield getAdapter(channel, IAMQPChannelAdapter).declareExchange(exchangeConfig)

        # Shut down, we're done.
        if reactor.running:
            reactor.stop()


if __name__ == '__main__':
    from twisted.internet import reactor

    amqp_init = OpenStackAMQPInit()
    amqp_init.go()
    reactor.run()
