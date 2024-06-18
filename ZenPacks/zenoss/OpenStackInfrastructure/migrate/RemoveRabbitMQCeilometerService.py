##############################################################################
#
# Copyright (C) Zenoss, Inc. 2024, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Remove RabbitMQ-Ceilometer service"""

import logging

from Products.ZenModel.migrate.Migrate import Version
from Products.ZenModel.ZenPack import ZenPackMigration
from service_migration import remove_migrate_zenpython
from Products.Zuul.interfaces import ICatalogTool
from Products.ZenModel.RRDTemplate import RRDTemplate

try:
    import servicemigration as sm
    from Products.ZenUtils.application import ApplicationState
    from Products.ZenUtils.controlplane.application import getConnectionSettings
    from Products.ZenUtils.controlplane import ControlPlaneClient
    from Products.ZenUtils.controlplane import ControlCenterError
except ImportError:
    CONTROL_CENTER = False
else:
    CONTROL_CENTER = True

LOG = logging.getLogger("zen.migrate")

# Name of service to remove.
SERVICE_NAME = "rabbitmq-ceilometer"


class RemoveRabbitMQCeilometerService(ZenPackMigration):
    version = Version(4, 0, 1)

    def migrate(self, pack):
        self.migrate_service(pack)
        self.migrate_templates(pack.dmd)
        self.migrate_zprops(pack.dmd)
        
    def migrate_zprops(self, dmd):
        zprops_to_remove = ["zOpenStackAMQPUsername", "zOpenStackAMQPPassword"]
        for zprop in zprops_to_remove:
            if dmd.Devices.hasProperty(zprop):
                try:
                    dmd.Devices._delProperty(zprop)
                except Exception as e:
                    LOG.warn("Failed to delete zProperty - %s with a message: %s", zprop, e)
            
    def migrate_templates(self, dmd):
        amqp_templates = [
            "Endpoint",
            "Instance",
            "Vnic"
        ]
        ds_types_to_delete = [
            "OpenStack Ceilometer AMQP",
            "OpenStack Ceilometer Events AMQP",
            "OpenStack Ceilometer Heartbeats AMQP"
        ]
        ds_names_to_delete = [
            "rabbitmq-credentials"
        ]
        templates = []
        results = ICatalogTool(dmd.Devices.OpenStack.Infrastructure).search(RRDTemplate)
        if results.total == 0:
            return
        for result in results:
            try:
                template = result.getObject()
            except Exception:
                continue
            if template.id in amqp_templates:
                templates.append(template)
        for template in templates:
            ds_to_delete = []
            for ds in template.datasources():
                if ds.sourcetype in ds_types_to_delete or ds.id in ds_names_to_delete:
                    ds_to_delete.append(ds.id)
            if ds_to_delete:
                try:
                    template.manage_deleteRRDDataSources(ds_to_delete)
                except Exception as e:
                    LOG.warn("Failed to delete datasource - %s with a message: %s", ds_to_delete, e)
            # if the template is empty then remove it
            if len(template.datasources()) == 0:
                try:
                    template.deviceClass().manage_deleteRRDTemplates((template.id,))
                except Exception as e:
                    LOG.warn("Failed to delete template - %s with a message: %s", template.id, e)
        
        
    def migrate_service(self, pack):
        if pack.prevZenPackVersion is None:
            # Do nothing if this is a fresh install of self.version.
            return
        if not CONTROL_CENTER:
            return
          
        sm.require("1.0.0")
        try:
            ctx = sm.ServiceContext()
        except Exception as e:
            LOG.warn("Failed to remove %s service: %s", SERVICE_NAME, e)
            return
        services = get_services_ids(ctx)
        if not services:
            return
        client = ControlPlaneClient(**getConnectionSettings())

        # Stop and remove the old service and rabbitmqs_ceil endpoints in zenpython.
        remove_migrate_zenpython()
        remove_service(client, services)


def get_services_ids(ctx):
    services = []
    """Return service to be removed or None."""
    for service in ctx.services:
        if service.name.lower() == SERVICE_NAME:
            services.append(service)
    return services


def stop_service(client, service):
    """Stop service."""
    service_id = service._Service__data['ID']

    try:
        status = client.queryServiceStatus(service_id)
    except Exception as e:
        LOG.warn("failed to get %s service status: %s", service.name, e)
    else:
        for instance_status in status.itervalues():
            if instance_status.status != ApplicationState.STOPPED:
                try:
                    client.stopService(service_id)
                except Exception as e:
                    LOG.warn("failed to stop %s service: %s", service.name, e)

                return


def remove_service(client, services):
    """Remove service. Stopping it first if necessary."""
    for service in services:
      stop_service(client, service)

      try:
          client.deleteService(service._Service__data['ID'])
          LOG.info("successfuly removed service from serviced: %s", service.name)
      except ControlCenterError as e:
          LOG.warn("failed to remove %s service: %s", service.name, e)
          
          
          
RemoveRabbitMQCeilometerService()
