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

    def region(self):
        return self.getDeviceComponents(type="OpenStackInfrastructureRegion")[0]

    def get_maintain_proxydevices(self):
        from ZenPacks.zenoss.OpenStackInfrastructure.DeviceProxyComponent \
            import DeviceProxyComponent
        for meta_type in DeviceProxyComponent.deviceproxy_meta_types():
            for component in self.getDeviceComponents(type=meta_type):
                if component.need_maintenance():
                    return False

        return True

    def set_maintain_proxydevices(self, arg):
        from ZenPacks.zenoss.OpenStackInfrastructure.DeviceProxyComponent \
            import DeviceProxyComponent
        for meta_type in DeviceProxyComponent.deviceproxy_meta_types():
            for component in self.getDeviceComponents(type=meta_type):
                component.maintain_proxy_device()

        return True
