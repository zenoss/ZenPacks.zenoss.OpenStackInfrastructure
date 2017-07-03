##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016-2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack')

import datetime
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks

from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import \
    PythonDataSourcePlugin

from Products.DataCollector.plugins.DataMaps import ObjectMap
from Products.ZenEvents import ZenEventClasses

import zope.component
from zope.component import getUtility
from Products.Five import zcml

import Products.ZenMessaging.queuemessaging
from zenoss.protocols.interfaces import IAMQPConnectionInfo

zcml.load_config('meta.zcml', zope.component)
zcml.load_config('configure.zcml', zope.component)
zcml.load_config('configure.zcml', Products.ZenMessaging.queuemessaging)

from ZenPacks.zenoss.OpenStackInfrastructure.apiclients.txrabbitadminapi import RabbitMqAdminApiClient

try:
    import servicemigration as sm
    sm.require("1.0.0")
    VERSION5 = True
except ImportError:
    VERSION5 = False

# cache of the last password set for each user during rabbitmq provisioning
USER_PASSWORD = {}

# and the last time it was checked
USER_LASTCHECK = {}


class MaintenanceDataSourcePlugin(PythonDataSourcePlugin):
    proxy_attributes = ()

    @classmethod
    def config_key(cls, datasource, context):
        """
        Return list that is used to split configurations at the collector.

        This is a classmethod that is executed in zenhub. The datasource and
        context parameters are the full objects.
        """
        return (
            context.device().id,
            datasource.getCycleTime(context),
            datasource.plugin_classname,
        )

    @classmethod
    def params(cls, datasource, context):
        return {}

    @inlineCallbacks
    def collect(self, config):
        defer.returnValue(None)
        yield None

    def onSuccess(self, result, config):
        data = self.new_data()

        data['maps'].append(ObjectMap(
            modname='ZenPacks.zenoss.OpenStackInfrastructure.Endpoint',
            data=dict(
                set_ensure_service_monitoring=True
            )
        ))

        return data


class RabbitMQCeilometerCredentialsDataSourcePlugin(PythonDataSourcePlugin):
    proxy_attributes = ()

    @classmethod
    def config_key(cls, datasource, context):
        # We would ideally run one task per username to provision.
        # (not per device), but because the task splitter runs per device,
        # this results in duplicate tasks, which fail silently to be allocated.
        # (See ZEN-27883)
        #
        # Instead, we will run it once per device, but only perform the
        # collection step a maximum of once every 5 minutes.
        return (
            context.device().id,
            datasource.getCycleTime(context),
            datasource.plugin_classname,
            context.zOpenStackAMQPUsername
        )

    @classmethod
    def params(cls, datasource, context):
        return {
            'zOpenStackAMQPUsername': context.zOpenStackAMQPUsername,
            'zOpenStackAMQPPassword': context.zOpenStackAMQPPassword
        }

    @defer.inlineCallbacks
    def collect(self, config):
        ds0 = config.datasources[0]
        user = ds0.params['zOpenStackAMQPUsername']
        password = ds0.params['zOpenStackAMQPPassword']

        if not VERSION5:
            # This datasource is only applicable to v5.
            defer.returnValue(None)

        if not user:
            # the task splitter will still consider no user as a valid
            # task differentiator.  So, if this is the task for the non
            # existant username, just exit without doing anything.
            defer.returnValue(None)

        last_run = USER_LASTCHECK.get(user)
        if last_run and datetime.datetime.now() - last_run < datetime.timedelta(minutes=5):
            # This user has already been checked within the last
            # 5 minutes.
            log.debug(
                "Skipping RabbitMQCeilometerCredentialsDataSourcePlugin for "
                "user %s because it has already run recently", user)
            defer.returnValue(None)

        USER_LASTCHECK[user] = \
            datetime.datetime.now()

        connectionInfo = getUtility(IAMQPConnectionInfo)

        if USER_PASSWORD.get(user, None) != password:
            # password has changed, or not previously been set- go ahead
            # and set that user up.   (note that this will also verify
            # the vhost and exchanges)

            yield self._verify_amqp_credentials(
                vhost='/zenoss',
                user=user,
                password=password,
                admin_host='localhost',
                admin_port='45672',
                admin_user=connectionInfo.user,
                admin_password=connectionInfo.password
            )

        # Store password if we set it successfully.
        USER_PASSWORD[user] = password

    def onSuccess(self, result, config):
        return {
            'events': [{
                'summary': 'RabbitMQ-Ceilometer: successful completion',
                'eventKey': 'RabbitMQCeilometerResult',
                'severity': ZenEventClasses.Clear,
                }],
            }

    def onError(self, result, config):
        return {
            'events': [{
                'summary': 'Error configuring RabbitMQ-Ceilometer: %s' % result,
                'eventKey': 'RabbitMQCeilometerResult',
                'severity': ZenEventClasses.Error,
                }],
            }

    @inlineCallbacks
    def _verify_amqp_credentials(self, vhost, user, password, admin_host, admin_port, admin_user, admin_password):
        client = RabbitMqAdminApiClient(admin_host, admin_port, admin_user, admin_password)

        log.info("Verifying access to RabbitMQ Management HTTP API")
        if not (yield client.verify_access()):
            raise Exception("Cannot access RabbitMQ Management HTTP API http://%s:%s as %s" % (admin_host, admin_port, admin_user))

        log.info("Verifying vhost...")
        success = yield client.does_vhost_exist(vhost)
        if not success:
            success = yield client.add_vhost(vhost)
            if not success:
                raise Exception("Unable to create vhost %s, cannot complete setup" % vhost)

        log.info("Verifying exchanges...")
        for exchange in ('zenoss.openstack.ceilometer', 'zenoss.openstack.heartbeats'):
            success = yield client.does_exchange_exist_on_vhost(exchange, vhost)
            if not success:
                success = yield client.add_exchange_to_vhost(exchange, vhost)
                if not success:
                    raise Exception("Unable to create exchange %s on vhost %s, cannot complete setup" % (exchange, vhost))

        log.info("Verifying user '%s'" % user)
        existing_user = yield client.does_user_exist(user)

        # create user if missing, set password if it exists.
        success = yield client.add_user(user, password)
        if not success:
            raise Exception("Unable to create or update user %s, cannot complete setup" % user)

        if not existing_user:
            # If this is a new user, setup desired permissions
            log.info("Setting up new amqp user's permissions")
            success = yield client.delete_user_permissions_from_all_vhosts(user)
            if success:
                success = yield client.add_user_permissions_to_vhost(user, {"configure": "zenoss.openstack.*",
                                                                            "write": "zenoss.openstack.*",
                                                                            "read": "^$"}, vhost)
            if not success:
                raise Exception("Unable to set permissions for user %s on vhost %s, cannot complete setup" % (user, vhost))
