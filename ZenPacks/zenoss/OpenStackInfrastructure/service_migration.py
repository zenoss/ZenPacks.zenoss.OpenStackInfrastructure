##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
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
            "ApplicationTemplate": "rabbitmq_{{(parent .).Name}}_admin",
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
            "ApplicationTemplate": "rabbitmq_{{(parent .).Name}}",
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
            rabbit_amqp.application = "rabbitmq_{}".format(collector)
            zpython.endpoints.append(rabbit_amqp)
            commit = True
        rbtmgmt_imports = filter(lambda ep: ep.name == "rabbitmqadmins_ceil" and ep.purpose == "import_all", zpython.endpoints)
        if len(rbtmgmt_imports) > 0:
            log.info("Service %s already has a rabbitmqadmins_ceil endpoint." % ctx.getServicePath(zpython))
        else:
            log.info("Adding a rabbitmqadmins_ceil import endpoint to service '%s'." % ctx.getServicePath(zpython))
            rabbit_mgmt = sm.Endpoint(**mgmt_endpoint_lc)
            rabbit_mgmt.__data = copy.deepcopy(mgmt_endpoint)
            rabbit_mgmt.application = "rabbitmq_{}_admin".format(collector)
            zpython.endpoints.append(rabbit_mgmt)
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


