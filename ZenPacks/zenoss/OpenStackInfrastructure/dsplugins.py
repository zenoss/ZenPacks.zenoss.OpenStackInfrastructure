##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016-2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import \
    PythonDataSourcePlugin

from Products.DataCollector.plugins.DataMaps import ObjectMap

import zope.component
from Products.Five import zcml

import Products.ZenMessaging.queuemessaging

zcml.load_config('meta.zcml', zope.component)
zcml.load_config('configure.zcml', zope.component)
zcml.load_config('configure.zcml', Products.ZenMessaging.queuemessaging)


class MaintenanceDataSourcePlugin(PythonDataSourcePlugin):
    proxy_attributes = ()

    @classmethod
    def config_key(cls, datasource, context):
        """
        Return list that is used to split configurations at the collector.

        This is a classmethod that is executed in zenhub. The datasource and
        context parameters are the full objects.
        """
        return (
            context.device().id,
            datasource.getCycleTime(context),
            datasource.plugin_classname,
        )

    @classmethod
    def params(cls, datasource, context):
        return {}

    @inlineCallbacks
    def collect(self, config):
        defer.returnValue(None)
        yield None

    def onSuccess(self, result, config):
        data = self.new_data()

        data['maps'].append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Endpoint',
            data=dict(
                set_ensure_service_monitoring=True
            )
        ))

        return data
