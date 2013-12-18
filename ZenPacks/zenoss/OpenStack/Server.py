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
from ZenPacks.zenoss.OpenStack.utils import updateToMany,updateToOne


class Server(LogicalComponent):
    meta_type = portal_type = 'OpenStackServer'

    Klasses = [LogicalComponent]

    serverId = None             # 847424
    serverStatus = None         # ACTIVE
    serverBackupEnabled = None  # False
    serverBackupDaily = None    # DISABLED
    serverBackupWeekly = None   # DISABLED
    publicIps = []              # ['50.57.74.222']
    privateIps = []             # ['10.182.13.13']
    hostId = None               # a84303c0021aa53c7e749cbbbfac265f

    _properties = ()
    for Klass in Klasses:
        _properties = _properties + getattr(Klass, '_properties', ())

    _properties = _properties + (
        {'id': 'hostId', 'type': 'string', 'mode': 'w'},
        {'id': 'serverBackupEnabled', 'type': 'boolean', 'mode': 'w'},
        {'id': 'privateIps', 'type': 'string', 'mode': 'w'},
        {'id': 'serverBackupDaily', 'type': 'string', 'mode': 'w'},
        {'id': 'publicIps', 'type': 'string', 'mode': 'w'},
        {'id': 'serverStatus', 'type': 'string', 'mode': 'w'},
        {'id': 'serverBackupWeekly', 'type': 'string', 'mode': 'w'},
        {'id': 'serverId', 'type': 'int', 'mode': 'w'},
        )

    _relations = ()
    for Klass in Klasses:
        _relations = _relations + getattr(Klass, '_relations', ())

    _relations = _relations + (
        ('flavor', ToOne(
            ToMany, 'ZenPacks.zenoss.OpenStack.Flavor', 'servers',
        )),
        ('hypervisors', ToMany(
            ToOne, 'ZenPacks.zenoss.OpenStack.Hypervisor', 'server',
        )),
        ('image', ToOne(
            ToMany, 'ZenPacks.zenoss.OpenStack.Image', 'servers',
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
            return super(Server, self).manage_deleteComponent(REQUEST)
        except AttributeError:
            # Fall back to copying the Zenoss 4.2.4 implementation.
            url = None
            if REQUEST is not None:
                url = self.device().absolute_url()
            self.getPrimaryParent()._delObject(self.id)
            if REQUEST is not None:
                REQUEST['RESPONSE'].redirect(url)

    def getflavorId(self):
        '''
        Return flavor id or None.

        Used by modeling.
        '''
        obj = self.flavor()
        if obj:
            return obj.id

    def setflavorId(self, id_):
        '''
        Set flavor by id.

        Used by modeling.
        '''
        updateToOne(
            relationship=self.flavor,
            root=self.device(),
            type_='ZenPacks.zenoss.OpenStack.Flavor',
            id_=id_)

    def getimageId(self):
        '''
        Return image id or None.

        Used by modeling.
        '''
        obj = self.image()
        if obj:
            return obj.id

    def setimageId(self, id_):
        '''
        Set image by id.

        Used by modeling.
        '''
        updateToOne(
            relationship=self.image,
            root=self.device(),
            type_='ZenPacks.zenoss.OpenStack.Image',
            id_=id_)

    def getHypervisorIds(self):
        '''
        Return a sorted list of each hypervisor id related to this
        Aggregate.

        Used by modeling.
        '''

        return sorted([hypervisor.id for hypervisor in self.hypervisors.objectValuesGen()])

    def setHypervisorIds(self, ids):
        '''
        Update Hypervisor relationship given ids.

        Used by modeling.
        '''
        updateToMany(
            relationship=self.hypervisors,
            root=self.device(),
            type_='ZenPacks.zenoss.OpenStack.Hypervisor',
            ids=ids)

    def getIconPath(self):
        return '/++resource++openstack/img/openstack.png'

    def getGuestDevice(self):
        server_ips = []

        if len(self.publicIps) > 0:
            server_ips.extend(self.publicIps)

        if len(self.privateIps) > 0:
            server_ips.extend(self.privateIps)

        for server_ip in server_ips:
            device = self.dmd.Devices.findDeviceByIdOrIp(server_ip)
            if device:
                return device

            ip = self.dmd.Networks.findIp(server_ip)
            if ip:
                return ip.device()

        return None

    def getDefaultGraphDefs(self, drange=None):
        """
        Currently no metrics are collected directly from servers. Pull in the
        graphs from the associated guest device if it is known.
        """
        graphs = []

        guestDevice = self.getGuestDevice()
        if guestDevice:
            for guest_graph in guestDevice.getDefaultGraphDefs(drange):
                graphs.append(dict(
                    title='{0} (Guest Device)'.format(guest_graph['title']),
                    url=guest_graph['url']))

        return graphs



class IServerInfo(IComponentInfo):
    hypervisor_count = schema.Int(title=_t(u'Number of Hypervisors'))

    serverStatus = schema.Text(title=_t(u"Server Status"))
    publicIps = schema.List(title=_t(u"Public IPs"))
    privateIps = schema.List(title=_t(u"Private IPs"))
    flavor = schema.Entity(title=_t(u"Server Flavor"))
    image = schema.Entity(title=_t(u"Server Image"))
    serverBackupEnabled = schema.Bool(title=_t(u"Server Backup Enabled"))
    serverBackupDaily = schema.Text(title=_t(u"Server Backup Daily"))
    serverBackupWeekly = schema.Text(title=_t(u"Server Backup Weekly"))
    hostId = schema.Text(title=_t(u"Host ID"))
    guestDevice = schema.Entity(title=_t(u"Guest Device"))


class ServerInfo(ComponentInfo):
    implements(IServerInfo)

    hostId = ProxyProperty('hostId')
    serverBackupEnabled = ProxyProperty('serverBackupEnabled')
    privateIps = ProxyProperty('privateIps')
    serverBackupDaily = ProxyProperty('serverBackupDaily')
    publicIps = ProxyProperty('publicIps')
    serverStatus = ProxyProperty('serverStatus')
    serverBackupWeekly = ProxyProperty('serverBackupWeekly')
    serverId = ProxyProperty('serverId')

    @property
    def hypervisor_count(self):
        # Using countObjects is fast.
        try:
            return self._object.hypervisors.countObjects()
        except:
            # Using len on the results of calling the relationship is slow.
            return len(self._object.hypervisors())

    @property
    @info
    def flavor(self):
        return self._object.flavor()

    @property
    @info
    def image(self):
        return self._object.image()

    @property
    @info
    def guestDevice(self):
        return self._object.getGuestDevice()

