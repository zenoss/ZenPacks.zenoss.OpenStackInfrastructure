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

from twisted.internet.defer import inlineCallbacks, returnValue

from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from ZenPacks.zenoss.OpenStack.utils import add_local_lib_path
add_local_lib_path()

import logging
from sshclient import SSHClient


class libvirt(PythonPlugin):

    deviceProperties = PythonPlugin.deviceProperties \
        + ('zCommandUsername', 'zCommandPassword',
           'zCommandPort', 'zCommandCommandTimeout', 'openstack_instanceNames')

    def condition(self, device, log):
        # Only run this if we've got openstack instances on this host.
        return len(device.openstack_instanceNames()) > 0

    @inlineCallbacks
    def collect(self, device, log):
        log.info('User name %s', device.zCommandUsername)

        for ssh_logname in ('auth', 'channel', 'client', 'connection',
            'ServerProtocol', 'SSHClient', 'SSHServer', 'SSHTransport'):
            ssh_logger = logging.getLogger(ssh_logname)
            ssh_logger.setLevel(logging.DEBUG)

        if (device.zCommandUsername == '') \
                and (device.zCommandPassword == ''):
            log.warn('Command User Name & Password is empty')
            returnValue(None)

        serverIP = str(device.manageIp)
        log.info('Server IP %s', serverIP)

        client = SSHClient({
            'hostname': serverIP,
            'port': device.zCommandPort,
            'user': device.zCommandUsername,
            'password': device.zCommandPassword,
            'buffersize': 32768})
        client.connect()
        timeout = device.zCommandCommandTimeout

        for instanceName in device.openstack_instanceNames:
            cmd = "virsh --readonly -c 'qemu:///system' dumpxml '%s'" % instanceName
            log.info("Running %s" % cmd)
            d = yield client.run(cmd, timeout=timeout)

            if ((d.exitCode != 0) or (d is None)):
                if d is not None:
                    log.error('Error in Output Output:%s Exitcode :%s',
                              str(d.output),
                              str(d.exitCode))
                log.error('Error in Output')
                returnValue(None)

            else:
                log.info("OUTPUT: " + d.output)

        client.disconnect()

        returnValue([])

    def process(self, device, results, log):
        log.info("Modeler %s processing data for device %s",
                 self.name(), device.id)
        objectmaps = []
        import pdb; pdb.set_trace()


        pass
