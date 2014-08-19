##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
Patches to be applied to the platform.
'''

import logging
log = logging.getLogger("zen.OpenStack.device")

from Products.ZenUtils.Utils import monkeypatch
from ZenPacks.zenoss.OpenStack.DeviceProxyComponent import DeviceProxyComponent
from Products.DataCollector.ApplyDataMap import ApplyDataMap


@monkeypatch('Products.ZenModel.Device.Device')
def getApplyDataMapToOpenStackEndpoint(self):
    return []

@monkeypatch('Products.ZenModel.Device.Device')
def setApplyDataMapToOpenStackEndpoint(self, datamap):
    mapper = ApplyDataMap()

    component = DeviceProxyComponent.component_for_proxy_device(self)
    if not component:
        log.error("Unable to apply datamap to proxy component for %s (component not found)" % self)
    else:
        mapper._applyDataMap(component.device(), datamap)
