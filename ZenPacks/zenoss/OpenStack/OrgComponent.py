##############################################################################
#
# GPLv2
#
# You should have received a copy of the GNU General Public License
# along with this ZenPack. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


from zope.interface import implements
from Products.ZenModel.Device import Device
from Products.ZenModel.ZenossSecurity import ZEN_CHANGE_DEVICE
from Products.Zuul.decorators import info
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.utils import ZuulMessageFactory as _t
from ZenPacks.zenoss.OpenStack.OpenstackComponent import OpenstackComponent
from Products.ZenRelations.RelSchema import ToMany, ToOne
from ZenPacks.zenoss.OpenStack.utils import updateToMany


class OrgComponent(OpenstackComponent):
    meta_type = portal_type = 'OpenStackOrgComponent'

    Klasses = [OpenstackComponent]

    _relations = ()
    for Klass in Klasses:
        _relations = _relations + getattr(Klass, '_relations', ())

    _relations = _relations + (
        ('childOrgs', ToMany(
            ToOne, 'ZenPacks.zenoss.OpenStack.OrgComponent', 'parentOrg',
        )),
        ('nodecomponents', ToMany(
            ToOne, 'ZenPacks.zenoss.OpenStack.NodeComponent', 'orgcomponent',
        )),
        ('softwarecomponents', ToMany(
            ToOne, 'ZenPacks.zenoss.OpenStack.SoftwareComponent', 'orgcomponent',
        )),
    )

    def device(self):
        '''
        Return device under which this component/device is contained.
        '''
        obj = self

        for i in range(200):
            if isinstance(obj, Device):
                return obj

            try:
                obj = obj.getPrimaryParent()
            except AttributeError as exc:
                raise AttributeError(
                    'Unable to determine parent at %s (%s) '
                    'while getting device for %s' % (
                        obj, exc, self))


    def getChildOrgIds(self):
        '''
        Return a sorted list of each id from the childOrgs relationship
        Aggregate.

        Used by modeling.
        '''

        return sorted([childOrg.id for childOrg in self.childOrgs.objectValuesGen()])

    def setChildOrgIds(self, ids):
        '''
        Update childOrgs relationship given ids.

        Used by modeling.
        '''
        updateToMany(
            relationship=self.childOrgs,
            root=self.device(),
            type_='ZenPacks.zenoss.OpenStack.OrgComponent',
            ids=ids)

    def getNodecomponentIds(self):
        '''
        Return a sorted list of each id from the nodecomponents relationship
        Aggregate.

        Used by modeling.
        '''

        return sorted([nodecomponent.id for nodecomponent in self.nodecomponents.objectValuesGen()])

    def setNodecomponentIds(self, ids):
        '''
        Update nodecomponents relationship given ids.

        Used by modeling.
        '''
        updateToMany(
            relationship=self.nodecomponents,
            root=self.device(),
            type_='ZenPacks.zenoss.OpenStack.NodeComponent',
            ids=ids)

    def getSoftwarecomponentIds(self):
        '''
        Return a sorted list of each id from the softwarecomponents relationship
        Aggregate.

        Used by modeling.
        '''

        return sorted([softwarecomponent.id for softwarecomponent in self.softwarecomponents.objectValuesGen()])

    def setSoftwarecomponentIds(self, ids):
        '''
        Update softwarecomponents relationship given ids.

        Used by modeling.
        '''
        updateToMany(
            relationship=self.softwarecomponents,
            root=self.device(),
            type_='ZenPacks.zenoss.OpenStack.SoftwareComponent',
            ids=ids)
