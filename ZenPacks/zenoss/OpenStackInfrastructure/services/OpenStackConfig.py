##############################################################################
#
# Copyright (C) Zenoss, Inc. 2018-2019, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.services.OpenStackConfig')

from twisted.spread import pb

from Products.ZenCollector.services.config import CollectorConfigService
from Products.ZenRRD.zencommand import DataPointConfig

from ZenPacks.zenoss.OpenStackInfrastructure.Endpoint import Endpoint
from ZenPacks.zenoss.OpenStackInfrastructure.datasources.PerfAMQPDataSource import PerfAMQPDataSource


class OpenStackDataSourceConfig(pb.Copyable, pb.RemoteCopy):
    device = None
    component = None
    template = None
    datasource = None
    points = None
    resourceId = None
    meter = None

    def __init__(self):
        self.points = []


class OpenStackConfig(CollectorConfigService):

    def _filterDevice(self, device):
        return (
            isinstance(device, Endpoint) and
            CollectorConfigService._filterDevice(self, device)
        )

    def _createDeviceProxy(self, device):
        collector = device.getPerformanceServer()

        proxy = CollectorConfigService._createDeviceProxy(self, device)
        proxy.datasources = []
        proxy.thresholds = []
        proxy.zOpenStackProcessEventTypes = device.zOpenStackProcessEventTypes
        proxy.zOpenStackIncrementalShortLivedSeconds = device.zOpenStackIncrementalShortLivedSeconds
        proxy.zOpenStackIncrementalBlackListSeconds = device.zOpenStackIncrementalBlackListSeconds
        proxy.zOpenStackIncrementalConsolidateSeconds = device.zOpenStackIncrementalConsolidateSeconds

        for component in device.getMonitoredComponents():
            proxy.datasources += list(
                self.component_datasources(component, collector))

            proxy.thresholds += component.getThresholdInstances(
                PerfAMQPDataSource.sourcetype)

        return proxy

    def component_datasources(self, component, collector):
        for template in component.getRRDTemplates():

            # Get all enabled datasources that are PerfAMQPDataSources
            datasources = [
                ds for ds in template.getRRDDataSources()
                if ds.enabled and isinstance(ds, PerfAMQPDataSource)]

            device = component.device()

            for ds in datasources:
                datapoints = []

                for dp in ds.datapoints():
                    dp_config = DataPointConfig()
                    dp_config.id = dp.id
                    dp_config.dpName = dp.name()
                    dp_config.component = component.id
                    dp_config.rrdPath = '/'.join((component.rrdPath(), dp.name()))
                    dp_config.rrdType = dp.rrdtype
                    dp_config.rrdCreateCommand = dp.getRRDCreateCommand(collector)
                    dp_config.rrdMin = dp.rrdmin
                    dp_config.rrdMax = dp.rrdmax

                    # MetricMixin.getMetricMetadata() added in Zenoss 5.
                    if hasattr(component, 'getMetricMetadata'):
                        dp_config.metadata = component.getMetricMetadata()

                    datapoints.append(dp_config)

                ds_config = OpenStackDataSourceConfig()
                ds_config.device = device.id
                ds_config.component = component.id
                ds_config.component_meta_type = component.meta_type
                ds_config.template = template.id
                ds_config.datasource = ds.titleOrId()
                ds_config.points = datapoints
                ds_config.meter = ds.meter
                ds_config.resourceId = component.resourceId

                yield ds_config
