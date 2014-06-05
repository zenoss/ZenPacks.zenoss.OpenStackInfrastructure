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
LOG = logging.getLogger('zen.OpenStackHost')

class Host(schema.Host):
    # These will be derived from the services present on the host
    def isComputeNode(self):
        pass

    def isControllerNode(self):
        pass
    
    def ensure_proxy_device(self):
        device = self.proxy_device()

        # Replace the default linux process plugin with our own, which
        # will enforce that certain processes are monitored, and will create
        # instances of ZenPacks.zenoss.OpenStack.OSProcess instead of
        # the default one.
        plugins = device.getZ('zCollectorPlugins')
        plugins.remove('zenoss.cmd.linux.process')    
        if 'zenoss.cmd.linux.openstack.process' not in plugins:
            plugins.append('zenoss.cmd.linux.openstack.process')
        device.setZenProperty('zCollectorPlugins', plugins)

        return True

    def devicelink_descr(self):
        '''
        The description to put on the proxy device's expanded links section when linking
        back to this component.
        '''    
        return 'Host %s in OpenStack instance %s' % (
            self.name(),
            self.device().name()
        )

