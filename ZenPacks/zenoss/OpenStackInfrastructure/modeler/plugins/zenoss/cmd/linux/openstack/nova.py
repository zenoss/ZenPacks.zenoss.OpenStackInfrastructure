###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2014-2017, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

""" Get OpenStack Nova API version """

from twisted.internet.defer import inlineCallbacks, returnValue

from Products.DataCollector.plugins.DataMaps import ObjectMap, MultiArgs
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from ZenPacks.zenoss.OpenStackInfrastructure.utils import add_local_lib_path, \
    container_cmd_wrapper

from ZenPacks.zenoss.OpenStackInfrastructure.ssh import SSHClient

add_local_lib_path()

import re

def get_productKey(version):
    VERSION_MAP = [
        # in order versions, we used the returned version as the product key
        ('2013',   version),   # Havana
        ('2014.1', version),   # Icehouse
        ('2014.2', version),   # Juno
        ('2015.1', version),   # Kilo
        ('2015.2', version),   # Liberty
        ('2016.1', version),   # Mitaka

        # Moving forward, we are using the product name as the product key.
        # This will automatically create new products with that name, as well,
        # if we don't include them in objects.xml, so that's a nice side effect.
        ('14',    'Newton'),
        ('15',    'Ocata'),
        ('16',    'Pike'),
    ]

    for prefix, productKey in VERSION_MAP:
        if version.startswith(prefix):
            return productKey

    # Unrecognized?  Well, just return the version and we'll use that.
    return version


class nova(PythonPlugin):

    deviceProperties = PythonPlugin.deviceProperties \
                       + ('zCommandUsername', 'zCommandPassword',
                          'zCommandPort', 'zCommandCommandTimeout',
                          'zOpenStackRunNovaManageInContainer', 'zKeyPath')

    @inlineCallbacks
    def collect(self, device, log):
        manageIp = str(device.manageIp)

        log.info('Connecting to ssh://%s@%s:%d' % (
            device.zCommandUsername,
            manageIp,
            device.zCommandPort
        ))

        client = SSHClient({
            'hostname': manageIp,
            'port': device.zCommandPort,
            'user': device.zCommandUsername,
            'password': device.zCommandPassword,
            'identities': [device.zKeyPath],
            'buffersize': 32768})
        client.connect()
        timeout = device.zCommandCommandTimeout

        # host based installation
        cmd = "nova-manage --version 2>&1"
        if device.zOpenStackRunNovaManageInContainer:
            # container based installation
            cmd = container_cmd_wrapper(
                device.zOpenStackRunNovaManageInContainer,
                "nova-manage --version 2>&1"
            )
        log.info("Running %s" % cmd)
        try:
            d = yield client.run(cmd, timeout=timeout)

            if d.exitCode != 0 or d.stderr:
                # nova conduct isn't running on this host, and should be ignored.
                log.info("nova conduct not running on host- not collecting nova version")
                return

        except Exception:
            raise
        finally:
            client.disconnect()

        returnValue(d.output)

    def process(self, device, results, log):
        log.info("Modeler %s processing data for device %s",
                 self.name(), device.id)

        matcher = re.compile(r'^(?P<version>[\d\.]+)')

        for line in results.split('\n'):
            match = matcher.search(line)
            if match:
                version = match.group('version')
                productKey = get_productKey(version)
                openstack_om = ObjectMap({
                    'compname': 'os',
                    'setProductKey': MultiArgs(productKey, 'OpenStack')
                })

                return [ObjectMap({
                    'setApplyDataMapToOpenStackInfrastructureEndpoint': openstack_om
                    })]

        return []
