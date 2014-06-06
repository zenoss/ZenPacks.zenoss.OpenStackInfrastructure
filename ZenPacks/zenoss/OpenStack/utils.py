##############################################################################
#
# GPLv2
#
# You should have received a copy of the GNU General Public License
# along with this ZenPack. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


import re

from Products.AdvancedQuery import And, Eq
from ZODB.transact import transact

from Products.Zuul.interfaces import ICatalogTool

from Products.ZenUtils.guid.interfaces import IGlobalIdentifier
import functools
import importlib

import logging
LOG = logging.getLogger('ZenPacks.zenoss.OpenStack.utils')


def add_local_lib_path():
    '''
    Helper to add the ZenPack's lib directory to sys.path.
    '''
    import os
    import site

    # The novaclient library does some elaborate things to figure out
    # what version of itself is installed. These seem to not work in
    # our environment for some reason, so we override that and have
    # it report a dummy version that nobody will look at anyway.
    #
    # So, if you're wondering why novaclient.__version__ is 1.2.3.4.5,
    # this is why.
    os.environ['PBR_VERSION'] = '1.2.3.4.5'

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
