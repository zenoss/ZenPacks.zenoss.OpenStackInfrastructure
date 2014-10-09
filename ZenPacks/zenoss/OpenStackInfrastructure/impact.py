##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from zope.component import adapts
from zope.interface import implements

from Products.ZenUtils.guid.interfaces import IGlobalIdentifier
from ZenPacks.zenoss.Impact.impactd.relations import ImpactEdge
from ZenPacks.zenoss.Impact.impactd.interfaces import IRelationshipDataProvider

from Products.ZenModel.Device import Device
from Products.ZenModel.OSProcess import OSProcess

ZENPACK_NAME = 'ZenPacks.zenoss.OpenStackInfrastructure'


class BaseRelationshipDataProvider(object):
    '''
    Abstract base for IRelationshipDataProvider adapter factories.
    '''
    implements(IRelationshipDataProvider)

    relationship_provider = ZENPACK_NAME

    impacts = None
    impacted_by = None

    def __init__(self, adapted):
        self.adapted = adapted

    def belongsInImpactGraph(self):
        """Return True so generated edges will show in impact graph.

        Required by IRelationshipDataProvider.

        """
        return True

    def getEdges(self):
        """Generate ImpactEdge instances for adapted object.

        Required by IRelationshipDataProvider.

        """
        provider = self.relationship_provider
        myguid = IGlobalIdentifier(self.adapted).getGUID()

        if self.impacted_by:
            for methodname in self.impacted_by:
                for impactor_guid in self.get_remote_guids(methodname):
                    yield ImpactEdge(impactor_guid, myguid, provider)

        if self.impacts:
            for methodname in self.impacts:
                for impactee_guid in self.get_remote_guids(methodname):
                    yield ImpactEdge(myguid, impactee_guid, provider)

    def get_remote_guids(self, methodname):
        """Generate object GUIDs returned by adapted.methodname()."""

        method = getattr(self.adapted, methodname, None)
        if not method or not callable(method):
            return

        r = method()
        if not r:
            return

        try:
            for obj in r:
                yield IGlobalIdentifier(obj).getGUID()

        except TypeError:
            yield IGlobalIdentifier(r).getGUID()


class HostDeviceRelationsProvider(BaseRelationshipDataProvider):
    adapts(Device)

    # A linux device that is also an openstack host impacts that host component.
    impacts = ['openstack_hostComponent']


class OSProcessRelationsProvider(BaseRelationshipDataProvider):
    adapts(OSProcess)

    def getEdges(self):
        for base_edge in BaseRelationshipDataProvider.getEdges(self):
            yield base_edge

        host = self.adapted.device().openstack_hostComponent()
        if host:
            for software in host.hostedSoftware():
                if software.binary == self.adapted.osProcessClass().id:
                    # impact the corresponding software software component
                    yield ImpactEdge(
                        IGlobalIdentifier(self.adapted).getGUID(),
                        IGlobalIdentifier(software).getGUID(),
                        self.relationship_provider
                    )


class GuestDeviceRelationsProvider(BaseRelationshipDataProvider):
    adapts(Device)

    impacted_by = ['openstackInstance']
