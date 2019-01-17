#!/usr/bin/env python
##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


import Globals

import logging
log = logging.getLogger('zen.sim_events')

import datetime
import json
import yaml
import uuid
import random

from twisted.internet import reactor, defer
from twisted.internet.task import LoopingCall

from Products.Five import zcml
import zope.component
from zope.component import getUtility

from Products.ZenUtils.Utils import unused
from Products.ZenUtils.ZenScriptBase import ZenScriptBase
from Products.ZenUtils.ZenTales import talesEval, talesEvalStr
import Products.ZenMessaging.queuemessaging
from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema
from zenoss.protocols.twisted.amqp import AMQPFactory

unused(Globals)


def sleep(secs):
    d = defer.Deferred()
    reactor.callLater(secs, d.callback, None)
    return d


class SimEvents(ZenScriptBase):

    def buildOptions(self):
        super(SimEvents, self).buildOptions()

        self.parser.add_option(
            '-d', dest='device',
            help='Device Name',
            default='test_ostack')

        self.parser.add_option(
            '--nottl', dest='no_ttl',
            default=False, action='store_true',
            help="Disable TTL on generated messages (prevent rabbitmq's expiration, force zenpython to consume them all)")

        self.parser.add_option(
            '--delete_create_every', dest='delete_create_every',
            help='Delete and re-create a random instance every x seconds',
            type='int',
            default=60)

        self.parser.add_option(
            '--powercycle_every', dest='powercycle_every',
            help='Power Cycle (off/on) a random instance every x seconds',
            type='int',
            default=60)

        self.parser.add_option(
            '--suspend_every', dest='suspend_every',
            help='Suspend, then resume a random instance every x seconds',
            type='int',
            default=60)

        self.parser.add_option(
            '--reboot_every', dest='reboot_every',
            help='Reboot a random instance every x seconds',
            type='int',
            default=60)

    @defer.inlineCallbacks
    def run(self):
        self.connect()

        self.load_config_and_model()
        self.connect_to_amqp()

        deferreds = []
        loop = LoopingCall(self.send_instance_delete_create)
        deferreds.append(
            loop.start(self.options.delete_create_every, now=True))

        yield sleep(10)

        loop = LoopingCall(self.send_instance_powercycle)
        deferreds.append(
            loop.start(self.options.powercycle_every, now=True))

        yield sleep(10)

        loop = LoopingCall(self.send_instance_suspend_resume)
        deferreds.append(
            loop.start(self.options.suspend_every, now=True))

        yield sleep(10)

        loop = LoopingCall(self.send_instance_reboot)
        deferreds.append(
            loop.start(self.options.reboot_every, now=True))

        yield defer.DeferredList(deferreds)

    @defer.inlineCallbacks
    def send_instance_delete_create(self):
        instance = random.choice(self.model['instances'])

        for routing_key, payload in self.get_instance_events('instance_delete', instance):
            yield self.amqp_send(routing_key, payload)

        for routing_key, payload in self.get_instance_events('instance_creation', instance):
            yield self.amqp_send(routing_key, payload)

    @defer.inlineCallbacks
    def send_instance_powercycle(self):
        instance = random.choice(self.model['instances'])

        for routing_key, payload in self.get_instance_events('instance_power_off', instance):
            yield self.amqp_send(routing_key, payload)

        for routing_key, payload in self.get_instance_events('instance_power_on', instance):
            yield self.amqp_send(routing_key, payload)

    @defer.inlineCallbacks
    def send_instance_suspend_resume(self):
        instance = random.choice(self.model['instances'])

        for routing_key, payload in self.get_instance_events('instance_suspend_resume', instance):
            yield self.amqp_send(routing_key, payload)

    @defer.inlineCallbacks
    def send_instance_reboot(self):
        instance = random.choice(self.model['instances'])

        for routing_key, payload in self.get_instance_events('instance_reboot', instance):
            yield self.amqp_send(routing_key, payload)

    @defer.inlineCallbacks
    def amqp_send(self, routing_key, message):
        exchange = 'zenoss.openstack.ceilometer'
        log.debug("Send event (%s)", routing_key)
        log.debug(message)

        headers = {'x-message-ttl': 600000}  # 10 minutes

        if self.options.no_ttl:
            headers = {}

        yield self.amqp.send(
            exchange,
            routing_key,
            message,
            headers=headers,
            declareExchange=False
        )

    def connect_to_amqp(self):
        zcml.load_config('configure.zcml', zope.component)
        zcml.load_config('configure.zcml', Products.ZenMessaging.queuemessaging)

        self._amqpConnectionInfo = getUtility(IAMQPConnectionInfo)
        self._queueSchema = getUtility(IQueueSchema)

        self.amqp = AMQPFactory(self._amqpConnectionInfo, self._queueSchema)

    def load_config_and_model(self):
        device = self.dmd.Devices.OpenStack.Infrastructure.findDevice(self.options.device)
        if not device:
            log.error("Device '%s' not found", self.options.device)
            return

        with open('events.yaml', 'r') as f:
            self.yaml_config = yaml.load(f)

        self.model = dict(
            instances=device.getDeviceComponents(type="OpenStackInfrastructureInstance")
        )

    def talesEvalStr(self, value, **kwargs):
        if value.startswith("python:"):
            return talesEval(value, self, extra=kwargs)
        else:
            return talesEvalStr(value, self, extra=kwargs)

    def get_instance_events(self, event_type, instance):
        if event_type not in self.yaml_config:
            raise ValueError("Event Type '%s' is not supported" % event_type)

        timestamp = datetime.datetime.utcnow().isoformat().split('.', 1)[0] + "Z"

        for event_template in self.yaml_config[event_type]:
            event = {}
            for attr, value in event_template.iteritems():
                if isinstance(value, dict):
                    event[attr] = {}
                    for attr2, value2 in value.iteritems():
                        event[attr][attr2] = self.talesEvalStr(
                            str(value2),
                            instance=instance,
                            message_id=str(uuid.uuid4()),
                            request_id="req-" + str(uuid.uuid4()))
                else:
                    event[attr] = self.talesEvalStr(
                        str(value),
                        instance=instance,
                        message_id=str(uuid.uuid4()),
                        request_id="req-" + str(uuid.uuid4()))

            if 'traits' in event:
                traitlist = []
                for name, value in event['traits'].iteritems():
                    traitlist.append(dict(name=name, value=value))
                event['traits'] = traitlist

            event['generated'] = timestamp

            routing_key = ".".join([
                'zenoss',
                'openstack',
                self.options.device,
                'event',
                event['event_type']
            ])

            payload = {
                'device': self.options.device,
                'type': 'event',
                'data': event
            }

            yield (routing_key, json.dumps(payload, indent=4))


def main():
    def finished(arg):
        if arg:
            log.error("Error: %s", arg)
        reactor.stop()

    script = SimEvents()
    d = script.run()
    d.addBoth(finished)

    reactor.run()


if __name__ == '__main__':

    # turn on timestamps in the root logger (ZenScriptBase doesnt' do this
    # by default)
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S"))
    logging.getLogger().handlers = [h]

    main()
