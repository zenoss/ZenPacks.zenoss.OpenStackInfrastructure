##############################################################################
#
# GPLv2
#
# You should have received a copy of the GNU General Public License
# along with this ZenPack. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import os
import re

from Products.AdvancedQuery import And, Eq
from ZODB.transact import transact

from Products.Zuul.interfaces import ICatalogTool

from Products.ZenUtils.guid.interfaces import IGlobalIdentifier
from collections import deque
import dateutil
import datetime
import functools
import importlib
import pytz
import time

from twisted.internet import reactor
from twisted.internet.error import ConnectionRefusedError, TimeoutError
from twisted.internet.task import deferLater

import logging
LOG = logging.getLogger('zen.OpenStack.utils')


def zenpack_path(path):
    return os.path.join(os.path.dirname(__file__), path)


def add_local_lib_path():
    '''
    Helper to add the ZenPack's lib directory to sys.path.
    '''
    import site

    # The novaclient library does some elaborate things to figure out
    # what version of itself is installed. These seem to not work in
    # our environment for some reason, so we override that and have
    # it report a dummy version that nobody will look at anyway.
    #
    # So, if you're wondering why novaclient.__version__ is 1.2.3.4.5,
    # this is why.
    os.environ['PBR_VERSION'] = '1.2.3.4.5'

    site.addsitedir(os.path.join(os.path.dirname(__file__), '.'))
    site.addsitedir(os.path.join(os.path.dirname(__file__), 'lib'))
    site.addsitedir(os.path.join(os.path.dirname(__file__), 'apiclients'))

add_local_lib_path()


@transact
def schedule_remodel(dmd, device):
    """Schedule the remodeling of device if not already scheduled."""
    pattern = re.compile(r'zenmodeler .+ %s$' % device.id)

    for job in dmd.JobManager.getUnfinishedJobs():
        if pattern.search(job.job_description):
            LOG.info('Model of %s already scheduled', device.id)
            return

    LOG.info('Scheduling model of %s', device.id)
    device.collectDevice(setlog=False, background=True)


def keyword_search(obj, keyword, types=(), meta_type=None):
    """Generate objects with a matching serial number."""
    keyword_query = Eq('searchKeywords', keyword)

    query = None
    if meta_type:
        query = And(Eq('meta_type', meta_type), keyword_query)
    else:
        query = keyword_query

    for brain in ICatalogTool(obj.dmd).search(types, query=query):
        yield brain.getObject()


def device_ip_search(obj, ip_address):
    """Return a device given an IP address."""
    device = obj.getDmdRoot('Devices').findDevice(ip_address)
    if device:
        return device

    ip = obj.getDmdRoot('Networks').findIp(ip_address)
    if ip:
        return ip.device()


def oid_to_string(oid):
    return ''.join(map(chr, map(int, oid.split('.'))))


def string_to_int(value):
    """Convert value to integer for valid comparison."""
    try:
        i = int(value)
    except (ValueError, TypeError):
        i = value

    return i


def guid(obj):
    '''
    Return GUID for obj.
    '''

    return IGlobalIdentifier(obj).getGUID()


def require_zenpack(zenpack_name, default=None):
    '''
    Decorator with mandatory zenpack_name argument.

    If zenpack_name can't be imported, the decorated function or method
    will return default. Otherwise it will execute and return as
    written.

    Usage looks like the following:

        @require_zenpack('ZenPacks.zenoss.Impact')
        @require_zenpack('ZenPacks.zenoss.vCloud')
        def dothatthingyoudo(args):
            return "OK"

        @require_zenpack('ZenPacks.zenoss.Impact', [])
        def returnalistofthings(args):
            return [1, 2, 3]
    '''
    def wrap(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                importlib.import_module(zenpack_name)
            except ImportError:
                return

            return f(*args, **kwargs)

        return wrapper

    return wrap


def lookup_enum(enum_obj, key, default='unknown'):
    '''Take an enumeration dictionary and lookup the value given a key'''

    return enum_obj.get(string_to_int(key), default)


def result_errmsg(result):
    """Return a useful error message string given a twisted errBack result."""
    try:
        if result.type == ConnectionRefusedError:
            return 'connection refused'
        elif result.type == TimeoutError:
            return 'connection timeout'
        else:
            return result.getErrorMessage()
    except AttributeError:
        pass

    return str(result)


_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)


def amqp_timestamp_to_int(timestamp_string):
    # The timestamps arrive in several formats, so we let
    # dateutil.parser.parse() figure them out.
    dt = dateutil.parser.parse(timestamp_string)
    if dt.tzinfo is None:
        LOG.debug("Timestamp string (%s) does not contain a timezone- assuming it is UTC." % timestamp_string)
        dt = pytz.utc.localize(dt)

    return (dt - _EPOCH).total_seconds()


