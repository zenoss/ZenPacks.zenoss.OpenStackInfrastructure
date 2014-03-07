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
from Products.Zuul.catalog.paths import DefaultPathReporter, relPath
from Products.ZenRelations.RelSchema import ToMany, ToOne
from ZenPacks.zenoss.OpenStack.utils import updateToOne


class SoftwareComponent(OpenstackComponent):
    meta_type = portal_type = 'OpenStackSoftwareComponent'

    Klasses = [OpenstackComponent]

    _relations = ()
    for Klass in Klasses:
        _relations = _relations + getattr(Klass, '_relations', ())

    _relations = _relations + (
        ('hostedOnNode', ToOne(
            ToMany, 'ZenPacks.zenoss.OpenStack.NodeComponent', 'hostedSoftware',
        )),
        ('orgcomponent', ToOne(
            ToMany, 'ZenPacks.zenoss.OpenStack.OrgComponent', 'softwarecomponents',
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


    def getHostedOnNodeId(self):
        '''
        Return hostedOnNode id or None.

        Used by modeling.
        '''
        obj = self.hostedOnNode()
        if obj:
            return obj.id

    def setHostedOnNodeId(self, id_):
        '''
        Set hostedOnNode by id.

        Used by modeling.
        '''
        updateToOne(
            relationship=self.hostedOnNode,
            root=self.device(),
            type_='ZenPacks.zenoss.OpenStack.NodeComponent',
            id_=id_)

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


class SoftwareComponentPathReporter(DefaultPathReporter):
    def getPaths(self):
        paths = super(SoftwareComponentPathReporter, self).getPaths()

        obj = self.context.hostedSoftware()
        if obj:
            paths.extend(relPath(obj, 'components'))
        obj = self.context.softwarecomponents()
        if obj:
            paths.extend(relPath(obj, 'components'))

        return paths
