from test_common import SSHServer, ServerProtocol, ClientProtocol
from sshclient import SSHClient
from twisted.trial.unittest import TestCase
from twisted.internet import reactor, defer
import getpass
import logging
log = logging.getLogger('txsshclient.test_exec')

from twisted.internet.error import ConnectionDone, ConnectError, ConnectionLost
import os
import shutil
import tempfile
import logging
#logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.INFO)
#from twisted.python import log as twistedlog
#observer = twistedlog.PythonLoggingObserver()
#observer.start()
log = logging.getLogger('txsshclient.test_errors')


def touch(path):
    with open(path, 'a'):
        os.utime(path, None)


class IPV4FunctionalNoServerTestCase(TestCase):
    def setUp(self):
        self.hostname = '127.0.0.1'
        self.user = getpass.getuser()
        self.password = 'dummyTestPassword'
        self.server = SSHServer()
        self.server.protocol = ServerProtocol

        self.port = reactor.listenTCP(0, self.server, interface=self.hostname)
        self.portnum = self.port.getHost().port

        options = {'hostname': self.hostname,
                   'port': self.portnum+1,
                   'user': self.user,
                   'password': self.password,
                   'buffersize': 32768}

        self.client = SSHClient(options)
        self.client.protocol = ClientProtocol
        self.client.connect()

    def tearDown(self):
        # Shut down the server and client
        port, self.port = self.port, None
        client, self.client = self.client, None
        server, self.server = self.server, None

        # A Deferred for the server listening port
        d = port.stopListening()

        # Tell the client to disconnect and not retry.
        client.disconnect()

        # Wait for the deferred that tell us we disconnected.
        return defer.gatherResults([d])

    def test_run_command_connect_failure(self):
        'test what happens if the server isnt running'
        d = self.client.run('echo hi')
        return self.assertFailure(d, ConnectError)

    def test_ls_connect_failure(self):
        'test what happens if the server isnt running'

        sandbox = tempfile.mkdtemp()
        d = self.client.ls(sandbox)

        def sandbox_cleanup(data):
            shutil.rmtree(sandbox)
            return data
        d.addBoth(sandbox_cleanup)
        return self.assertFailure(d, ConnectError)


class IPV4FunctionalReconnectionTestCase(TestCase):
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

    def test_run_command(self):

        def server_stop_listening(data):
            sld = self.port.stopListening()
            return sld

        def server_drop_connections(data):
            port, self.port = self.port, None
            server, self.server = self.server, None
            server.protocol.transport.loseConnection()
            return server.onConnectionLost

        def run_command(sld):
            results = self.client.run('echo hi')
            return results

        def test_failure(data):
            return self.assertFailure(data, ConnectionLost)

        def test_success(data):
            self.assertEqual(data.exitCode, 0)
            self.assertEqual(data.output,  'hi\n')
            return data

        def start_server(data):
            self.server = SSHServer()
            self.server.protocol = ServerProtocol
            self.port = reactor.listenTCP(self.portnum,
                                          self.server,
                                          interface=self.hostname)
            return self.port

        d = self.client.run('echo hi')
        d.addBoth(test_success)
        d.addCallback(server_stop_listening)
        d.addCallback(server_drop_connections)
        d.addCallback(run_command)
        d.addBoth(test_failure)
        d.addBoth(start_server)
        d.addCallback(run_command)
        d.addBoth(test_success)
        return d


class IPV4FunctionalNoReconnectionTestCase(TestCase):
    def setUp(self):
        self.timeout = 10
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
        self.client.maxRetries = 0
        #self.client.maxDelay = 0
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

        # Wait for the server to stop.
        return defer.gatherResults([d])

    def test_run_command(self):

        def server_stop_listening(data):
            sld = self.port.stopListening()
            return sld

        def server_drop_connections(data):
            port, self.port = self.port, None
            server, self.server = self.server, None
            server.protocol.transport.loseConnection()
            log.debug('Dropping server connection')
            return self.client.onConnectionLost

        def run_command(data):

            log.debug('running command hi2')
            results = self.client.run('echo hi2')
            return results

        def test_failure_done(deferred):
            log.debug('Failure %s ' % deferred)
            return self.assertEqual(deferred.type, ConnectionDone)

        def test_success(data):
            log.debug('Success %s' % (data,))
            self.assertEqual(data.exitCode, 0)
            self.assertEqual(data.output,  'hi\n')

        def bring_up_server(data):
            self.server = SSHServer()
            self.server.protocol = ServerProtocol
            self.port = reactor.listenTCP(self.portnum,
                                          self.server,
                                          interface=self.hostname)
            log.debug('server started')
            return data.factory.dConnected


        d = self.client.run('echo hi')
        d.addBoth(test_success)
        d.addCallback(server_stop_listening)
        d.addCallback(server_drop_connections)
        d.addCallback(bring_up_server)
        d.addCallback(run_command)
        d.addErrback(test_failure_done)

        return d

    def test_lsdir(self):
        test_file = 'test_ls_dir'
        sandbox = tempfile.mkdtemp()
        testfile = '/'.join([sandbox, test_file])
        touch(testfile)
        d = self.client.ls(sandbox)

        def cleanup_sandbox(data):
            log.debug('Cleaning up sandbox')
            shutil.rmtree(sandbox)

        def test_success(data):
            return self.assertEqual(data[0][0], test_file)

        def server_stop_listening(data):
            sld = self.port.stopListening()
            return sld

        def server_drop_connections(data):
            port, self.port = self.port, None
            server, self.server = self.server, None
            server.protocol.transport.loseConnection()
            log.debug('Dropping server connection')
            return self.client.onConnectionLost

        def bring_up_server(data):
            self.server = SSHServer()
            self.server.protocol = ServerProtocol
            self.port = reactor.listenTCP(self.portnum,
                                          self.server,
                                          interface=self.hostname)
            log.debug('server started')
            return data.factory.dConnected

        def run_lsdir(data):

            log.debug('running command ls again')
            results = self.client.ls(sandbox)
            return results

        def test_failure_done(deferred):
            log.debug('Failure %s ' % deferred)
            return self.assertEqual(deferred.type, ConnectionDone)

        d.addCallback(test_success)
        d.addCallback(server_stop_listening)
        d.addCallback(server_drop_connections)
        d.addCallback(bring_up_server)
        d.addCallback(run_lsdir)
        d.addErrback(test_failure_done)
        d.addBoth(cleanup_sandbox)

        return d



