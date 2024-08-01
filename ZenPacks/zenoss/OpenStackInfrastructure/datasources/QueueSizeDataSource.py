##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014-2024, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from zope.component import adapts
from zope.interface import implements

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import (
    PythonDataSource, PythonDataSourcePlugin, PythonDataSourceInfo,
    IPythonDataSourceInfo)

from ZenPacks.zenoss.OpenStackInfrastructure.utils import add_local_lib_path, result_errmsg

class QueueSizeDataSource(PythonDataSource):
    '''
    Deprecated. Need to delete with the next release.
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack AMQP Queue Size',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 30

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'QueueSizeDataSource.QueueSizeDataSourcePlugin'

    # QueueSizeDataSource
    _properties = PythonDataSource._properties + ()


class IQueueSizeDataSourceInfo(IPythonDataSourceInfo):
    '''
    Deprecated. Need to delete with the next release.
    '''
    pass


class QueueSizeDataSourceInfo(PythonDataSourceInfo):
    '''
    Deprecated. Need to delete with the next release.
    '''

    implements(IQueueSizeDataSourceInfo)
    adapts(QueueSizeDataSource)

    testable = False


class QueueSizeDataSourcePlugin(PythonDataSourcePlugin):
    """
    Deprecated. Need to delete with the next release.
    """
    pass
