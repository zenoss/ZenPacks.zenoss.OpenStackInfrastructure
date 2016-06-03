##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from ZenPacks.zenoss.DynamicView import TAG_ALL, TAG_IMPACTED_BY, TAG_IMPACTS
from ZenPacks.zenoss.DynamicView.model.adapters import BaseRelationsProvider


class LinuxDeviceRelationsProvider_OSI(BaseRelationsProvider):
    def relations(self, type=TAG_ALL):
        if type in (TAG_ALL, TAG_IMPACTED_BY):
            instance = self._adapted.openstackInstance()
            if instance:
                yield self.constructRelationTo(instance, TAG_IMPACTED_BY)

        if type in (TAG_ALL, TAG_IMPACTS):
            host = self._adapted.openstack_hostComponent()
            if host:
                yield self.constructRelationTo(host, TAG_IMPACTS)


class OSProcessRelationsProvider_OSI(BaseRelationsProvider):
    def relations(self, type=TAG_ALL):
        if type in (TAG_ALL, TAG_IMPACTS):
            software_component = self._adapted.openstack_softwareComponent()
            if software_component:
                # impact the corresponding software software component
                yield self.constructRelationTo(software_component, TAG_IMPACTS)
