##############################################################################
#
# Copyright (C) Zenoss, Inc. 2013-2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################


from . import schema

import logging
LOG = logging.getLogger('zen.OpenStackInfrastructureEndpoint')


class Endpoint(schema.Endpoint):

    def hosts(self):
        return self.getDeviceComponents(type="OpenStackInfrastructureHost")

    def get_maintain_proxydevices(self):
        from ZenPacks.zenoss.OpenStackInfrastructure.DeviceProxyComponent \
            import DeviceProxyComponent
        # hosts that our Endpoint already knows about
        hosts = self.dmd.Devices.findDevice(self.name()).hosts()
        hostUuids = [host.uuid for host in hosts]
        found = True
        for meta_type in DeviceProxyComponent.deviceproxy_meta_types():
            for component in self.getDeviceComponents(type=meta_type):
                if component.uuid not in hostUuids:
                    found = False
                    break
        return found

    def set_maintain_proxydevices(self, arg):
        from ZenPacks.zenoss.OpenStackInfrastructure.DeviceProxyComponent \
            import DeviceProxyComponent
        for meta_type in DeviceProxyComponent.deviceproxy_meta_types():
            for component in self.getDeviceComponents(type=meta_type):
                component.maintain_proxy_device()

        return True
