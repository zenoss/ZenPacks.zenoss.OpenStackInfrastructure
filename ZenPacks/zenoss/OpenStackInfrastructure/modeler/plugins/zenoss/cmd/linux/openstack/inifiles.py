###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2015, Zenoss Inc.
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

from ZenPacks.zenoss.OpenStackInfrastructure.interfaces import INeutronImplementationPlugin
from ZenPacks.zenoss.OpenStackInfrastructure.neutron_integration import split_list

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
                log.error("Unable to access required file %s (%s)" % (filepath, d.stderr.strip()))
                self.sendFileErrorEvent(device, filepath, d.stderr)
            else:
                log.info("Unable to access optional file %s (%s)" % (filepath, d.stderr.strip()))

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
        required_files = ['neutron.conf']
        optional_files = ['plugins/ml2/ml2_conf.ini']
        plugin_names = set()

        try:
            # Check if neutron-server runs on this machine
            d = yield self.client.run("pgrep neutron-server", timeout=self.timeout)
            if d.exitCode != 0:
                # neutron isn't running on this host, so its config
                # files are suspect, and should be ignored.
                log.info("neutron-server not running on host- not collecting ini files")
                defer.returnValue(data)
                return

            # Collect ini files
            for filename in required_files:
                if filename not in data:
                    data[filename] = yield self.read_ini(device, filename, required=True)
            for filename in optional_files:
                if filename not in data:
                    data[filename] = yield self.read_ini(device, filename)

            required_files = []
            optional_files = []

            if data['neutron.conf']:
                ini = data['neutron.conf']
                neutron_core_plugin = self.ini_get(device, filename, ini, 'DEFAULT', 'core_plugin', required=True)
                plugin_names.add(neutron_core_plugin)

            if 'plugins/ml2/ml2_conf.ini' in data:
                mechanism_drivers = split_list(self.ini_get(
                    device,
                    filename,
                    data['plugins/ml2/ml2_conf.ini'],
                    'ml2',
                    'mechanism_drivers',
                    required=False) or '')

                for mechanism_driver in mechanism_drivers:
                    plugin_names.add("ml2." + mechanism_driver)

            data['plugin_names'] = set()
            for plugin_name in plugin_names:
                plugin = zope.component.queryUtility(INeutronImplementationPlugin, plugin_name)
                if not plugin:
                    continue

                plugin_class = plugin.__class__.__name__
                log.info("Checking for additinal ini requirements in neutron implementation plugin '%s': %s" % (plugin_name, plugin_class))
                data['plugin_names'].add(plugin_name)

                for filename, section, option in plugin.ini_required():
                    required_files.append(filename)

                for filename, section, option in plugin.ini_optional():
                    optional_files.append(filename)

            for filename in required_files:
                if filename not in data:
                    data[filename] = yield self.read_ini(device, filename, required=True)
            for filename in optional_files:
                if filename not in data:
                    data[filename] = yield self.read_ini(device, filename)

        except Exception:
            raise
        finally:
            self.client.disconnect()

        defer.returnValue(data)

    def process(self, device, results, log):
        log.info("Modeler %s processing data for device %s",
                 self.name(), device.id)

        if 'neutron.conf' not in results:
            log.info("No neutron ini files to process.")
            return

        data = {
            'neutron_core_plugin': None,
            'neutron_mechanism_drivers': [],
            'neutron_type_drivers': [],
            'set_neutron_ini': {}
        }

        if 'plugin_names' not in results:
            log.error("No neutron implementation plugins were identified, unable to continue.")
            return

        if results['neutron.conf']:
            filename = 'neutron.conf'
            ini = results[filename]
            data['neutron_core_plugin'] = self.ini_get(device, filename, ini, 'DEFAULT', 'core_plugin', required=True)

        if data['neutron_core_plugin']:
            if data['neutron_core_plugin'] in ('neutron.plugins.ml2.plugin.Ml2Plugin', 'ml2'):
                filename = 'plugins/ml2/ml2_conf.ini'
                ini = results[filename]
                if ini:
                    data['neutron_type_drivers'] = split_list(self.ini_get(device, filename, ini, 'ml2', 'type_drivers', required=True))
                    data['neutron_mechanism_drivers'] = split_list(self.ini_get(device, filename, ini, 'ml2', 'mechanism_drivers', required=True))

        for plugin_name in results['plugin_names']:
            # See if we have any plugins registered for the core module
            # (if not ML2) or mechanism type (if ML2)
            plugin = zope.component.queryUtility(INeutronImplementationPlugin, plugin_name)
            if not plugin:
                continue

            log.debug("(Process) Using plugin '%s'" % plugin_name)
            for filename, section, option in plugin.ini_required():
                ini = results.get(filename, None)
                if ini:
                    data['set_neutron_ini'][(filename, section, option)] = self.ini_get(device, filename, ini, section, option, required=True)

            for filename, section, option in plugin.ini_optional():
                ini = results.get(filename, None)
                if ini:
                    data['set_neutron_ini'][(filename, section, option)] = self.ini_get(device, filename, ini, section, option)

            return ObjectMap({'setApplyDataMapToOpenStackInfrastructureEndpoint': ObjectMap(data)})
