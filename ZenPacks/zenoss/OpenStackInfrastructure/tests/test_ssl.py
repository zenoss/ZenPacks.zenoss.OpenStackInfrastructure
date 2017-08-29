#!/usr/bin/env python

##############################################################################
#
# Copyright (C) Zenoss, Inc. 2017, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

'''
These tests are intended to ensure that PermissiveBrowserLikePolicyForHTTPS
can handle a variety of self-signed cerficates.
'''

import logging
logging.basicConfig(level=logging.WARNING)
log = logging.getLogger('zen.OpenStack')

import os
from socket import gethostname
import ssl
import tempfile
from threading import Thread
import BaseHTTPServer
from OpenSSL import crypto

import Globals
from Products.ZenTestCase.BaseTestCase import BaseTestCase
from Products.ZenUtils.Utils import unused

from twisted.internet import reactor, defer
from twisted.web.client import Agent, HTTPConnectionPool, readBody

from ZenPacks.zenoss.OpenStackInfrastructure.tests.utils import setup_crochet
from ZenPacks.zenoss.OpenStackInfrastructure.apiclients.ssl import PermissiveBrowserLikePolicyForHTTPS

unused(Globals)

crochet = setup_crochet()
pool = HTTPConnectionPool(reactor)


@crochet.wait_for(timeout=30)
def do_nothing():
    return

def create_certificate(altnames=None):
    # create a key pair
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)

    # create a self-signed cert
    cert = crypto.X509()
    subject = cert.get_subject()
    subject.C = "US"
    subject.ST = "Texas"
    subject.L = "Austin"
    subject.O = "Zenoss"
    subject.OU = "Solutions"
    subject.CN = gethostname()
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(24*60*60)
    cert.set_issuer(subject)
    cert.set_pubkey(key)
    cert.set_version(2)

    cert.add_extensions([
        crypto.X509Extension("basicConstraints", False, "CA:FALSE"),
        crypto.X509Extension("subjectKeyIdentifier", False, "hash", subject=cert)
    ])
    cert.add_extensions([
        crypto.X509Extension("authorityKeyIdentifier", False, "keyid:always", issuer=cert),
        crypto.X509Extension("keyUsage", False,  "digitalSignature, nonRepudiation, keyEncipherment"),
    ])

    if altnames:
        cert.add_extensions([
            crypto.X509Extension("subjectAltName", False, ', '.join(altnames))
        ])

    cert.sign(key, 'sha256WithRSAEncryption')

    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        certfile = f.name

    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
        keyfile = f.name

    return certfile, keyfile


def create_webserver_thread(certfile, keyfile):
    # Start a https server running which will handle a single request.
    # Returns the port number and thread object.

    class HTTPServer(BaseHTTPServer.HTTPServer):
        def handle_error(self, request, client_address):
            # shhhh.
            pass

    class HTTPRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

        def do_GET(self):
            body = bytes("Hello")
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, formatstr, *args):
            log.debug(formatstr % args)

    httpd = HTTPServer(('', 0), HTTPRequestHandler)
    port = httpd.socket.getsockname()[1]

    log.info("HTTPS server listening on port %d", port)
    httpd.socket = ssl.wrap_socket(
        httpd.socket,
        certfile=certfile,
        keyfile=keyfile,
        server_side=True)

    os.remove(certfile)
    os.remove(keyfile)

    request_thread = Thread(target=httpd.handle_request)
    request_thread.start()

    return port, request_thread


@crochet.wait_for(timeout=30)
@defer.inlineCallbacks
def http_request(hostname, port):
    url = "https://%s:%d/" % (hostname, port)
    log.debug("Requesting %s", url)

    agent = Agent(
        reactor,
        pool=pool,
        contextFactory=PermissiveBrowserLikePolicyForHTTPS())

    response = yield agent.request('GET', url)
    body = yield readBody(response)

    defer.returnValue(body)


class TestSSL(BaseTestCase):
    '''
    Test suite for HostMap
    '''

    disableLogging = False

    def setUp(self):
        do_nothing()

    def _dotest(self, altnames=None, hostname='localhost'):
        certfile, keyfile = create_certificate(altnames=altnames)

        port, request_thread = create_webserver_thread(certfile, keyfile)

        # Make our (twisted) http request
        result = http_request(hostname, port)
        self.assertTrue(result == "Hello")

        # And wait for the server thread to complete, since it should be done now.
        request_thread.join(30)

    def test_noaltnames(self):
        self._dotest(altnames=None, hostname=gethostname())

    def test_dnsname_simple(self):
        self._dotest(
            altnames=[
                'DNS:%s' % gethostname(),
                'DNS:localhost'])

    def test_ipaddr_simple(self):
        self._dotest(
            altnames=['IP:127.0.0.1'],
            hostname="127.0.0.1")

    def test_dnsname_ip_string(self):
        self._dotest(
            altnames=[
                'DNS:%s' % gethostname(),
                'DNS:localhost',
                'DNS:127.0.0.1',  # technically invalid, but we need this to work.
                'IP:127.0.0.1'],
            hostname="127.0.0.1")


def test_suite():
    from unittest import TestSuite, makeSuite
    suite = TestSuite()
    suite.addTest(makeSuite(TestSSL))
    return suite


if __name__ == "__main__":
    from zope.testrunner.runner import Runner
    runner = Runner(found_suites=[test_suite()])
    runner.run()