def sleep(sec):
    # Simple helper to delay asynchronously for some number of seconds.
    return deferLater(reactor, sec, lambda: None)


class ExpiringFIFOEntry(object):
    def __init__(self, value, timestamp, expires):
        self.value = value
        self.timestamp = timestamp
        self.expires = expires


class ExpiringFIFO(object):
    '''
    As data arrives via AMQP, we place it into an in-memory cache (for a
    period of time), and then pull it out of the cache during normal collection
    cycles.
    '''

    # seconds to retain entries before discarding them.
    expireTime = None
    queueName = None
    entries = None

    def __init__(self, expireTime, queueName):
        self.expireTime = expireTime
        self.queueName = queueName
        self.entries = deque()

    def _expire(self):
        # remove expired entries from the supplied list (deque)
        now = time.time()

        while len(self.entries) and self.entries[0].expires <= now:
            v = self.entries.popleft()
            LOG.debug("Expired %s@%s from %s", v.value, v.timestamp, self.queueName)

    def add(self, value, timestamp):
        self._expire()
        self.entries.append(ExpiringFIFOEntry(value, timestamp, timestamp + self.expireTime))

    def get(self):
        while True:
            try:
                yield self.entries.popleft()
            except IndexError:
                break


def findIpInterfacesByMAC(dmd, macaddresses, interfaceType=None):
    '''
    Yield IpInterface objects that match the parameters.
    '''
    if not macaddresses:
        return

    layer2_catalog = dmd.ZenLinkManager._getCatalog(layer=2)
    if layer2_catalog is not None:
        for result in layer2_catalog(macaddress=macaddresses):
            iface = result.getObject()
            if not interfaceType or isinstance(iface, interfaceType):
                yield iface

def getIpInterfaceMacs(device):
    '''
    Return all MAC addresses for all interfaces on this device.
    '''
    macs = []
    cat = device.dmd.ZenLinkManager._getCatalog(layer=2)
    if cat is not None:
        brains = cat(deviceId=device.getPrimaryId())
        macs.extend(b.macaddress for b in brains if b.macaddress)

    return macs

def get_port_fixedips(port_fips):
    '''get formatted list of fixed_ip's from Neutron API fixed_ip structure'''
    fixed_ips = set()
    for _fip in port_fips:
        fixed_ips.add(_fip.get('ip_address'))

    return ', '.join(fixed_ips)

def get_subnets_from_fixedips(port_fips):
    '''get formatted list of subnets from Neutron API fixed_ip structure'''
    subnets = set()
    for _fip in port_fips:
        subnets.add(_fip.get('subnet_id'))

    return ['subnet-{0}'.format(x) for x in subnets]

def get_port_instance(device_owner, device_id):
    # If device_owner is part of compute, then add device_id as set_instance
    if 'compute' in device_owner and device_id:
        return 'server-{0}'.format(device_id)

def getNetSubnetsGws_from_GwInfo(external_gateway_info):
    ''' Return (network, subnets, gateways) from external_gateway_info
        type(network): string
        type(subnets): set
        type(gateways): set
    '''
    network = None
    gateways = set()
    subnets = set()

    if not external_gateway_info:
        return (network, subnets, gateways)

    # Network may exist even if fixed_ips dont
    network = external_gateway_info.get('network_id')

    external_fixed_ips = external_gateway_info.get('external_fixed_ips')
    if not external_fixed_ips:
        return (network, subnets, gateways)

    for _ip in external_fixed_ips:
        gateways.add(_ip.get('ip_address', None))
        subnets.add(_ip.get('subnet_id', None))

    return (network, subnets, gateways)


def sanitize_host_or_ip(host):
    '''Return valid IP, else hostname, else ''
    '''
    if not host:
        return ''

    host_RX = re.compile(
                         '^'
                         '(?P<hostname>[\w-]+[\.\-\w]*)'
                         '[^\w\-\.]*'
                         '.*'
                         '$'
                         )

    ip_RX = re.compile(
                         '^'
                         '(?P<ipnumber>[\d]{1,3}\.[\d]{1,3}\.[\d]{1,3}\.[\d]{1,3})'
                         '[^\d\.]*'
                         '.*'
                         '$'
                         )

    # Search IP first: the pattern is easier to parse
    ip_search = ip_RX.search(host)
    if ip_search:
        return ip_search.group('ipnumber')

    host_search = host_RX.search(host)
    if host_search:
        return host_search.group('hostname')

    return ''

# -----------------------------------------------------------------------------
