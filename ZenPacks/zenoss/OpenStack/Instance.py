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
LOG = logging.getLogger('zen.OpenStackInstance')

from ZenPacks.zenoss.OpenStack.utils import findIpInterfacesByMAC

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
            return ['<a href="%s">Openstack VM Instance \'%s\' on %s</a>' % (
                instance.getPrimaryUrlPath(), instance.titleOrId(), instance.device().titleOrId())]

        return []
