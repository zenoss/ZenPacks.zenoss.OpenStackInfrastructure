##############################################################################
#
# GPLv2
#
# You should have received a copy of the GNU General Public License
# along with this ZenPack. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


from zope.interface import implements
from Products.ZenModel.ZenossSecurity import ZEN_CHANGE_DEVICE
from Products.Zuul.form import schema
from Products.Zuul.infos import ProxyProperty
from Products.Zuul.utils import ZuulMessageFactory as _t
from Products.ZenModel.Device import Device
from Products.Zuul.infos.device import DeviceInfo
from Products.Zuul.interfaces import IDeviceInfo
from Products.ZenRelations.RelSchema import ToMany, ToOne
from ZenPacks.zenoss.OpenStack.utils import updateToMany


class Endpoint(Device):
    meta_type = portal_type = 'Endpoint'

    Klasses = [Device]

    _relations = ()
    for Klass in Klasses:
        _relations = _relations + getattr(Klass, '_relations', ())

    _relations = _relations + (
        ('components', ToMany(
            ToOne, 'ZenPacks.zenoss.OpenStack.OpenstackComponent', 'endpoint',
        )),
    )

    factory_type_information = ({
        'actions': ({
            'id': 'perfConf',
            'name': 'Template',
            'action': 'objTemplates',
            'permissions': (ZEN_CHANGE_DEVICE,),
            },),
        },)

    def device(self):
        '''
        Return device under which this component/device is contained.
        '''
        return self


    def getOpenstackComponentIds(self):
        '''
        Return a sorted list of each openstackcomponent id related to this
        Aggregate.

        Used by modeling.
        '''

        return sorted([openstackcomponent.id for openstackcomponent in self.openstackcomponents.objectValuesGen()])

    def setOpenstackComponentIds(self, ids):
        '''
        Update OpenstackComponent relationship given ids.

        Used by modeling.
        '''
        updateToMany(
            relationship=self.openstackcomponents,
            root=self.device(),
            type_='ZenPacks.zenoss.OpenStack.OpenstackComponent',
            ids=ids)


class IEndpointInfo(IDeviceInfo):
    openstackcomponent_count = schema.Int(title=_t(u'Number of OpenstackComponents'))

    username = schema.Text(title=_t(u"Username"))
    project_id = schema.Text(title=_t(u"Project ID"))
    auth_url = schema.Text(title=_t(u"Auth URL"))
    region_name = schema.Text(title=_t(u"Region Name"))
    server_count = schema.Int(title=_t(u"Total Servers"))
    flavor_count = schema.Int(title=_t(u"Total Flavors"))
    image_count = schema.Int(title=_t(u"Total Images"))

class EndpointInfo(DeviceInfo):
    implements(IEndpointInfo)

    @property
    def openstackcomponent_count(self):
        # Using countObjects is fast.
        try:
            return self._object.openstackcomponents.countObjects()
        except:
            # Using len on the results of calling the relationship is slow.
            return len(self._object.openstackcomponents())

    @property
    def username(self):
        return self._object.primaryAq().zCommandUsername

    @property
    def project_id(self):
        return self._object.primaryAq().zOpenStackProjectId

    @property
    def auth_url(self):
        return self._object.primaryAq().zOpenStackAuthUrl

    @property
    def api_version(self):
        return self._object.primaryAq().zOpenstackComputeApiVersion

    @property
    def region_name(self):
        return self._object.primaryAq().zOpenStackRegionName

    @property
    def flavor_count(self):
        return self._object.flavors.countObjects()

    @property
    def image_count(self):
        return self._object.images.countObjects()

    @property
    def server_count(self):
        return self._object.servers.countObjects()