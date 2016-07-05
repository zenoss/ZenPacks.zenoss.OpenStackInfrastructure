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
LOG = logging.getLogger('zen.OpenStackInfrastructureHost')

from Products.ZenEvents.ZenEventClasses import Clear, Warning
from DateTime import DateTime


class Host(schema.Host):
    # These will be derived from the services present on the host
    def isComputeNode(self):
        pass

    def isControllerNode(self):
        pass

    def proxy_deviceclass_zproperty(self):
        return 'zOpenStackHostDeviceClass'

    def maintain_proxy_device(self):
        self.ensure_proxy_device()
        self.ensure_service_monitoring()

    def ensure_proxy_device(self):
        # ensure that the host exists.
        self.proxy_device()

    def ensure_service_monitoring(self):
        # Based on the NovaServices we have modeled on the host, ensure that we
        # have the right OSProcess groups detected.
        device = self.proxy_device()

        # If we're getting IPServices directly from the OS (rather than port
        # scannning, there's no good reason to have such a low
        # zIpServiceMapMaxPort value.  It prevents detection of most useful
        # services.
        if device.getZ('zIpServiceMapMaxPort') < 32767:

            LOG.info("Raising zIpServiceMapMaxPort on %s to 32767" % device.name())
            device.setZenProperty('zIpServiceMapMaxPort', 32767)

        if device.getSnmpLastCollection() == DateTime(0):
            LOG.info("Unable to ensure service monitoring until host device is modeled.")
            return

        required_services = set()
        for service in [x for x in self.hostedSoftware()
                        if x.meta_type == 'OpenStackInfrastructureNovaService'
                        and x.enabled]:
            required_services.add(service.binary)

        process_classes = [p.osProcessClass().getPrimaryUrlPath()
                           for p in device.getDeviceComponents(type='OSProcess')]

        detected_services = [pc.split('/')[6] for pc in process_classes
                             if pc.split('/')[4] == 'OpenStack']

        # Services we have defined process sets for, and thus can monitor.
        supported_services = [x.id for x in self.dmd.Processes.getSubOSProcessClassesGen()
                              if x.getPrimaryParentOrgName() == '/OpenStack']

        for service in supported_services:
            if service in required_services and service not in detected_services:
                self.dmd.ZenEventManager.sendEvent(dict(
                    device=self.id,
                    summary='OpenStack Host %s is missing OSProcess monitoring for %s process set.' % (device.name(), service),
                    eventClass='/Status/OpenStack',
                    eventKey='ServiceMonitoring-' + service,
                    severity=Warning,
                    ))
            else:
                self.dmd.ZenEventManager.sendEvent(dict(
                    device=self.id,
                    summary='Openstack Host %s monitoring for %s process set has been enabled.' % (device.name(), service),
                    eventClass='/Status/OpenStack',
                    eventKey='ServiceMonitoring-' + service,
                    severity=Clear,
                    ))

    def devicelink_descr(self):
        '''
        The description to put on the proxy device's expanded links section when linking
        back to this component.
        '''
        return 'Host %s in OpenStack %s' % (
            self.name(),
            self.device().name()
        )
