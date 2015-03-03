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

""" Gather selected INI files """

import io
import os.path
from twisted.internet import defer
import ConfigParser

import zope.component

from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.ZenCollector.interfaces import IEventService
from Products.ZenEvents import Event

from ZenPacks.zenoss.OpenStackInfrastructure.utils import add_local_lib_path
add_local_lib_path()

import logging
from sshclient import SSHClient

ssh_logger = logging.getLogger('txsshclient')
ssh_logger.setLevel(logging.DEBUG)

log = logging.getLogger('zen.OpenStack.inifiles')


class inifiles(PythonPlugin):

    _yaml_config = None
    _eventService = None

    deviceProperties = PythonPlugin.deviceProperties \
        + ('zCommandUsername', 'zCommandPassword',
           'zCommandPort', 'zCommandCommandTimeout',
           'zOpenStackNeutronConfigDir')

    def sendEvent(self, evt):
        if not self._eventService:
            self._eventService = zope.component.queryUtility(IEventService)
        self._eventService.sendEvent(evt)

    def sendFileClearEvent(self, device, filename):
        evt = dict(
            device=device.id,
            component='',
            summary="File %s was loaded successfully" % filename,
            severity=Event.Clear,
            eventClassKey='openStackIniFileAccess',
            eventKey=filename
        )
        self.sendEvent(evt)

    def sendFileErrorEvent(self, device, filename, errmsg):
        evt = dict(
            device=device.id,
            component='',
            summary="File %s could not be accessed: %s" % (filename, errmsg),
            severity=Event.Error,
            eventClassKey='openStackIniFileAccess',
            eventKey=filename
        )
        self.sendEvent(evt)

    def sendOptionClearEvent(self, device, filename, section, option):
        evt = dict(
            device=device.id,
            component='',
            summary="%s: Required option [%s] %s was loaded successfully" % (filename, section, option),
            severity=Event.Clear,
            eventClassKey='openStackIniFileOptionParsing',
            eventKey="%s/%s/%s" % (filename, section, option)
        )
        self.sendEvent(evt)

    def sendOptionErrorEvent(self, device, filename, section, option):
        evt = dict(
            device=device.id,
            component='',
            summary="%s: Required option [%s] %s was not found" % (filename, section, option),
            severity=Event.Error,
            eventClassKey='openStackIniFileOptionParsing',
            eventKey="%s/%s/%s" % (filename, section, option)
        )
        self.sendEvent(evt)

    def ini_get(self, device, filename, ini, section, option, required=False):
        try:
            return ini.get(section, option)
            if required:
                self.sendOptionClearEvent(device, filename, section, option)
        except ConfigParser.NoOptionError:
            if required:
                self.sendOptionErrorEvent(device, filename, section, option)
            return None

    @defer.inlineCallbacks
    def read_ini(self, device, filename, required=False):
        filepath = os.path.join(device.zOpenStackNeutronConfigDir, filename)
        log.info("Retrieving %s", filepath)

        cmd = "cat %s" % filepath
        d = yield self.client.run(cmd, timeout=self.timeout)

        if d.exitCode != 0 or d.stderr:
            if required:
                log.error("Unable to access required file %s (%s)" % (filepath, d.stderr))
                self.sendFileErrorEvent(device, filepath, d.stderr)
            else:
                log.info("Unable to access optional file %s (%s)" % (filepath, d.stderr))

            defer.returnValue(None)
            return

        self.sendFileClearEvent(device, filepath)

        ini = ConfigParser.RawConfigParser(allow_no_value=True)
        ini.readfp(io.BytesIO(d.output))
        defer.returnValue(ini)

        return

    @defer.inlineCallbacks
    def collect(self, device, log):
        manageIp = str(device.manageIp)

        log.info('Connecting to ssh://%s@%s:%d' % (
            device.zCommandUsername,
            manageIp,
            device.zCommandPort
            ))

        self.client = SSHClient({
            'hostname': manageIp,
            'port': device.zCommandPort,
            'user': device.zCommandUsername,
            'password': device.zCommandPassword,
            'buffersize': 32768})
        self.client.connect()
        self.timeout = device.zCommandCommandTimeout

        data = {}
        files = ['neutron.conf', 'plugins/ml2/ml2_conf.ini']

        # dummy
        files.append('plugins/openvswitch/ovs_neutron_plugin.ini')

        try:
            for filename in files:
                if filename == 'neutron.conf':
                    data[filename] = yield self.read_ini(device, filename, required=True)
                else:
                    data[filename] = yield self.read_ini(device, filename)
        except Exception:
            raise
        finally:
            self.client.disconnect()

        defer.returnValue(data)

    def process(self, device, results, log):
        log.info("Modeler %s processing data for device %s",
                 self.name(), device.id)

        data = {
            'neutron_core_plugin': None,
            'neutron_mechanism_drivers': [],
            'neutron_type_drivers': [],
            'neutron_ml2_ini': {}
        }

        if results['neutron.conf']:
            filename = 'neutron.conf'
            ini = results[filename]
            data['neutron_core_plugin'] = self.ini_get(device, filename, ini, 'DEFAULT', 'core_plugin', required=True)

        if data['neutron_core_plugin']:
            if data['neutron_core_plugin'] in ('neutron.plugins.ml2.plugin.Ml2Plugin', 'ml2'):
                filename = 'plugins/ml2/ml2_conf.ini'
                ini = results[filename]
                if ini:
                    data['neutron_type_drivers'] = self.ini_get(device, filename, ini, 'ml2', 'type_drivers', required=True)
                    data['neutron_mechanism_drivers'] = self.ini_get(device, filename, ini, 'ml2', 'mechanism_drivers', required=True)

        if data['neutron_mechanism_drivers']:
            # Dummy data.  This will come from the type driver for realz.
            mechanism_ini_config = [
                ('plugins/openvswitch/ovs_neutron_plugin.ini', 'ovs', 'integration_bridge')
            ]

            for filename, section, option in mechanism_ini_config:
                ini = results[filename]
                if ini:
                    data['neutron_ml2_ini'][(filename, section, option)] = self.ini_get(device, filename, ini, section, option)

        results_om = ObjectMap(data)
        return ObjectMap({'setApplyDataMapToOpenStackInfrastructureHost': results_om})
