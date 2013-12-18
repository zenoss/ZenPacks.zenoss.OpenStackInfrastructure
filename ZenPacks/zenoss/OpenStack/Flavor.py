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
from Products.ZenUtils.Utils import convToUnits

class Flavor(LogicalComponent):
    meta_type = portal_type = 'OpenStackFlavor'

    Klasses = [LogicalComponent]

    flavorId = None     # 1
    flavorRAM = None    # Stored as bytes
    flavorDisk = None   # Stored as bytes

    _properties = ()
    for Klass in Klasses:
        _properties = _properties + getattr(Klass, '_properties', ())

    _properties = _properties + (
        {'id': 'flavorDisk', 'type': 'int', 'mode': 'w'},
        {'id': 'flavorId', 'type': 'int', 'mode': 'w'},
        {'id': 'flavorRAM', 'type': 'int', 'mode': 'w'},
        )

    _relations = ()
    for Klass in Klasses:
        _relations = _relations + getattr(Klass, '_relations', ())

    _relations = _relations + (
        ('servers', ToMany(
            ToOne, 'ZenPacks.zenoss.OpenStack.Server', 'flavor',
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
            return super(Flavor, self).manage_deleteComponent(REQUEST)
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


class IFlavorInfo(IComponentInfo):
    server_count = schema.Int(title=_t(u'Number of Servers'))

    flavorDisk = schema.Int(title=_t(u'flavorDisks'), readonly=True)
    flavorId = schema.Int(title=_t(u'flavorIds'), readonly=True)
    flavorRAM = schema.Int(title=_t(u'flavorRAMs'), readonly=True)

    flavorRAMString = schema.Text(title=_t(u"Flavor RAM"))
    flavorDiskString = schema.Text(title=_t(u"Flavor Disk"))

class FlavorInfo(ComponentInfo):
    implements(IFlavorInfo)

    flavorDisk = ProxyProperty('flavorDisk')
    flavorId = ProxyProperty('flavorId')
    flavorRAM = ProxyProperty('flavorRAM')

    @property
    def server_count(self):
        # Using countObjects is fast.
        try:
            return self._object.servers.countObjects()
        except:
            # Using len on the results of calling the relationship is slow.
            return len(self._object.servers())

    def flavorRAMString(self):
        return convToUnits(self._object.flavorRAM, 1024, 'B')

    @property
    def flavorDiskString(self):
        return convToUnits(self._object.flavorDisk, 1024, 'B')

