##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

from importlib import import_module


def optional_import(module_name, patch_module_name):
    '''
    Import patch_module_name only if module_name is importable.
    '''
    try:
        import_module(module_name)
    except ImportError:
        pass
    else:
        import_module(
            '.{0}'.format(patch_module_name),
            'ZenPacks.zenoss.OpenStackInfrastructure.patches')


optional_import('Products.ZenModel', 'platform')
optional_import('Products.ZenModel', 'duplicateips')
