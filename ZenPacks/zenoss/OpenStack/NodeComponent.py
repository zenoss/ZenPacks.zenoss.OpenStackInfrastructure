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
from ZenPacks.zenoss.OpenStack.DeviceProxyComponent import DeviceProxyComponent
from Products.Zuul.catalog.paths import DefaultPathReporter, relPath
from Products.ZenRelations.RelSchema import ToMany, ToOne
from ZenPacks.zenoss.OpenStack.utils import updateToMany,updateToOne


class NodeComponent(DeviceProxyComponent):
    meta_type = portal_type = 'OpenStackNodeComponent'

    Klasses = [DeviceProxyComponent]

    _relations = ()
    for Klass in Klasses:
        _relations = _relations + getattr(Klass, '_relations', ())

    _relations = _relations + (
        ('hostedSoftware', ToMany(
            ToOne, 'ZenPacks.zenoss.OpenStack.SoftwareComponent', 'hostedOnNode',
        )),
        ('orgcomponent', ToOne(
            ToMany, 'ZenPacks.zenoss.OpenStack.OrgComponent', 'nodecomponents',
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


    def getOrgcomponentId(self):
        '''
        Return orgcomponent id or None.

        Used by modeling.
        '''
        obj = self.orgcomponent()
        if obj:
            return obj.id

    def setOrgcomponentId(self, id_):
        '''
        Set orgcomponent by id.

        Used by modeling.
        '''
        updateToOne(
            relationship=self.orgcomponent,
            root=self.device(),
            type_='ZenPacks.zenoss.OpenStack.OrgComponent',
            id_=id_)

    def getHostedSoftwareIds(self):
        '''
        Return a sorted list of each id from the hostedSoftware relationship
        Aggregate.

        Used by modeling.
        '''

        return sorted([hostedSoftware.id for hostedSoftware in self.hostedSoftware.objectValuesGen()])

    def setHostedSoftwareIds(self, ids):
        '''
        Update hostedSoftware relationship given ids.

        Used by modeling.
        '''
        updateToMany(
            relationship=self.hostedSoftware,
            root=self.device(),
            type_='ZenPacks.zenoss.OpenStack.SoftwareComponent',
            ids=ids)


class NodeComponentPathReporter(DefaultPathReporter):
    def getPaths(self):
        paths = super(NodeComponentPathReporter, self).getPaths()

        obj = self.context.nodecomponents()
        if obj:
            paths.extend(relPath(obj, 'components'))

        return paths
