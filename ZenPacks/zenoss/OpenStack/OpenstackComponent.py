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
from Products.ZenModel.DeviceComponent import DeviceComponent
from Products.ZenModel.ManagedEntity import ManagedEntity
from Products.ZenRelations.RelSchema import ToMany, ToOne
from ZenPacks.zenoss.OpenStack.utils import updateToOne


class OpenstackComponent(DeviceComponent, ManagedEntity):
    meta_type = portal_type = 'OpenstackComponent'

    Klasses = [DeviceComponent, ManagedEntity]

    _relations = ()
    for Klass in Klasses:
        _relations = _relations + getattr(Klass, '_relations', ())

    _relations = _relations + (
        ('endpoint', ToOne(
            ToMany, 'ZenPacks.zenoss.OpenStack.Endpoint', 'components',
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


    def getEndpointId(self):
        '''
        Return endpoint id or None.

        Used by modeling.
        '''
        obj = self.endpoint()
        if obj:
            return obj.id

    def setEndpointId(self, id_):
        '''
        Set endpoint by id.

        Used by modeling.
        '''
        updateToOne(
            relationship=self.endpoint,
            root=self.device(),
            type_='ZenPacks.zenoss.OpenStack.Endpoint',
            id_=id_)
