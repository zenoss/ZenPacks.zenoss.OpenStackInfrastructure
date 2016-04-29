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

""" Get OpenStack instance virtual NIC information using libvert """

from lxml import etree
from twisted.internet.defer import inlineCallbacks, returnValue

from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
from ZenPacks.zenoss.OpenStackInfrastructure.utils import add_local_lib_path, \
    container_cmd_wrapper
add_local_lib_path()

import logging
from ZenPacks.zenoss.OpenStackInfrastructure.ssh import SSHClient

ssh_logger = logging.getLogger('txsshclient')
ssh_logger.setLevel(logging.DEBUG)

log = logging.getLogger('zen.OpenStack.libvirt')


class LibvirtXMLError(Exception):
    pass


class libvirt(PythonPlugin):

    deviceProperties = PythonPlugin.deviceProperties \
        + ('zCommandUsername', 'zCommandPassword',
           'zCommandPort', 'zCommandCommandTimeout', 'openstack_instanceList',
           'zOpenStackRunVirshQemuInContainer')

    def condition(self, device, log):
        # Only run this if we've got openstack instances on this host.
        return len(device.openstack_instanceList()) > 0

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
            'identities': ['~/.ssh/id_rsa', '~/.ssh/id_dsa'],
            'buffersize': 32768})
        client.connect()
        timeout = device.zCommandCommandTimeout
        data = {}

        try:
            for instanceId, instanceUUID in device.openstack_instanceList:
                # host based installation
                cmd = "virsh --readonly -c 'qemu:///system' dumpxml '%s'" % \
                      instanceUUID
                if device.zOpenStackRunNeutronCommonInContainer:
                    # container based installation
                    cmd = container_cmd_wrapper(
                        device.zOpenStackRunVirshQemuInContainer,
                        "virsh --readonly -c 'qemu:///system' dumpxml '%s'" % \
                        instanceUUID)
                log.info("Running %s" % cmd)
                d = yield client.run(cmd, timeout=timeout)

                if d.exitCode != 0 or d.stderr:
                    if 'Domain not found' in d.stderr:
                        log.debug("Domain not found while running virsh (rc=%s, stderr='%s')" % (d.exitCode, d.stderr))
                    else:
                        log.error("Error running virsh (rc=%s, stderr='%s')" % (d.exitCode, d.stderr))
                    continue

                try:
                    tree = etree.fromstring(d.output)

                    instanceName = str(tree.xpath("/domain/name/text()")[0])
                    zenossInstanceId = 'server-%s' % (instanceUUID)
                    data[instanceUUID] = {
                        'id': zenossInstanceId,
                        'serialNumber': str(tree.xpath("/domain/sysinfo/system/entry[@name='serial']/text()")[0]),
                        'biosUuid': str(tree.xpath("/domain/sysinfo/system/entry[@name='uuid']/text()")[0])
                    }

                except Exception:
                    log.error("Invalid XML Received from (%s):\n%s\n\n" % (cmd, d.output))
                    raise LibvirtXMLError('Incomplete or invalid XML returned from virsh command. Consult log for more details.')

                vnics = []
                for interface in tree.xpath("/domain/devices/interface"):
                    target = interface.find("target/[@dev]")
                    mac = interface.find("mac/[@address]")

                    if target is None or mac is None:
                        # unrecognized interface type
                        continue

                    # compute the resourceId in the same way that ceilometer's
                    # net pollster does.
                    vnicName = str(target.get('dev'))
                    zenossVnicId = 'vnic-%s-%s' % (instanceUUID, vnicName)
                    ceilometerResourceId = '%s-%s-%s' % (instanceName, instanceUUID, vnicName)

                    vnics.append({
                        'id': zenossVnicId,
                        'name': vnicName,
                        'macaddress': str(mac.get('address')),
                        'resourceId': ceilometerResourceId
                    })
                data[instanceUUID]['vnics'] = vnics

        finally:
            client.disconnect()

        returnValue(data)

    def process(self, device, results, log):
        log.info("Modeler %s processing data for device %s",
                 self.name(), device.id)
        objmaps = []

        for instance in results.values():
            # additional instance-level attributes
            objmaps.append(ObjectMap(
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Instance',
                compname='components/%s' % (instance['id']),
                data=dict(
                    serialNumber=instance['serialNumber'],
                    biosUuid=instance['biosUuid']
                )))

            # vnics
            vnic_oms = []
            for vnic in instance['vnics']:
                vnic_oms.append(ObjectMap(
                    modname='ZenPacks.zenoss.OpenStackInfrastructure.Vnic',
                    compname='components/%s/vnics/%s' % (instance['id'], vnic['id']),
                    data=dict(
                        id=vnic['id'],
                        title=vnic['name'],
                        macaddress=vnic['macaddress'],
                        resourceId=vnic['resourceId']
                    )))

            objmaps.append(RelationshipMap(
                compname='components/%s' % (instance['id']),
                modname='ZenPacks.zenoss.OpenStackInfrastructure.Vnic',
                relname='vnics',
                objmaps=vnic_oms))

        # Wrap all the objmaps so that they are applied to the openstack
        # device components, not to the linux device we are modeling.

        return [ObjectMap({'setApplyDataMapToOpenStackInfrastructureEndpoint': om}) for om in objmaps]
