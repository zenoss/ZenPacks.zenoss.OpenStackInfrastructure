##############################################################################
#
# Copyright (C) Zenoss, Inc. 2015, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

# Logging
import logging
LOG = logging.getLogger('zen.OpenStackInfrastructureCallhome')

# Zope Imports
from zope.interface import implements

# Zenoss Imports
from Products.ZenCallHome import IDeviceResource

# ZenPack Imports
from .Host import Host
from .Hypervisor import Hypervisor
from .Instance import Instance
from .Router import Router
from .Network import Network
from .Volume import Volume

# Exports
__all__ = [
    'OSI_HOSTS',
    'OSI_HYPERVISORS',
    'OSI_INSTANCES',
    'OSI_ROUTERS',
    'OSI_NETWORKS',
    'OSI_VOLUMES',
    'OSIResource',
    ]

# Constants
OSI_HOSTS = 'OpenStack Infrastructure Host Count'
OSI_HYPERVISORS = 'OpenStack Infrastructure Hypervisor Count'
OSI_INSTANCES = 'OpenStack Infrastructure Instance Count'
OSI_ROUTERS = 'OpenStack Infrastructure Router Count'
OSI_NETWORKS = 'OpenStack Infrastructure Network Count'
OSI_VOLUMES = 'OpenStack Infrastructure Volume Count'


class OSIResource(object):

    """IDeviceResource subscriber for OpenStackInfrastructure."""

    implements(IDeviceResource)

    def __init__(self, device):
        """Initialize OpenStackInfrastructure DeviceResource subscriber."""
        self.device = device

    def processDevice(self, context=None):
        """Add OpenStackInfrastructure counters to context.

        Consider the following counters:

        * OpenStackInfrastructureController Host Count
        * OpenStackInfrastructure Hypervisor Count
        * OpenStackInfrastructure Instance Count
        * OpenStackInfrastructure Router Count
        * OpenStackInfrastructure Network Count
        * OpenStackInfrastructure Volume Count

        """
        counter_keys = (
            OSI_HOSTS,
            OSI_HYPERVISORS,
            OSI_INSTANCES,
            OSI_ROUTERS,
            OSI_NETWORKS,
            OSI_VOLUMES
            )

        # Initialize counters if needed.
        for counter_key in counter_keys:
            if counter_key not in context:
                LOG.debug("initializing %r counter", counter_key)
                context[counter_key] = 0

        hosts = self.device.componentSearch(meta_type=Host.meta_type)
        context[OSI_HOSTS] += len(hosts)
        hypervisors = self.device.componentSearch(meta_type=Hypervisor.meta_type)
        context[OSI_HYPERVISORS] += len(hypervisors)
        instances = self.device.componentSearch(meta_type=Instance.meta_type)
        context[OSI_INSTANCES] += len(instances)
        routers = self.device.componentSearch(meta_type=Router.meta_type)
        context[OSI_ROUTERS] += len(routers)
        networks = self.device.componentSearch(meta_type=Network.meta_type)
        context[OSI_NETWORKS] += len(networks)
        volumes = self.device.componentSearch(meta_type=Volume.meta_type)
        context[OSI_VOLUMES] += len(volumes)
