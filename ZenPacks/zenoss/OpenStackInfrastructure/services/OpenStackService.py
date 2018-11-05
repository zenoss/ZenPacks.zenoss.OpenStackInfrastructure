##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2018, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStackService')

from Products.ZenHub.HubService import HubService
from Products.ZenHub.PBDaemon import translateError


class OpenStackService(HubService):

    @translateError
    def remote_expected_ceilometer_heartbeats(self, endpoint_id):
        device = self.dmd.Devices.findDeviceByIdExact(endpoint_id)

        result = []
        try:
            for host in device.getDeviceComponents(type='OpenStackInfrastructureHost'):
                hostnames = set()
                hostnames.add(host.hostname)
                if host.hostfqdn:
                    hostnames.add(host.hostfqdn)
                if host.hostlocalname:
                    hostnames.add(host.hostlocalname)
                for hostref in [x[0] for x in device.get_host_mappings().items() if x[1] == host.id]:
                    hostnames.add(hostref)

                processes = set()
                linux_device = host.proxy_device()
                if linux_device:
                    hostnames.add(linux_device.titleOrId())

                    for process in linux_device.getDeviceComponents(type='OSProcess'):
                        process_name = process.osProcessClass().id
                        if process_name in ('ceilometer-collector'):
                            processes.add(process_name)

                if processes:
                    result.append(dict(
                        hostnames=list(hostnames),
                        processes=list(processes)
                    ))

        except Exception:
            log.error("Device Error %s on endpoint_id %s" % (device, endpoint_id))

        return result
