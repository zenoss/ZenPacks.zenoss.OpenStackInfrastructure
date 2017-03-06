##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016-2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.rabbitmqadmin')

import Globals
from Products.ZenUtils.Utils import unused
unused(Globals)

import json
import urllib
from base64 import b64encode

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import getPage
from twisted.web.error import Error as TwistedError


class RabbitMqAdminApiClient(object):
    """Class to connect, login, and retrieve data
    """
    def __init__(self, host, port, username, password, timeout=60):
        self._target = 'http://{}:{}'.format(host, port)
        self._username = username
        self._password = password
        self._timeout = int(timeout)
        self._auth = 'Basic {}'.format(b64encode('{}:{}'.format(username, password)))

    @inlineCallbacks
    def _request(self, path, method='GET', data=None):
        """Asynchronously request the URL.
        """

        headers = {
            'User-Agent': 'RabbitMqAdminApiClient',
            'Accept': 'application/json',
            'Authorization': self._auth,
            'Content-Type': 'application/json'
        }

        if data is not None:
            # Intended to be used with PUT method that requires a body be sent
            headers['Content-Length'] = str(len(data))
            # No need to add this header,we send all the time
            # headers['Content-Type'] = 'application/json'

        url = '{0}{1}'.format(self._target, path)
        log.debug('requesting page: {}'.format(url))

        try:
            result = yield getPage(
                url,
                method=method,
                postdata=data,
                headers=headers,
                cookies={},
                timeout=self._timeout
            )
        except TwistedError as e1:
            if e1.status == '204' and e1.message == 'No Content':
                # Usually indicates put/delete success
                returnValue('{"status":"204","message":"No Content"}')
            elif ((e1.status == '401' and e1.message == 'Unauthorized' and e1.response is not None)
                  or (e1.status == '500' and e1.message == 'Internal Server Error' and e1.response is not None)
                  or (e1.status == '404' and e1.message == 'Object Not Found' and e1.response is not None)
                  or (e1.status == '400' and e1.message == 'Bad Request' and e1.response is not None)):
                # We can handle this exception using the json in the response
                returnValue(e1.response)
            else:
                log.error('Could not fetch url {}: {}'.format(url, e1))
                raise
        except Exception as e2:
            log.exception('Failed to retrieve {}: {}'.format(url, e2))
            raise

        returnValue(result)

    @inlineCallbacks
    def json_from_request(self, path, method='GET', data=None):
        """Method to retrieve the json returned
        """

        result = yield self._request(path, method, data)

        if result is not None:
            try:
                log.debug(result)
                out_dict = json.loads(result)
                returnValue(out_dict)
            except Exception as e:
                # We don't care what went wrong as long as we can't decode the
                # json log it and return null
                log.exception('Could not decode JSON "{}": {}'.format(str(result), e))
                raise

        # Should not happen
        returnValue(None)

    @inlineCallbacks
    def does_user_exist(self, username):
        found = False
        json_result = yield self.json_from_request('/api/users')

        if self._does_response_contain_an_error_message(json_result):
            returnValue(False)

        # [{"name":"test","password_hash":"AbcdefghijKlmnOPqrsTuVw/bDM=","tags":"administrator"},{"name":"zenoss","password_hash":"c7885c9c376154362f338f256f4590a7=","tags":"management"}]
        for user in json_result:
            if username == user.get('name', None):
                found = True

        returnValue(found)

    @inlineCallbacks
    def add_user(self, username, password, tags='monitoring'):
        # url encode username because someone might create a user with a slash (just look at the slash in the vhosts we create)
        path = '/api/users/' + urllib.quote(username, '')

        # The tags key is mandatory. tags is a comma-separated list of tags for the user. Currently recognised tags are "administrator", "monitoring" and "management".
        json_result = yield self.json_from_request(path, 'PUT', '{"password":"'+password+'","tags":"'+tags+'"}')

        # did it work?
        if json_result is not None and '204' == json_result.get('status', None):
            returnValue(True)
        returnValue(False)

    @inlineCallbacks
    def delete_user(self, username):
        # url encode username because someone might create a user with a slash (just look at the slash in the /zenoss we create)
        path = '/api/users/' + urllib.quote(username, '')

        json_result = yield self.json_from_request(path, 'DELETE')

        # did it work?
        if json_result is not None and '204' == json_result.get('status', None):
            returnValue(True)
        returnValue(False)

    @inlineCallbacks
    def does_user_have_permissions_on_vhost(self, username, permissionsdict, vhost):
        found = False
        path = '/api/users/' + urllib.quote(username, '') + "/permissions"

        json_result = yield self.json_from_request(path)

        if self._does_response_contain_an_error_message(json_result):
            returnValue(False)

        # [{"user":"zenoss","vhost":"/zenoss","configure":".*","write":".*","read":".*"}]
        for vhostpermission in json_result:
            if username == vhostpermission.get('user', None) and vhost == vhostpermission.get('vhost', None):
                foundConfigurePerm = True
                foundWritePerm = True
                foundReadPerm = True
                # If the caller did not specify a permission to check for we assume anything is ok
                if "configure" in permissionsdict:
                    foundConfigurePerm = (permissionsdict["configure"] == vhostpermission.get('configure', None))
                if "write" in permissionsdict:
                    foundWritePerm = (permissionsdict["write"] == vhostpermission.get('write', None))
                if "read" in permissionsdict:
                    foundReadPerm = (permissionsdict["read"] == vhostpermission.get('read', None))

                # if we found everything we should be good
                found = (foundConfigurePerm and foundWritePerm and foundReadPerm)

        returnValue(found)

    @inlineCallbacks
    def add_user_permissions_to_vhost(self, username, permissionsdict, vhost):
        # All keys are mandatory.
        if 'configure' not in permissionsdict or 'write' not in permissionsdict or 'read' not in permissionsdict:
            log.error("Called add_user_permissions_to_vhost without all 3 permission keys defined (configure, write, read), what we got was: %s", str(permissionsdict))
            returnValue(False)

        # /api/parameters/component/vhost/name
        path = '/api/permissions/' + urllib.quote(vhost, '') + '/' + urllib.quote(username, '')

        json_result = yield self.json_from_request(path, 'PUT', '{"configure":"' + permissionsdict['configure']
                                                                + '","write":"' + permissionsdict['write']
                                                                + '","read":"' + permissionsdict['read'] + '"}')
        # did it work?
        if (not self._does_response_contain_an_error_message(json_result)
            and json_result is not None
            and '204' == json_result.get('status', None)):
            returnValue(True)
        returnValue(False)

    # delete permissions
    @inlineCallbacks
    def delete_user_permissions_from_vhost(self, username, vhost):
        path = '/api/permissions/' + urllib.quote(vhost, '') + '/' + urllib.quote(username, '')
        json_result = yield self.json_from_request(path, 'DELETE')

        # did it work?
        if (not self._does_response_contain_an_error_message(json_result)
            and json_result is not None
            and '204' == json_result.get('status', None)):
            returnValue(True)

        returnValue(False)

    @inlineCallbacks
    def delete_user_permissions_from_all_vhosts(self, username):
        success = True
        path = '/api/users/' + urllib.quote(username, '') + "/permissions"

        json_result = yield self.json_from_request(path)

        for vhostpermission in json_result:
            if username == vhostpermission.get('user', None):
                delete_result = yield self.delete_user_permissions_from_vhost(username, vhostpermission.get('vhost', None))
                if not delete_result:
                    log.error("Unable to delete permissions from vHost %s", vhostpermission.get('vhost', None))
                    success = False
        returnValue(success)

    @inlineCallbacks
    def does_vhost_exist(self, vhostname):
        found = False
        json_result = yield self.json_from_request('/api/vhosts')

        if self._does_response_contain_an_error_message(json_result):
            returnValue(False)

        # [{'tracing': False, 'name': '/'}, {'name': '/zenoss', 'tracing': False, 'messages_details': {'rate': 0.0}, 'messages': 0, 'message_stats': {'publish_details': {'rate': 0.0}, 'deliver_get': 34636, 'publish': 34636, 'get_no_ack': 34636, 'get_no_ack_details': {'rate': 0.0}, 'deliver_get_details': {'rate': 0.0}}, 'messages_unacknowledged_details': {'rate': 0.0}, 'messages_ready_details': {'rate': 0.0}, 'messages_unacknowledged': 0, 'messages_ready': 0}]
        for vhost in json_result:
            if vhostname == vhost.get('name', None):
                found = True

        returnValue(found)

    @inlineCallbacks
    def add_vhost(self, vhostname):
        # url encode vhostname because someone might create a vhost with a slash (just look at the slash in the /zenoss we create)
        path = '/api/vhosts/' + urllib.quote(vhostname, '')
        log.debug(path)

        # The tags key is mandatory. tags is a comma-separated list of tags for the user. Currently recognised tags are "administrator", "monitoring" and "management".
        json_result = yield self.json_from_request(path, 'PUT')

        # did it work?
        if json_result is not None and '204' == json_result.get('status', None):
            returnValue(True)
        returnValue(False)

    @inlineCallbacks
    def delete_vhost(self, vhostname):
        # url encode vhostname because someone might create a vhost with a slash (just look at the slash in the /zenoss we create)
        path = '/api/vhosts/' + urllib.quote(vhostname, '')

        # The tags key is mandatory. tags is a comma-separated list of tags for the user. Currently recognised tags are "administrator", "monitoring" and "management".
        json_result = yield self.json_from_request(path, 'DELETE')

        # did it work?
        if json_result is not None and '204' == json_result.get('status', None):
            returnValue(True)
        returnValue(False)

    @inlineCallbacks
    def does_exchange_exist_on_vhost(self, exchange, vhostname):
        found = False
        # /api/exchanges/vhost/name
        path = '/api/exchanges/' + urllib.quote(vhostname, '')

        json_result = yield self.json_from_request(path)

        # [{u'name': u'', u'durable': True, u'vhost': u'/zenoss', u'internal': False, u'message_stats': {u'publish_out': 43276, u'publish_out_details': {u'rate': 0.0}, u'publish_in': 43276, u'publish_in_details': {u'rate': 0.0}}, u'arguments': {}, u'type': u'direct', u'auto_delete': False}, {u'name': u'amq.direct', u'durable': True, u'vhost': u'/zenoss', u'internal': False, u'arguments': {}, u'type': u'direct', u'auto_delete': False}, {u'name': u'amq.fanout', u'durable': True, u'vhost': u'/zenoss', u'internal': False, u'arguments': {}, u'type': u'fanout', u'auto_delete': False}, {u'name': u'amq.headers', u'durable': True, u'vhost': u'/zenoss', u'internal': False, u'arguments': {}, u'type': u'headers', u'auto_delete': False}, {u'name': u'amq.match', u'durable': True, u'vhost': u'/zenoss', u'internal': False, u'arguments': {}, u'type': u'headers', u'auto_delete': False}, {u'name': u'amq.rabbitmq.trace', u'durable': True, u'vhost': u'/zenoss', u'internal': True, u'arguments': {}, u'type': u'topic', u'auto_delete': False}, {u'name': u'amq.topic', u'durable': True, u'vhost': u'/zenoss', u'internal': False, u'arguments': {}, u'type': u'topic', u'auto_delete': False}, {u'name': u'zenoss.openstack.ceilometer', u'durable': True, u'vhost': u'/zenoss', u'internal': False, u'arguments': {}, u'type': u'topic', u'auto_delete': False}, {u'name': u'zenoss.openstack.heartbeats', u'durable': True, u'vhost': u'/zenoss', u'internal': False, u'arguments': {}, u'type': u'topic', u'auto_delete': False}]
        for vhost in json_result:
            if vhostname == vhost.get('vhost', None) and exchange == vhost.get('name', None):
                found = True
        returnValue(found)

    @inlineCallbacks
    def add_exchange_to_vhost(self, exchange, vhostname):
        # /api/exchanges/vhost/name
        path = '/api/exchanges/' + urllib.quote(vhostname, '') + '/' + urllib.quote(exchange, '')

        # The type key is mandatory; other keys are optional.
        # {"type":"direct","auto_delete":false,"durable":true,"internal":false,"arguments":{}}
        json_result = yield self.json_from_request(path, 'PUT', '{"type":"topic"}')

        # did it work?
        if (not self._does_response_contain_an_error_message(json_result)
            and json_result is not None 
            and '204' == json_result.get('status', None)):
            returnValue(True)

        returnValue(False)

    @inlineCallbacks
    def delete_exchange_from_vhost(self, exchange, vhostname):
        # /api/exchanges/vhost/name
        path = '/api/exchanges/' + urllib.quote(vhostname, '') + '/' + urllib.quote(exchange, '')

        # The type key is mandatory; other keys are optional.
        # {"type":"direct","auto_delete":false,"durable":true,"internal":false,"arguments":{}}
        json_result = yield self.json_from_request(path, 'DELETE')

        # did it work?
        if (not self._does_response_contain_an_error_message(json_result)
            and json_result is not None
            and '204' == json_result.get('status', None)):
            returnValue(True)

        returnValue(False)

    @inlineCallbacks
    def verify_access(self):
        json_result = yield self.json_from_request('/api/whoami')

        if self._does_response_contain_an_error_message(json_result):
            returnValue(False)

        # TODO: Further verification on the data returned?
        returnValue(True)

    def _does_response_contain_an_error_message(self, json_result):
        # Check for json results that indicate this happened
        # {"error":"Unauthorized","reason":"\"Unauthorized\"\n"}
        # {"error":"not_authorised","reason":"Not administrator user"}
        # {"error":"Internal Server Error","reason":"{error, ....}"}
        if type(json_result) not in ['list'] and 'error' in json_result:
            log.error("Unsuccessful, the following error response was returned instead: %s", str(json_result))
            return True
        return False
