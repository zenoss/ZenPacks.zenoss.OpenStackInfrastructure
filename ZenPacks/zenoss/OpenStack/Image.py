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
from ZenPacks.zenoss.OpenStack.LogicalComponent import LogicalComponent
from Products.Zuul.infos.component import ComponentInfo
from Products.Zuul.interfaces.component import IComponentInfo
from Products.ZenRelations.RelSchema import ToMany, ToOne
from ZenPacks.zenoss.OpenStack.utils import updateToMany


class Image(LogicalComponent):
    meta_type = portal_type = 'OpenStackImage'

    Klasses = [LogicalComponent]

    imageId = None      # 346eeba5-a122-42f1-94e7-06cb3c53f690
    imageStatus = None  # ACTIVE
    imageCreated = None # 010-09-17T07:19:20-05:00
    imageUpdated = None # 010-09-17T07:19:20-05:00

    _properties = ()
    for Klass in Klasses:
        _properties = _properties + getattr(Klass, '_properties', ())

    _properties = _properties + (
        {'id': 'imageUpdated', 'type': 'string', 'mode': 'w'},
        {'id': 'imageCreated', 'type': 'string', 'mode': 'w'},
        {'id': 'imageStatus', 'type': 'string', 'mode': 'w'},
        {'id': 'imageId', 'type': 'string', 'mode': 'w'},
        )

    _relations = ()
    for Klass in Klasses:
        _relations = _relations + getattr(Klass, '_relations', ())

    _relations = _relations + (
        ('servers', ToMany(
            ToOne, 'ZenPacks.zenoss.OpenStack.Server', 'image',
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

    # Query for events by id instead of name.
    event_key = "ComponentId"

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

    def manage_deleteComponent(self, REQUEST=None):
        """
        Delete Component
        """
        try:
            # Default to using built-in method in Zenoss >= 4.2.4.
            return super(Image, self).manage_deleteComponent(REQUEST)
        except AttributeError:
            # Fall back to copying the Zenoss 4.2.4 implementation.
            url = None
            if REQUEST is not None:
                url = self.device().absolute_url()
            self.getPrimaryParent()._delObject(self.id)
            if REQUEST is not None:
                REQUEST['RESPONSE'].redirect(url)

    def getServerIds(self):
        '''
        Return a sorted list of each server id related to this
        Aggregate.

        Used by modeling.
        '''

        return sorted([server.id for server in self.servers.objectValuesGen()])

    def setServerIds(self, ids):
        '''
        Update Server relationship given ids.

        Used by modeling.
        '''
        updateToMany(
            relationship=self.servers,
            root=self.device(),
            type_='ZenPacks.zenoss.OpenStack.Server',
            ids=ids)


class IImageInfo(IComponentInfo):
    server_count = schema.Int(title=_t(u'Number of Servers'))
    imageStatus = schema.Text(title=_t(u"Image Status"))
    imageCreated = schema.Text(title=_t(u"Image Created"))
    imageUpdated = schema.Text(title=_t(u"Image Updated"))


class ImageInfo(ComponentInfo):
    implements(IImageInfo)

    imageUpdated = ProxyProperty('imageUpdated')
    imageCreated = ProxyProperty('imageCreated')
    imageStatus = ProxyProperty('imageStatus')
    imageId = ProxyProperty('imageId')

    @property
    def server_count(self):
        # Using countObjects is fast.
        try:
            return self._object.servers.countObjects()
        except:
            # Using len on the results of calling the relationship is slow.
            return len(self._object.servers())
