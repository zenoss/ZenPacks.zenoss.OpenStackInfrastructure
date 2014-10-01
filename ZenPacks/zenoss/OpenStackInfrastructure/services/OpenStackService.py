##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
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
        for host in device.getDeviceComponents(type='OpenStackInfrastructureHost'):
            hostnames = set()
            hostnames.add(host.hostname)
            if host.hostfqdn:
                hostnames.add(host.hostfqdn)

            processes = set()
            for process in host.proxy_device().getDeviceComponents(type='OSProcess'):
                process_name = process.osProcessClass().id
                if process_name in ('ceilometer-agent-notification', 'ceilometer-collector'):
                    processes.add(process_name)

            if processes:
                result.append(dict(
                    hostnames=list(hostnames),
                    processes=list(processes)
                ))

        return result
