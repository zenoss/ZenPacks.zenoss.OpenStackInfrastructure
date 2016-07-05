#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from Products.ZenUtils.Utils import unused


# use platform-provided version of sshclient if it's exists and is new
# enough.
try:
    from pkg_resources import parse_version
    from sshclient import __version__ as platform_version
    from .lib.sshclient import __version__ as local_version

    if parse_version(platform_version) < parse_version(local_version):
        # platform version is too old- force use of locally packaged
        # version
        raise ImportError

    from sshclient import SSHClient
except ImportError, e:
    from .lib.sshclient import SSHClient


unused(SSHClient)
