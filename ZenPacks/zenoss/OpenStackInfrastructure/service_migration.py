##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016-2019, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger("zen.migrate")

from ZenPacks.zenoss.OpenStackInfrastructure.utils import zenpack_path

try:
    import servicemigration as sm
    sm.require("1.0.0")
    VERSION5 = True
except ImportError:
    VERSION5 = False

import copy
import os


def force_update_configs(zenpack, service_name, config_filenames):
    # update the specified config filenames to match those provided in the
    # zenpack.  Any local changes to them will be overwritten.

    if not VERSION5:
        return

    try:
        ctx = sm.ServiceContext()
    except sm.ServiceMigrationError:
        log.info("Couldn't generate service context, skipping.")
        return

    for svc in ctx.services:
        if svc.name != service_name:
            continue

        for cfile in svc.configFiles:
            if cfile.filename.lstrip('/') in config_filenames:
                with open(os.path.join(zenpack.path('service_definition/-CONFIGS-/'), cfile.filename.lstrip('/'))) as f:
                    content = f.read()

                if cfile.content != content:
                    log.info("Updating %s", cfile.filename)
                    cfile.content = content

    ctx.commit()


def remove_migrate_zenpython():
    if not VERSION5:
        return

    try:
        ctx = sm.ServiceContext()
    except sm.ServiceMigrationError:
        log.info("Couldn't generate service context, skipping.")
        return

    commit = False
    zpythons = filter(lambda s: s.name == "zenpython", ctx.services)
    log.info("Found %i services named 'zenpython'" % len(zpythons))
    for zpython in zpythons:
        rbtamqp_imports = filter(lambda ep: ep.name == "rabbitmqs_ceil" and ep.purpose == "import_all", zpython.endpoints)
        if len(rbtamqp_imports) > 0:
            zpython.endpoints = filter(lambda ep: not (ep.name == "rabbitmqs_ceil" and ep.purpose == "import_all"), zpython.endpoints)
            commit = True
            log.info("Removing the rabbitmqs_ceil import endpoint from service '%s'." % ctx.getServicePath(zpython))
        rbtmgmt_imports = filter(lambda ep: ep.name == "rabbitmqadmins_ceil" and ep.purpose == "import_all", zpython.endpoints)
        if len(rbtmgmt_imports) > 0:
            zpython.endpoints = filter(lambda ep: not (ep.name == "rabbitmqadmins_ceil" and ep.purpose == "import_all"), zpython.endpoints)
            commit = True
            log.info("Removing the rabbitmqadmins_ceil import endpoint from service '%s'." % ctx.getServicePath(zpython))
    if commit:
        ctx.commit()
