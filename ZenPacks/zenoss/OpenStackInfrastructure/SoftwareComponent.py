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
LOG = logging.getLogger('zen.OpenStackSoftwareComponent')


class SoftwareComponent(schema.SoftwareComponent):

    def osprocess_components(self):
        try:
            device = self.hostedOn().proxy_device()
            if device:
                os_processes = filter(
                    lambda x: x.osProcessClass().id == self.binary,
                    device.getDeviceComponents(type='OSProcess')
                )
                return os_processes
        except Exception:
            pass

        return []

    def getDefaultGraphDefs(self, drange=None):
        """
        Return graph definitions for this software comoponent, along with
        any graphs from the associated OSProcess component.
        """
        graphs = super(SoftwareComponent, self).getDefaultGraphDefs(drange=drange)
        os_processes = self.osprocess_components()
        for os_process in os_processes:
            for graph in os_process.getDefaultGraphDefs(drange):
                graphs.append(graph)

        return graphs

    def getGraphObjects(self, drange=None):
        """
        Return graph definitions for this software comoponent, along with
        any graphs from the associated OSProcess component.
        This method is for 5.x compatibility
        """
        graphs = super(SoftwareComponent, self).getGraphObjects()
        os_processes = self.osprocess_components()
        for os_process in os_processes:
            graphs.extend(os_process.getGraphObjects())

        return graphs
