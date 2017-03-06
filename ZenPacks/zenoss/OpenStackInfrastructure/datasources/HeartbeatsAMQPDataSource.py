##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.HeartbeatsAMQP')

from time import time
from pprint import pformat

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks, returnValue

import zope.component
from zope.component import adapts
from zope.interface import implements

from Products.ZenCollector.interfaces import ICollector
from Products.ZenEvents import ZenEventClasses

from ZenPacks.zenoss.OpenStackInfrastructure.datasources.AMQPDataSource import (
    AMQPDataSource, AMQPDataSourcePlugin, AMQPDataSourceInfo,
    IAMQPDataSourceInfo)


class HeartbeatsAMQPDataSource(AMQPDataSource):
    '''
    Datasource used to capture heartbeats shipped to us from OpenStack
    Ceilometer via AMQP.
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack Ceilometer Heartbeats AMQP',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 30

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'HeartbeatsAMQPDataSource.HeartbeatsAMQPDataSourcePlugin'

    # HeartbeatsAMQPDataSource

    _properties = AMQPDataSource._properties + ()


class IHeartbeatsAMQPDataSourceInfo(IAMQPDataSourceInfo):
    '''
    API Info interface for IHeartbeatsAMQPDataSource.
    '''

    pass


class HeartbeatsAMQPDataSourceInfo(AMQPDataSourceInfo):
    '''
    API Info adapter factory for HeartbeatsAMQPDataSource.
    '''

    implements(IHeartbeatsAMQPDataSourceInfo)
    adapts(HeartbeatsAMQPDataSource)

    testable = False


# Persistent state
last_heard_heartbeats = {}
MAX_TIME_LAPSE = 300


class HeartbeatsAMQPDataSourcePlugin(AMQPDataSourcePlugin):
    proxy_attributes = ('expected_ceilometer_heartbeats',)
    exchange_name = '$OpenStackInboundHeartbeats'
    queue_name = "$OpenStackInboundHeartbeat"
    failure_eventClassKey = 'openStackCeilometerHeartbeat'

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
            datasource.plugin_classname
        )

    @inlineCallbacks
    def getService(self, service_name):
        collector = zope.component.queryUtility(ICollector)
        service = yield collector.getService(service_name)
        returnValue(service)

    @inlineCallbacks
    def collect(self, config):
        log.debug("Collect for OpenStack AMQP Heartbeats (%s)" % config.id)

        service = yield self.getService('ZenPacks.zenoss.OpenStackInfrastructure.services.OpenStackService')
        expected_heartbeats = yield service.callRemote('expected_ceilometer_heartbeats', config.id)

        if not expected_heartbeats:
            return

        data = yield super(HeartbeatsAMQPDataSourcePlugin, self).collect(config)
        device_id = config.id

        for host in expected_heartbeats:
            hostname = host['hostnames'][0]
            possible_hostnames = host['hostnames']
            required_processes = host['processes']

            heartbeat_hostname = None
            for possible_hostname in possible_hostnames:
                if possible_hostname in last_heard_heartbeats:
                    heartbeat_hostname = possible_hostname
                    break

            process_heartbeats = {}

            if heartbeat_hostname is None:
                # We have not heard a heartbeat from this host under
                # any of its possible hostnames (short name, fqdn)
                #
                # So there won't be any process heartbeats, and we will
                # consider them all to be down.
                process_heartbeats = {}
            else:
                process_heartbeats = last_heard_heartbeats[heartbeat_hostname]

            for proc in required_processes:
                if proc not in process_heartbeats:
                    evt = {
                        'device': device_id,
                        'severity': ZenEventClasses.Warning,
                        'eventKey': hostname + '_' + proc,
                        'summary': "No heartbeats received from '%s' on %s.  Check the host and process status." % (proc, hostname),
                        'eventClassKey': 'openStackCeilometerHeartbeat',
                    }
                    log.error(pformat(evt))
                else:
                    # diff > MAX_TIME_LAPSE?
                    time_diff = time() - \
                        process_heartbeats[proc]['lastheard']

                    if time_diff > MAX_TIME_LAPSE:
                        evt = {
                            'device': device_id,
                            'severity': ZenEventClasses.Warning,
                            'eventKey': hostname + '_' + proc,
                            'summary': "No heartbeats received from '%s' on %s for more than %d seconds.  Check its status and restart it if necessary." % (proc, hostname, MAX_TIME_LAPSE),
                            'eventClassKey': 'openStackCeilometerHeartbeat',
                        }
                        log.error(pformat(evt))
                    else:
                        evt = {
                            'device': device_id,
                            'severity': ZenEventClasses.Clear,
                            'eventKey': hostname + '_' + proc,
                            'summary': "Process '%s' on %s is sending heartbeats normally." % (proc, hostname),
                            'eventClassKey': 'openStackCeilometerHeartbeat',
                        }

                data['events'].append(evt)

        if len(data['events']):
            data['events'].append({
                'device': device_id,
                'summary': 'OpenStack Ceilometer AMQP Heartbeat: successful collection',
                'severity': ZenEventClasses.Clear,
                'eventKey': 'openstackCeilometerAMQPHeartbeatCollection',
                'eventClassKey': 'EventsSuccess',
                })

        defer.returnValue(data)

    def processMessage(self, device_id, message, contentbody):
        # add heartbeats to last_heard_heartbeats on per host, per process base
        msg = {}
        hostname = contentbody['hostname']
        processname = contentbody['processname']

        if hostname not in last_heard_heartbeats:
            last_heard_heartbeats[hostname] = {}

        msg['exchange'] = message.fields[3]
        msg['routing_key'] = message.fields[4]
        msg['lastheard'] = contentbody['timestamp']

        last_heard_heartbeats[hostname][processname] = msg
        log.debug("Received heartbeat from %s / %s" % (hostname, processname))
