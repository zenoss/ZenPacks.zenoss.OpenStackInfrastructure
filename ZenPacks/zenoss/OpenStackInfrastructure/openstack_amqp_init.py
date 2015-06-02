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
from Products.Five import zcml

import Products.ZenMessaging.queuemessaging
from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema, IAMQPChannelAdapter
from zenoss.protocols.amqp import Publisher as BlockingPublisher

# Create all the AMQP exchanges we require.   This should be run before we try
# to have ceilometer send zenoss any events.

if __name__ == '__main__':
    zcml.load_config('meta.zcml', zope.component)
    zcml.load_config('configure.zcml', zope.component)
    zcml.load_config('configure.zcml', Products.ZenMessaging.queuemessaging)

    connectionInfo = getUtility(IAMQPConnectionInfo)
    queueSchema = getUtility(IQueueSchema)
    amqpClient = BlockingPublisher(connectionInfo, queueSchema)
    channel = amqpClient.getChannel()

    for exchange in ('$OpenStackInbound', '$OpenStackInboundHeartbeats',):
        exchangeConfig = queueSchema.getExchange(exchange)
        print "Verifying configuration of exchange '%s' (%s)" % (exchange, exchangeConfig.name) 

        # Declare the exchange to which the message is being sent
        getAdapter(channel, IAMQPChannelAdapter).declareExchange(exchangeConfig)

    amqpClient.close()

