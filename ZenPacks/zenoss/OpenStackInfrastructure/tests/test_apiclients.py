#!/usr/bin/env python

###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2020, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################

from mock import Mock

from twisted.internet.defer import inlineCallbacks

from Products.ZenTestCase.BaseTestCase import BaseTestCase

from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import setup_crochet
from ZenPacks.zenoss.OpenStackInfrastructure.apiclients.base import BaseClient
from ZenPacks.zenoss.OpenStackInfrastructure.apiclients.session import base_url

crochet = setup_crochet()


class TestApiClients(BaseTestCase):

    def test_base_url_strip(self):
        url = base_url('http://www.test.com/')
        self.assertEquals(url, 'http://www.test.com')

    def test_base_url_no_change(self):
        url = base_url('http://www.test.com')
        self.assertEquals(url, 'http://www.test.com')

    def test_base_url_none(self):
        url = base_url(None)
        self.assertEquals(url, None)

    @crochet.wait_for(timeout=5)
    @inlineCallbacks
    def test_base_client_without_url(self):
        session_manager = Mock()
        session_manager.get_service_url.return_value = None
        base_client = BaseClient(session_manager=session_manager)
        result = yield base_client.get_json('http://www.test.com')
        self.assertEquals(result, {})

    @crochet.wait_for(timeout=5)
    @inlineCallbacks
    def test_base_client_valid_url(self):
        session_manager = Mock()
        session_manager.get_service_url.return_value = 'test'
        session_manager.authenticated_GET_request.return_value = ('{"key":["value"]}', None)
        base_client = BaseClient(session_manager=session_manager)
        result = yield base_client.get_json('http://www.test.com')
        self.assertEquals(result, {u'key': [u'value']})


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestApiClients))
    return suite


if __name__ == "__main__":
    from zope.testrunner.runner import Runner
    runner = Runner(found_suites=[test_suite()])
    runner.run()
