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

    def osprocess_component(self):
        try:
            device = self.hostedOn().proxy_device()
            if device:
                for osprocess in device.getDeviceComponents(type='OSProcess'):
                    if osprocess.osProcessClass().id == self.binary:
                        return osprocess
        except Exception:
            pass

        return None

    def getDefaultGraphDefs(self, drange=None):
        """
        Return graph definitions for this software comoponent, along with
        any graphs from the associated OSProcess component.
        """
        graphs = super(SoftwareComponent, self).getDefaultGraphDefs(drange=drange)
        osprocess = self.osprocess_component()
        if osprocess:
            for graph in osprocess.getDefaultGraphDefs(drange):
                graphs.append(graph)

        return graphs

    def getGraphObjects(self, drange=None):
        """
        Return graph definitions for this software comoponent, along with
        any graphs from the associated OSProcess component.
        This method is for 5.x compatibility
        """
        graphs = super(SoftwareComponent, self).getGraphObjects()
        osprocess = self.osprocess_component()
        if osprocess:
            graphs.extend(osprocess.getGraphObjects())
        return graphs
