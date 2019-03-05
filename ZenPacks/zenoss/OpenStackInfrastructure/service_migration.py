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

def fix_service_healthcheck_path():
    # When the zenpack is installed or upgraded, the path to the healthcheck
    # script will need to be updated to reflect the current zenpack path.

    if not VERSION5:
        return

    try:
        ctx = sm.ServiceContext()
    except sm.ServiceMigrationError:
        log.info("Couldn't generate service context, skipping.")
        return

    for svc in ctx.services:
        if svc.name != 'RabbitMQ-Ceilometer':
            continue

        for check in svc.healthChecks:
            if check.name == 'ceilometer-setup':
                log.info("Enabling %s healthcheck for %s", check.name, ctx.getServicePath(svc))
                script_path = zenpack_path('libexec/init_rabbitmq-ceil.sh')
                check.script = script_path + ' {{(getContext . "global.conf.amqpuser")}} {{(getContext . "global.conf.amqppassword")}}'
    ctx.commit()


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


def install_migrate_zenpython():
    if not VERSION5:
        return

    try:
        ctx = sm.ServiceContext()
    except sm.ServiceMigrationError:
        log.info("Couldn't generate service context, skipping.")
        return

    # Create the endpoints we're importing.
    mgmt_endpoint = {
        "ApplicationTemplate": "openstack_rabbitmq_{{(parent .).Name}}_admin",
        "Name": "rabbitmqadmins_ceil",
        "PortNumber": 45672,
        "PortTemplate": "{{plus .InstanceID 45672}}",
        "Protocol": "tcp",
        "Purpose": "import_all"
    }
    mgmt_endpoint_lc = {key.lower(): value for (key, value) in mgmt_endpoint.iteritems()}
    try:
        rabbit_mgmt = sm.Endpoint(**mgmt_endpoint_lc)
    except TypeError:
        mgmt_endpoint_lc = {key.lower(): value for (key, value) in mgmt_endpoint.iteritems() if key != "PortTemplate"}
    amqp_endpoint = {
        "ApplicationTemplate": "openstack_rabbitmq_{{(parent .).Name}}",
        "Name": "rabbitmqs_ceil",
        "PortNumber": 55672,
        "PortTemplate": "{{plus .InstanceID 55672}}",
        "Protocol": "tcp",
        "Purpose": "import_all"
    }
    amqp_endpoint_lc = {key.lower(): value for (key, value) in amqp_endpoint.iteritems()}
    try:
        rabbit_amqp = sm.Endpoint(**amqp_endpoint_lc)
    except TypeError:
        amqp_endpoint_lc = {key.lower(): value for (key, value) in amqp_endpoint.iteritems() if key != "PortTemplate"}

    commit = False
    zpythons = filter(lambda s: s.name == "zenpython", ctx.services)
    log.info("Found %i services named 'zenpython'" % len(zpythons))
    for zpython in zpythons:
        collector = ctx.getServiceParent(zpython).name
        rbtamqp_imports = filter(lambda ep: ep.name == "rabbitmqs_ceil" and ep.purpose == "import_all", zpython.endpoints)
        if len(rbtamqp_imports) > 0:
            log.info("Service %s already has a rabbitmqs_ceil endpoint." % ctx.getServicePath(zpython))
        else:
            log.info("Adding a rabbitmqs_ceil import endpoint to service '%s'." % ctx.getServicePath(zpython))
            rabbit_amqp = sm.Endpoint(**amqp_endpoint_lc)
            rabbit_amqp.__data = copy.deepcopy(amqp_endpoint)
            rabbit_amqp.application = "openstack_rabbitmq_{}".format(collector)
            zpython.endpoints.append(rabbit_amqp)
            commit = True
        rbtmgmt_imports = filter(lambda ep: ep.name == "rabbitmqadmins_ceil" and ep.purpose == "import_all", zpython.endpoints)
        if len(rbtmgmt_imports) > 0:
            log.info("Service %s already has a rabbitmqadmins_ceil endpoint." % ctx.getServicePath(zpython))
        else:
            log.info("Adding a rabbitmqadmins_ceil import endpoint to service '%s'." % ctx.getServicePath(zpython))
            rabbit_mgmt = sm.Endpoint(**mgmt_endpoint_lc)
            rabbit_mgmt.__data = copy.deepcopy(mgmt_endpoint)
            rabbit_mgmt.application = "openstack_rabbitmq_{}_admin".format(collector)
            zpython.endpoints.append(rabbit_mgmt)
            commit = True

    # Fix application names for rabbitmq-ceilometer exports to match the new
    # naming convention as well.
    rabbitmqs = filter(lambda s: s.name == "RabbitMQ-Ceilometer", ctx.services)
    for rabbitmq in rabbitmqs:
        collector = ctx.getServiceParent(rabbitmq).name
        rabbit_application_name = "openstack_rabbitmq_{}".format(collector)
        admin_application_name = "openstack_rabbitmq_{}_admin".format(collector)

        for endpoint in rabbitmq.endpoints:
            if endpoint.application.startswith("rabbitmq"):
                endpoint.application = endpoint.application.replace("rabbitmq", "openstack_rabbitmq")
                commit = True
            if endpoint.applicationtemplate.startswith("rabbitmq"):
                endpoint.applicationtemplate = endpoint.applicationtemplate.replace("rabbitmq", "openstack_rabbitmq")
                commit = True

    if commit:
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
