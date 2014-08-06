###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2014, Zenoss Inc.
#
# LICENSE TBD
#
###########################################################################

from oslo.config import cfg

from ceilometer import dispatcher
from ceilometer.openstack.common import log

from kombu import Connection
from kombu.entity import Exchange
from kombu.messaging import Producer
from eventlet import pools
from eventlet import semaphore

LOG = log.getLogger(__name__)

zenoss_dispatcher_opts = [
    cfg.StrOpt('zenoss_device',
               default=None,
               help='Zenoss device name for this openstack environment.'),
    cfg.StrOpt('amqp_hostname',
               default=None,
               help='Zenoss AMQP Host'),
    cfg.IntOpt('amqp_port',
               default=None,
               help='Zenoss AMQP Port'),
    cfg.StrOpt('amqp_userid',
               default=None,
               help='Zenoss AMQP UserID'),
    cfg.StrOpt('amqp_password',
               default=None,
               help='Zenoss AMQP Password'),
    cfg.StrOpt('amqp_virtual_host',
               default=None,
               help='Zenoss AMQP Virtual Host'),
    cfg.IntOpt('amqp_max_retries',
               default=5,
               help='Maximum number of times to retry when (re)connecting to AMQP.'),
    cfg.IntOpt('amqp_retry_interval_start',
               default=1,
               help='Seconds to sleep when retrying'),
    cfg.IntOpt('amqp_retry_interval_step',
               default=1,
               help='Seconds to add to the sleep interval on each retry)'),
    cfg.IntOpt('amqp_retry_interval_max',
               default=5,
               help='Maximum number of seconds to sleep between retries'),
]

cfg.CONF.register_opts(zenoss_dispatcher_opts, group="dispatcher_zenoss")


# Basic connection pooling for our amqp producers and sessions, used for sending
# AMQP messages to zenoss.

class AMQPConnection(object):

    conf = None
    exchange = Exchange('zenoss.openstack.ceilometer', type='topic')
    connection = None
    producer = None

    def __init__(self, conf):
        self.conf = conf
        self.reconnect()

    def reconnect(self):
        LOG.info("Opening new AMQP connection to amqp://%s@%s:%s%s" % (
            self.conf.amqp_userid, self.conf.amqp_hostname, self.conf.amqp_port, self.conf.amqp_virtual_host))

        if self.connection:
            self.connection.release()

        self.connection = Connection(
            hostname=self.conf.amqp_hostname,
            userid=self.conf.amqp_userid,
            password=self.conf.amqp_password,
            virtual_host=self.conf.amqp_virtual_host,
            port=self.conf.amqp_port)

        channel = self.connection.channel()   # get a new channel
        self.producer = Producer(channel, self.exchange,
                                 auto_declare=[self.exchange])


class AMQPPool(pools.Pool):
    def __init__(self, conf, *args, **kwargs):
        self.conf = conf
        super(AMQPPool, self).__init__(*args, **kwargs)

    def create(self):
        return AMQPConnection(self.conf)

_pool_create_sem = semaphore.Semaphore()


class ZenossDispatcher(dispatcher.Base):
    '''

    [dispatcher_zenoss]

    # Name of the device in zenoss for this openstack environment
    zenoss_device=myopenstack
    amqp_hostname=zenosshost
    amqp_port=5672
    amqp_userid=zenoss
    amqp_password=zenoss
    amqp_virtual_host=/zenoss

    To enable this dispatcher, the following section needs to be present in
    ceilometer.conf file

    [collector]
    dispatchers = zenoss

    (Note that other dispatchers may be listed on their own lines as well,
     such as dispatchers = database)
    '''

    pool = None

    def __init__(self, conf):
        super(ZenossDispatcher, self).__init__(conf)

        missing_cfg = set()
        for required_cfg in ('zenoss_device', 'amqp_hostname', 'amqp_port',
                             'amqp_userid', 'amqp_password',
                             'amqp_virtual_host'):

            if getattr(self.conf.dispatcher_zenoss, required_cfg, None) is None:
                missing_cfg.add(required_cfg)

        if len(missing_cfg):
            LOG.error("Zenoss dispatcher disabled due to missing required configuration: %s" %
                      (", ".join(missing_cfg)))
            self.enabled = False
            return

        self.enabled = True

        # Create the connection pool.
        with _pool_create_sem:
            # Just in case, make sure only one thread tries to create the
            # connection pool for this dispatcher.
            if not ZenossDispatcher.pool:
                ZenossDispatcher.pool = AMQPPool(self.conf.dispatcher_zenoss)

    def publish(self, amqp, routing_key, data):
        def errback(exc, interval):
            LOG.warning("Couldn't publish message: %r. Retry in %ds" % (exc, interval))

        conf = self.conf.dispatcher_zenoss

        publish_with_retry = amqp.connection.ensure(
            amqp.producer,
            amqp.producer.publish,
            errback=errback,
            max_retries=conf.amqp_max_retries,
            interval_start=conf.amqp_retry_interval_start,
            interval_step=conf.amqp_retry_interval_step,
            interval_max=conf.amqp_retry_interval_max,
            )

        publish_with_retry(data,
                           serializer='json',
                           routing_key=routing_key)

    def record_metering_data(self, data):
        if not self.enabled:
            return

        if not isinstance(data, list):
            data = [data]

        with self.pool.item() as amqp:
            for data_item in data:
                routing_key = ".".join([
                    'zenoss',
                    'openstack',
                    self.conf.dispatcher_zenoss.zenoss_device,
                    'meter',
                    data_item['counter_name'],
                    data_item['resource_id']
                ])

                LOG.debug("Publishing message to %s" % (routing_key))

                self.publish(amqp, routing_key, {
                    'device': self.conf.dispatcher_zenoss.zenoss_device,
                    'type': 'meter',
                    'data': data_item
                })

    def record_events(self, events):
        LOG.info("record_events called (events=%s)" % events)

        if not self.enabled:
            return

        if not isinstance(events, list):
            events = [events]

        with self.pool.item() as amqp:
            for event in events:
                routing_key = ".".join([
                    'zenoss',
                    'openstack',
                    self.conf.dispatcher_zenoss.zenoss_device,
                    'event',
                    event.event_type
                ])

                LOG.debug("Publishing message to %s" % (routing_key))

                self.publish(amqp, routing_key, {
                    'device': self.conf.dispatcher_zenoss.zenoss_device,
                    'type': 'event',
                    'data': event.as_dict()
                })
