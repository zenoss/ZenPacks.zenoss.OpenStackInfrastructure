###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2011, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

def addLocalLibPath():
    """
    Helper to add the ZenPack's lib directory to PYTHONPATH.
    """
    import os
    import site

    # The novaclient library does some elaborate things to figure out 
    # what version of itself is installed.  These seem to not work in
    # our environment for some reason, so we override that and have
    # it report a dummy version that nobody will look at anyway.
    #
    # So, if you're wondering why novaclient.__version__ is 1.2.3.4.5,
    # this is why.
    os.environ['PBR_VERSION'] = '1.2.3.4.5'

    site.addsitedir(os.path.join(os.path.dirname(__file__), 'lib'))

