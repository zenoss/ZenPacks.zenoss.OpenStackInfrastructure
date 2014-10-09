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

import sys
import json

from amqplib.client_0_8.connection import Connection
from amqplib.client_0_8.exceptions import AMQPChannelException

import Globals
from Products.ZenUtils.Utils import unused
unused(Globals)

from Products.ZenUtils.GlobalConfig import getGlobalConfiguration

def count_queues(channel, qnames):
    retMsg = []
    try:
        for qname in qnames:
            name, count, consumers = channel.queue_declare(qname,
                                                           passive=True)
            retMsg.append((name, count))
    except AMQPChannelException as ex:
        # this could happen if the queue is not available.
        # return an empty list
        return []

    return retMsg

def localhost_conn_chan():
    # zenoss amqp connection, channel
    global_conf = getGlobalConfiguration()
    hostname = global_conf.get('amqphost', 'localhost')
    port     = global_conf.get('amqpport', '5672')
    username = global_conf.get('amqpuser', 'zenoss')
    password = global_conf.get('amqppassword', 'zenoss')
    vhost    = global_conf.get('amqpvhost', '/zenoss')
    ssl      = global_conf.get('amqpusessl', '0')
    use_ssl  = True if ssl in ('1', 'True', 'true') else False

    conn = Connection(host="%s:%s" % (hostname, port),
                      userid=username,
                      password=password,
                      virtual_host=vhost,
                      ssl=use_ssl)
    channel = conn.channel()
    return conn, channel

def main():
    try:
        devicename = sys.argv[1]
    except ValueError:
        print >> sys.stderr, ("Usage: %s <devicename>") % sys.argv[0]
        sys.exit(1)

    # queue names we are interested in
    queue_names = []
    qname = 'zenoss.queues.openstack.ceilometer.' + devicename + '.event'
    queue_names.append(qname)
    qname = 'zenoss.queues.openstack.ceilometer.' + devicename + '.perf'
    queue_names.append(qname)

    conn, channel = localhost_conn_chan()
    with conn:
        with channel:
            msgs = count_queues(channel, queue_names)
            print json.dumps(msgs)

if __name__ == '__main__':
    main()