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
log = logging.getLogger('zen.sim_perf')

from collections import defaultdict
import datetime
import json
import yaml

from twisted.internet import reactor, defer
from twisted.internet.task import LoopingCall

from Products.Five import zcml
import zope.component
from zope.component import getUtility

from Products.ZenUtils.Utils import unused
from Products.ZenUtils.ZenScriptBase import ZenScriptBase
from Products.ZenUtils.ZenTales import talesEvalStr
import Products.ZenMessaging.queuemessaging
from zenoss.protocols.interfaces import IAMQPConnectionInfo, IQueueSchema
from zenoss.protocols.twisted.amqp import AMQPFactory

unused(Globals)


def sleep(secs):
    d = defer.Deferred()
    reactor.callLater(secs, d.callback, None)
    return d


class SimPerf(ZenScriptBase):

    def buildOptions(self):
        super(SimPerf, self).buildOptions()

        self.parser.add_option(
            '-d', dest='device',
            help='Device Name',
            default='test_ostack')

        self.parser.add_option(
            '--nottl', dest='no_ttl',
            default=False, action='store_true',
            help="Disable TTL on generated messages (prevent rabbitmq's expiration, force zenpython to consume them all)")

    @defer.inlineCallbacks
    def run(self):
        delay_step = 15
        delay_max = 120

        self.connect()

        self.load_config_and_model()
        self.connect_to_amqp()

        loopingcalls = defaultdict(list)
        for i, host in enumerate(self.model['host_instances']):
            interval = self.yaml_config['Instance']['interval']
            delay = (i * delay_step) % delay_max
            loop = LoopingCall(self.send_host_instance_batch, host)
            loopingcalls[int(delay)].append(("Host %s Instances" % host, loop, interval))

        for i, host in enumerate(self.model['host_vnics']):
            interval = self.yaml_config['Vnic']['interval']
            delay = (i * delay_step) % delay_max
            loop = LoopingCall(self.send_host_vnic_batch, host)
            loopingcalls[int(delay)].append(("Host %s Vnics" % host, loop, interval))

        interval = self.yaml_config['Image']['interval']
        loop = LoopingCall(self.send_image_batch)
        loopingcalls[0].append(("Images", loop, interval))

        # Start the looping calls in stages, so that the "hosts" don't all send at
        # once.
        deferreds = []
        for delay in range(0, delay_max, delay_step):
            for descr, loop, interval in loopingcalls[delay]:
                log.info("Starting %s loopingcall (delay=%d, interval=%d)", descr, delay, interval)
                deferreds.append(loop.start(interval, now=True))

            if interval < delay_max:
                yield sleep(delay_step)

        yield defer.DeferredList(deferreds)

    @defer.inlineCallbacks
    def send_host_instance_batch(self, host):
        log.info("Starting instance batch for %s", host)
        instances = self.model['host_instances'][host]
        data = self.get_meter_data('Instance', instances)
        for routing_key, payload in data:
            yield self.amqp_send(routing_key, payload)
        log.info("Finished instance batch for %s", host)

    @defer.inlineCallbacks
    def send_host_vnic_batch(self, host):
        log.info("Starting vnic batch for %s", host)
        vnics = self.model['host_vnics'][host]
        data = self.get_meter_data('Vnic', vnics)
        for routing_key, payload in data:
            yield self.amqp_send(routing_key, payload)
        log.info("Finished vnic batch for %s", host)

    @defer.inlineCallbacks
    def send_image_batch(self):
        log.info("Starting image batch")
        data = self.get_meter_data('Image', self.model['images'])
        for routing_key, payload in data:
            yield self.amqp_send(routing_key, payload)
        log.info("Finished image batch")

    @defer.inlineCallbacks
    def amqp_send(self, routing_key, message):
        exchange = 'zenoss.openstack.ceilometer'
        log.debug("Send event (%s)", routing_key)

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

        with open('perf.yaml', 'r') as f:
            self.yaml_config = yaml.load(f)

        self.model = dict(
            host_instances={},
            host_vnics={},
            images=[]
        )

        for host in device.getDeviceComponents(type="OpenStackInfrastructureHost"):
            self.model['host_instances'][host.id] = []
            self.model['host_vnics'][host.id] = []
            if not host.hypervisor():
                log.warning("Host %s has no hypervisor - skipping" % host.id)
                continue
            for instance in host.hypervisor().instances():
                self.model['host_instances'][host.id].append(instance.resourceId)
                for vnic in instance.vnics():
                    self.model['host_vnics'][host.id].append(vnic.resourceId)

        for image in device.getDeviceComponents(type="OpenStackInfrastructureImage"):
            # we don't have modeled resourceIds for these.  It doesn't really
            # matter- these events are unused by our perf collector anyway.
            # Just use the image.id as a dummy value.
            self.model['images'].append(str(image.id))

    def get_meter_data(self, object_type, resourceIds=None):
        if object_type not in self.yaml_config:
            raise ValueError("Object Type '%s' is not supported" % object_type)

        if resourceIds is None:
            raise ValueError("resourceIds is required")

        resource_metadata = self.yaml_config[object_type]['resource_metadata']
        for resource_id in resourceIds:
            for meter_config in self.yaml_config[object_type]['meters'].values():
                v_meter = self.talesEvalStr(meter_config['meter'], resource_id=resource_id)
                v_resource_id = self.talesEvalStr(meter_config['resource_id'], resource_id=resource_id)

                routing_key = self.build_routing_key(self.options.device, v_meter)

                payload = self.build_payload(
                    resource_id=v_resource_id,
                    counter_name=meter_config['counter_name'],
                    counter_unit=meter_config['counter_unit'],
                    counter_volume=meter_config['counter_volume'],
                    counter_type=meter_config['counter_type'],
                    resource_metadata=resource_metadata
                )

                yield (routing_key, json.dumps(payload, indent=4))

    def talesEvalStr(self, value, **kwargs):
        return talesEvalStr(value, self, extra=kwargs)

    def build_routing_key(self, device, meter):
        return "zenoss.openstack.{device}.meter.{meter}".format(device=device, meter=meter)

    def build_payload(self, resource_id, counter_name, counter_unit, counter_volume, counter_type, resource_metadata):
        timestamp = datetime.datetime.utcnow().isoformat().split('.', 1)[0] + "Z"
        data = dict(
            source="openstack",

            # Dummy values.. we can get away with this because nothing looks at them.
            user_id="2f715915690342798305dcc0407161a5",
            message_signature="e8605590524a89a73c992d83ac168eff034181f82db3cb4927be06b43d045dbc",
            message_id="89ae8508-204b-11e6-94da-0050568531f8",
            project_id="33ffa6ba1ecc46de98afb7394d311eae",
            resource_metadata=resource_metadata,

            # actual values of importance(tm)
            timestamp=timestamp,
            resource_id=resource_id,
            counter_name=counter_name,
            counter_unit=counter_unit,
            counter_volume=counter_volume,
            counter_type=counter_type
        )

        return {
            "device": self.options.device,
            "data": data,
            "type": "meter"
        }


def main():
    def finished(arg):
        if arg:
            log.error("Error: %s", arg)
        reactor.stop()

    script = SimPerf()
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
