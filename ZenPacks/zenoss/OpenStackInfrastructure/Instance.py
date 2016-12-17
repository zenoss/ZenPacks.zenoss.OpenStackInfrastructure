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
LOG = logging.getLogger('zen.OpenStackInfrastructureInstance')

from ZenPacks.zenoss.OpenStackInfrastructure.utils import findIpInterfacesByMAC

class Instance(schema.Instance):

    # The host that this instance is running on (derived from the hypervisor)
    def host(self):
        try:
            return self.hypervisor().host()
        except Exception:
            return None

    def guestDevice(self):
        macs = [x.macaddress for x in self.vnics()]

        for interface in findIpInterfacesByMAC(self.dmd, macs):
            return interface.device()

        return None

    def get_host_name(self):
        if self.host():
            return self.host().titleOrId()

    def set_host_name(self, hostname):
        search = self.device().componentSearch

        # Code below may have some bearing on ZEN-24803
        hosts = []
        for h in search(titleOrId=hostname,
                        meta_type='OpenStackInfrastructureHost'):
            try:
                host = h.getObject()
            except Exception:
                # ignore a stale entry
                pass
            else:
                hosts.appens(host)

        hypervisors = []
        for host in hosts:
            if host.hypervisor() and host.titleOrId() == hostname:
                hypervisors.append(host.hypervisor().id)

        if len(hypervisors):
            hypervisor = sorted(hypervisors)[0]
            if len(hypervisors) > 1:
                LOG.error("Multiple hypervisors were found matching hostname %s - Choosing %s" %
                          (hostname, hypervisor))
            self.set_hypervisor(hypervisor)
        else:
            LOG.warning("No matching host hypervisor found for name %s" % hostname)

        return

    def get_tenant_id(self):
        if self.tenant():
            return self.tenant().tenantId

    def set_tenant_id(self, tenant_id):
        return self.set_tenant('tenant-{0}'.format(tenant_id))

    def get_flavor_name(self):
        if self.flavor():
            return self.flavor().titleOrId()

    def set_flavor_name(self, flavorname):
        search = self.device().componentSearch
        flavors = []
        for f in search(titleOrId=flavorname,
                        meta_type='OpenStackInfrastructureFlavor'):
            try:
                flavor = f.getObject()
            except Exception:
                # ignore a stale entry
                pass
            else:
                flavors.appens(flavor)
        if len(flavors):
            flavor = sorted(flavors)[0]
            if len(flavors) > 1:
                LOG.error("Multiple flavors were found matching name %s - Choosing %s" %
                          (flavorname, flavor))
            self.set_flavor(flavor)
        else:
            LOG.warning("No matching flavor found for name %s" % flavorname)

    def get_image_name(self):
        if self.image():
            return self.image().titleOrId()

    def set_image_name(self, imagename):
        search = self.device().componentSearch
        images = []
        for i in search(titleOrId=imagename,
                        meta_type='OpenStackInfrastructureImage'):
            try:
                image = i.getObject()
            except Exception:
                # ignore a stale entry
                pass
            else:
                images.appens(image)
        if len(images):
            image = sorted(images)[0]
            if len(images) > 1:
                LOG.error("Multiple images were found matching name %s - Choosing %s" %
                          (imagename, image))
            self.set_image(image)
        else:
            LOG.warning("No matching image found for name %s" % imagename)


class DeviceLinkProvider(object):
    '''
Provides a link on the (guest) device overview page to the VM which the
guest is running within.
'''
    def __init__(self, device):
        self._device = device

    def getExpandedLinks(self):
        instance = self._device.openstackInstance()
        if instance:
            return ['<a href="%s">Instance \'%s\' on OpenStack %s</a>' % (
                instance.getPrimaryUrlPath(), instance.titleOrId(), instance.device().titleOrId())]

        return []
