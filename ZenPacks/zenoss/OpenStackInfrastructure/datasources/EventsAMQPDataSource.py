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

from Products.Zuul.infos import ProxyProperty

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import (
    PythonDataSource, PythonDataSourcePlugin )

from Products.Zuul.infos.template import RRDDataSourceInfo
from Products.Zuul.interfaces import IRRDDataSourceInfo


class EventsAMQPDataSource(PythonDataSource):
    '''
    Deprecated. Need to delete with the next release.
    '''

    ZENPACKID = 'ZenPacks.zenoss.OpenStackInfrastructure.'

    sourcetypes = ('OpenStack Ceilometer Events AMQP',)
    sourcetype = sourcetypes[0]

    # RRDDataSource
    component = '${here/id}'
    cycletime = 30

    # PythonDataSource
    plugin_classname = 'ZenPacks.zenoss.OpenStackInfrastructure.datasources.'\
        'EventsAMQPDataSource.EventsAMQPDataSourcePlugin'

    # EventsAMQPDataSource

    _properties = PythonDataSource._properties + ()


class IEventsAMQPDataSourceInfo(IRRDDataSourceInfo):
    '''
    Deprecated. Need to delete with the next release.
    '''
    pass

class EventsAMQPDataSourceInfo(RRDDataSourceInfo):
    '''
    Deprecated. Need to delete with the next release.
    '''

    implements(IEventsAMQPDataSourceInfo)
    adapts(EventsAMQPDataSource)

    cycletime = ProxyProperty('cycletime')

    testable = False


class EventsAMQPDataSourcePlugin(PythonDataSourcePlugin):
    """
    Deprecated. Need to delete with the next release.
    """
    pass
