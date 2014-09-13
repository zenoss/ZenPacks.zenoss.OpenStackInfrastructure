##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import basereportable
from ZenPacks.zenoss.OpenStackInfrastructure.SoftwareComponent import SoftwareComponent


class BaseReportable(basereportable.BaseReportable):

    @classmethod
    def entity_class_for_class(cls, object_class):
        entity_class = super(BaseReportable, cls).entity_class_for_class(object_class)
        return entity_class.replace("open_stack", "openstack")

    @property
    def export_as_bases(self):
        bases = super(BaseReportable, self).export_as_bases

        # Anything that is a softwarecomponent subclass, also export
        # as a softwarecomponent.
        if isinstance(self.context, SoftwareComponent):
            bases.append(SoftwareComponent)

        return bases


class BaseReportableFactory(basereportable.BaseReportableFactory):
    pass
