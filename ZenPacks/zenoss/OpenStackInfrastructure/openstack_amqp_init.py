#!/usr/bin/env python
###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2014-2016, Zenoss Inc.
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

import os
import subprocess
import sys
import uuid

import transaction

import Globals
from Products.ZenUtils.Utils import unused
unused(Globals)

import zope.component
from zope.component import getUtility, getAdapter
from Products.Five import zcml

from Products.ZenUtils.ZenScriptBase import ZenScriptBase
import Products.ZenMessaging.queuemessaging
from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema, IAMQPChannelAdapter
from zenoss.protocols.amqp import Publisher as BlockingPublisher

try:
    import servicemigration as sm
    sm.require("1.0.0")
    VERSION5 = True
except ImportError:
    VERSION5 = False


def require_rabbitmq():
    print "Verifying rabbitmqctl access"
    try:
        with open(os.devnull, 'w') as devnull:
            subprocess.check_call(["sudo", "rabbitmqctl", "list_vhosts"], stdout=devnull)
    except subprocess.CalledProcessError, e:
        sys.exit("Unable to exceute rabbitmqctl (%s)\nPlease execute this command on the correct host." % e)


def create_exchanges():
    print "Verifying exchanges"

    # Create all the AMQP exchanges we require.   This should be run before we try
    # to have ceilometer send zenoss any events.
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


def create_default_credentials(dmd):
    print "Checking default credentials"
    dc = dmd.getObjByPath("Devices/OpenStack/Infrastructure")
    if not dc.getProperty('zOpenStackAMQPPassword'):
        print "Generating random default zOpenStackAMQPPassword"
        random_password = uuid.uuid4().bytes.encode("base64")[:15]
        dc.setZenProperty('zOpenStackAMQPPassword', random_password)


def provision_user(dmd):
    dc = dmd.getObjByPath("Devices/OpenStack/Infrastructure")
    user = dc.getZ('zOpenStackAMQPUsername')
    password = dc.getProperty('zOpenStackAMQPPassword')

    conninfo = getUtility(IAMQPConnectionInfo)
    vhost = conninfo.vhost

    if not [x for x in subprocess.check_output(['sudo', 'rabbitmqctl', 'list_users']).split("\n") if x.startswith(user + "\t")]:
        print "Adding user %s to rabbitmq" % user
        try:
            with open(os.devnull, 'w') as devnull:
                subprocess.check_call(['sudo', 'rabbitmqctl', 'add_user', user, password], stdout=devnull)
        except subprocess.CalledProcessError, e:
            sys.exit("Unable to exceute rabbitmqctl (%s)" % e)
    else:
        # Set the password (unconditionally)
        print "Updating user password"
        try:
            with open(os.devnull, 'w') as devnull:
                subprocess.check_call(['sudo', 'rabbitmqctl', 'change_password', user, password], stdout=devnull)
        except subprocess.CalledProcessError, e:
            sys.exit("Unable to exceute rabbitmqctl (%s)" % e)

    # Fix the user permissions, too, just in case.
    print "Verifying user permissions"
    try:
        with open(os.devnull, 'w') as devnull:
            subprocess.check_call(['sudo', 'rabbitmqctl', '-p', vhost, 'clear_permissions', user], stdout=devnull)
            subprocess.check_call(['sudo', 'rabbitmqctl', '-p', vhost, 'set_permissions', user, 'zenoss.openstack.*', 'zenoss.openstack.*', '^$'], stdout=devnull)
    except subprocess.CalledProcessError, e:
        sys.exit("Unable to exceute rabbitmqctl (%s)" % e)


if __name__ == '__main__':
    if not VERSION5:
        require_rabbitmq()
        create_exchanges()

    # Log into ZODB..
    try:
        script = ZenScriptBase()
        script.connect()
        dmd = script.dmd
    except Exception, e:
        sys.exit("Unable to connect to ZODB: %s" % e)

    create_default_credentials(dmd)

    if not VERSION5:
        provision_user(dmd)

    rabbit_ip = {}
    if VERSION5:
        from Products.ZenUtils.controlplane.application import getConnectionSettings
        from Products.ZenUtils.controlplane import ControlPlaneClient

        client = ControlPlaneClient(**getConnectionSettings())
        for svc_id in [x.id for x in client.queryServices() if x.name == 'RabbitMQ-Ceilometer']:
            svc = client.getService(svc_id)
            for ceil_endpoint in filter(lambda s: s['Name'] == 'rabbitmq_ceil', svc.getRawData()['Endpoints']):
                try:
                    ip = ceil_endpoint['AddressAssignment']['IPAddr']
                    collector = client.getService(svc.parentId).name

                    rabbit_ip[collector] = ip
                except Exception:
                    # no ip assignment or error determining what collector this is.
                    pass

    dc = dmd.getObjByPath("Devices/OpenStack/Infrastructure")

    transaction.commit()

    conninfo = getUtility(IAMQPConnectionInfo)
    if VERSION5:
        port = 55672
    else:
        port = conninfo.port

    print """
OpenStack Configuration
-----------------------
Add the following configuration to ceilometer.conf on all openstack nodes:
For Liberty and prior versions,

    [DEFAULT]
    dispatcher=zenoss

For Mitaka and newer versions,

    [DEFAULT]
    meter_dispatchers = zenoss
    event_dispatchers = zenoss

For all versions,
    [notification]
    store_events=True

    [dispatcher_zenoss]

    zenoss_device = [device that the openstack environment is registered as in zenoss]

    amqp_port = {AMQP_PORT}
    amqp_userid = {AMQP_USERID}
    amqp_password = {AMQP_PASSWORD}
    amqp_virtual_host = {AMQP_VIRTUAL_HOST}
    amqp_hostname = [The correct AMQP system IP or hostname (see below)]

 """.format(
        AMQP_PORT=port,
        AMQP_USERID=dc.getZ('zOpenStackAMQPUsername'),
        AMQP_PASSWORD=dc.getProperty('zOpenStackAMQPPassword'),
        AMQP_VIRTUAL_HOST=conninfo.vhost,
        )

    if VERSION5:
        if rabbit_ip:
            print "* The correct IP address will depend upon the collector for the device:"
            for collector_name, ip in rabbit_ip.iteritems():
                print "  %s: %s" % (collector_name, ip)
        else:
            print "* No RabbitMQ-Ceilometer IP address assignments could be found."
            print "  - To correct this, in Control Center, click 'Assign' for the"
            print "    unassigned RabbitMQ-Ceilometer IP assignments."
    else:
        print """
 * Your current Zenoss amqp_hostname is set to '{AMQP_HOSTNAME}'.

  => If this is not the correct IP to access your rabbitmq server from
     external hosts, you must specify the proper IP for amqp_hostname
     in ceilometer.conf.
    """.format(AMQP_HOSTNAME=conninfo.host)
