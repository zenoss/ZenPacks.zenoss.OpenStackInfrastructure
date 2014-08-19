from test_common import SlowSSHServer, ServerProtocol, ClientProtocol
from test_common import SSHServer
from sshclient import SSHClient
from twisted.trial.unittest import TestCase
from twisted.internet import reactor, defer
import getpass
import logging
#logging.basicConfig(level=logging.DEBUG)
#from twisted.python import log as twistedlog
#observer = twistedlog.PythonLoggingObserver()
#observer.start()
log = logging.getLogger('txsshclient.test_timeouts')

import tempfile
import os
import shutil
from twisted.internet.error import TimeoutError


def touch(path):
    with open(path, 'a'):
        os.utime(path, None)


class IPV4FTPTimeoutTestCase(TestCase):
    def setUp(self):
        self.hostname = '127.0.0.1'
        self.user = getpass.getuser()
        self.password = 'dummyTestPassword'
        self.server = SlowSSHServer()
        self.server.protocol = ServerProtocol

        self.port = reactor.listenTCP(0, self.server, interface=self.hostname)
        self.portnum = self.port.getHost().port

        options = {'hostname': self.hostname,
                   'port': self.portnum,
                   'user': self.user,
                   'password': self.password,
                   'buffersize': 32768}

        self.client = SSHClient(options)
        self.client.protocol = ClientProtocol
        self.client.connect()

    def tearDown(self):
        # Shut down the server and client
        log.debug('tearing down')
        port, self.port = self.port, None
        client, self.client = self.client, None
        server, self.server = self.server, None

        # A Deferred for the server listening port
        d = port.stopListening()

        # Tell the client to disconnect and not retry.
        client.disconnect()

        return defer.gatherResults([d,
                                    client.onConnectionLost,
                                    server.onConnectionLost])

    def test_lsdir_timeout_fail(self):
        d = self.client.ls('/tmp', timeout=1)
        return self.assertFailure(d, TimeoutError)

    @defer.inlineCallbacks
    def test_lsdir_timeout_pass(self):
        try:
            test_file = 'test_ls_dir'
            sandbox = tempfile.mkdtemp()
            testfile = '/'.join([sandbox, test_file])
            touch(testfile)
            d = yield self.client.ls(sandbox, timeout=60)

            self.assertEquals(d[0][0], test_file)
            defer.returnValue(d)
        finally:
            shutil.rmtree(sandbox)


class IPV4CommandTimeoutTestCase(TestCase):
    def setUp(self):
        self.hostname = '127.0.0.1'
        self.user = getpass.getuser()
        self.password = 'dummyTestPassword'
        self.server = SSHServer()
        self.server.protocol = ServerProtocol

        self.port = reactor.listenTCP(0, self.server, interface=self.hostname)
        self.portnum = self.port.getHost().port

        options = {'hostname': self.hostname,
                   'port': self.portnum,
                   'user': self.user,
                   'password': self.password,
                   'buffersize': 32768}

        self.client = SSHClient(options)
        self.client.protocol = ClientProtocol
        self.client.connect()

    def tearDown(self):
        # Shut down the server and client
        log.debug('tearing down')
        port, self.port = self.port, None
        client, self.client = self.client, None
        server, self.server = self.server, None

        # A Deferred for the server listening port
        d = port.stopListening()

        # Tell the client to disconnect and not retry.
        client.disconnect()

        return defer.gatherResults([d,
                                    client.onConnectionLost,
                                    server.onConnectionLost])

    def test_run_command_timeout_failed(self):
        d = self.client.run('sleep 2 && ls', timeout=1)
        return self.assertFailure(d, TimeoutError)
