from twisted.cred.portal import Portal
from twisted.cred import checkers
from test_common import ServerProtocol, ClientProtocol
from sshclient import SSHClient
from twisted.trial.unittest import TestCase
from twisted.internet import reactor, defer
import logging
log = logging.getLogger('txsshclient.test_exec')

from twisted.cred.error import UnauthorizedLogin

import shutil
import tempfile
import logging
from test_common import pubkey, privkey, NoRootUnixSSHRealm
from test_common import PublicKeyCredentialsChecker
from twisted.conch.ssh.factory import SSHFactory
from twisted.conch.ssh.keys import Key

#logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.INFO)
#from twisted.python import log as twistedlog
#observer = twistedlog.PythonLoggingObserver()
#observer.start()

log = logging.getLogger('txsshclient.test_auth')
testUsers = {}
testUsers['testUser'] = {}
testUsers['testUser2'] = {}

testUsers['testUser']['pub'] = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQC3A/hrYFlJ1kL4IDcpuFDzy+1FE3c/lIY0sHO/be+znXWlyJj3Y/+m0FOPnzcsvakYYDLKXtHtmxolGS738s6ldXC3hGzicgFw48oq0VVvHRqgj9hYmzQ9jLqRSC+4NVH5pcfgSRPeQk7dv9OEGNM+M383FLqxMbZSYv+TDvl4bQ=="
testUsers['testUser']['priv'] = '''-----BEGIN RSA PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: DES-EDE3-CBC,F14D2D259FC7A299

cYAIV67gLCvu7G6ZVF9j0Jtv8xonWqvjdKOMmGlHrvS7ceWNo0PyaamCaEzzHJK9
15CQy16rcZKA56dYiwnVGiYIAWKkUpCiKquqeq4jiYemDyfAV8gHtUlTHtq7FbEt
Fbhn3b+eBC5I5+KPfrs0rrqOv0ljHjfNBjyKaIJ0gMfb7f7+u3hjC+w8S6TfGUC3
l+hwgIUtgDZhWUqfZ13K26vkZP/XCFQahTdWp2GW8PcKaGfdjELPFz9HVUobghqm
KzDfleBFVl6ucq4Nifl1yAhAo0ei476LHHV0JZMbq/Ci3RHNhs/OJEo8ExVUXzDI
8itWUOVP/HK2MAzqcZg2UvFRCjejpNU+8PpObbMml0sV/iosK0JQKcJuccsV5IN/
NKSD4Tm0j/2uywGJ7JtlXleDXRjO6ocIi+ShI0ETO9WByeVLM/GJNat1im/TZems
BQ/GGFgL0OzxKOtGO04v22O1ghMabEDlhXZ8NmHgoXOpYOjrDbGSCBiUwtWeB9j7
7TdHAqzlfu+saCr0AzQXKeosG9pCJfR2rAyx3R1UEcCa+WT5AFXy7rfzhlXdclA/
ebiZcMHnkHMoUmUXpPMO3y9vRq3FKYv9J2mlM72w/3ohPRmLSP7ClOobKCPjfN/M
huM4kBaQ87aYsnn0i16fQ4vCO6E+Vr4MJmFzP7qa9QbEDVta0e+VfkCaEnCrDaro
3lGi2kXpmPADnQrHIXoMk0KS9MzApeo/hpfrEGpMQSvyYHvQQXRqd1ozIhYvYuHR
yo6y9SoUwqiEXwwMxw3md4UWcdYv/U6SZhLlIbbF+TlicgyYLKjW+Q==
-----END RSA PRIVATE KEY-----'''

testUsers['testUser2']['pub'] = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQC3A/hrYFlJ1kL4IDcpuFDzy+1FE3c/lIY0sHO/be+znXWlyJj3Y/+m0FOPnzcsvakYYDLKXtHtmxolGS738s6ldXC3hGzicgFw48oq0VVvHRqgj9hYmzQ9jLqRSC+4NVH5pcfgSRPeQk7dv9OEGNM+M383FLqxMbZSYv+TDvl4bQ=="

testUsers['testUser2']['priv'] = '''-----BEGIN RSA PRIVATE KEY-----
MIICXAIBAAKBgQC3A/hrYFlJ1kL4IDcpuFDzy+1FE3c/lIY0sHO/be+znXWlyJj3
Y/+m0FOPnzcsvakYYDLKXtHtmxolGS738s6ldXC3hGzicgFw48oq0VVvHRqgj9hY
mzQ9jLqRSC+4NVH5pcfgSRPeQk7dv9OEGNM+M383FLqxMbZSYv+TDvl4bQIDAQAB
AoGAAZPqL1rMSkOrniIA974cDI4EhKTvUUABjDC9Prg+6ciAvCYnk3JsQM7o+YMA
4cTc0VX6+h2pJ6g/qHQ4IHEacPT+1Y3/sbsqa/eE2WlArHf4OBubiFFWfTvGGQ6t
vJaSohdx8Siquv4RgRugfJTZvy+z8wLPzUByos/rc9BZAGECQQDiZ6YJm4L1YFFy
P1vize5tkM7t/b7tclQ1jd473oJHDBZrez4iTj/okXUrFIW8NtJxzSopUR03NSjN
hnfd914ZAkEAzvBaDQ413YXgfWfzliMKlsJrw4vLlAS2BXeJduNwsXUpbB/0ytfl
k/bfO6tqf83KtAqIuTQVc4hLUHt+DqgPdQJBAKsMVaQCioEpwL7I4XnLzWuXsM6b
G2k3LCm9wf2HUPOuTS3s0XeHmL7zTgs7GQKmhH2X3FeUwbbZAbes9NiMr9kCQFMA
GD5QSs6VGdtyzEKVv3OEe5CtC3RNB2zd6ybiRpsGsRyLHLYXLh/Qzuyx7j9gnULl
Tr1p5Ii4S+z1+zOJuNkCQGEsWHLZ9aKcNxoE/QzYdouTvMFGob3ArJr2SYjqACbY
2Ec0cStsNSG2HteJMjVqO+b/xBSE2RgA0c2HWDIDYtY=
-----END RSA PRIVATE KEY-----'''

class SSHServer(SSHFactory):
    'Simulate an OpenSSH server.'
    portal = Portal(NoRootUnixSSHRealm())
    passwdDB = checkers.InMemoryUsernamePasswordDatabaseDontUse()
    #passwdDB.addUser('testUser', 'testPassword')
    portal.registerChecker(passwdDB)

    authorizedKeys = {}
    for user in testUsers:
        authorizedKeys[user] = testUsers[user]['pub']

    portal.registerChecker(PublicKeyCredentialsChecker(authorizedKeys))

    def __init__(self, user, password):
        log.debug('adding user %s to ssh server' % user)
        self.passwdDB.addUser(user, password)
        self.privateKeys = {'ssh-rsa': Key.fromString(data=privkey)}
        self.publicKeys = {'ssh-rsa': Key.fromString(data=pubkey)}

    def buildProtocol(self, addr):
        self.protocol = SSHFactory.buildProtocol(self, addr)
        return self.protocol


class IPV4FunctionalAuthTestCase(TestCase):
    def setUp(self):
        self.hostname = '127.0.0.1'
        self.sshServeruser = 'testUser'
        self.sshServerPassword = 'dummyTestPassword'
        self.server = SSHServer(self.sshServeruser, self.sshServerPassword)
        self.server.protocol = ServerProtocol

        self.port = reactor.listenTCP(0, self.server, interface=self.hostname)
        self.portnum = self.port.getHost().port

        # create ssh auth sandbox for keys.
        self.sandbox = tempfile.mkdtemp()

    def tearDown(self):

        # Shut down the server and client
        port, self.port = self.port, None
        #client, self.client = self.client, None
        server, self.server = self.server, None

        # A Deferred for the server listening port
        d = port.stopListening()

        # Remove the sandbox
        shutil.rmtree(self.sandbox)

        # Wait for the deferred that tell us we disconnected.
        return defer.gatherResults([d])

    def test_password_auth_success(self):
        options = {'hostname': self.hostname,
                   'port': self.portnum,
                   'user': self.sshServeruser,
                   'password': self.sshServerPassword,
                   'buffersize': 32768}

        self.client = SSHClient(options)
        self.client.protocol = ClientProtocol
        self.client.connect()

        d = self.client.run('echo hi')

        def client_disconnect(data):
            log.debug('Disconnecting client')
            self.client.disconnect()
            return data

        def got_hi(data):
            log.debug('Got Data %s' % (data,))
            self.assertEqual(data.exitCode, 0)
            self.assertEqual(data.output,  'hi\n')
            return data

        d.addBoth(client_disconnect)
        d.addCallback(got_hi)

        return d

    def test_password_auth_failure(self):
        options = {'hostname': self.hostname,
                   'port': self.portnum,
                   'user': self.sshServeruser,
                   'password': 'bad password',
                   'buffersize': 32768}

        self.client = SSHClient(options)
        self.client.protocol = ClientProtocol
        self.client.connect()

        d = self.client.run('echo hi')

        def client_disconnect(data):
            log.debug('Disconnecting client')
            self.client.disconnect()
            return data

        d.addBoth(client_disconnect)

        return self.assertFailure(d, UnauthorizedLogin)

    def test_password_identity_success(self):
        options = {'hostname': self.hostname,
                   'port': self.portnum,
                   'user': self.sshServeruser,
                   'password': 'test1',  # sshkey phrase
                   'identities': [self.sandbox+'/id_rsa'],
                   'buffersize': 32768}

        id_rsa_pub = testUsers['testUser']['pub']
        id_rsa_priv = testUsers['testUser']['priv']

        open(self.sandbox+'/id_rsa.pub', 'w').write(id_rsa_pub)
        open(self.sandbox+'/id_rsa', 'w').write(id_rsa_priv)
        self.client = SSHClient(options)
        self.client.protocol = ClientProtocol
        self.client.connect()

        d = self.client.run('echo hi')

        def client_disconnect(data):
            log.debug('Disconnecting client')
            self.client.disconnect()
            return data

        def got_hi(data):
            log.debug('Got Data %s' % (data,))
            self.assertEqual(data.exitCode, 0)
            self.assertEqual(data.output,  'hi\n')
            return data

        d.addBoth(client_disconnect)
        d.addCallback(got_hi)

        return d

    def test_password_identity_failure(self):
        options = {'hostname': self.hostname,
                   'port': self.portnum,
                   'user': self.sshServeruser,
                   'password': 'test2',  # sshkey phrase
                   'identities': [self.sandbox + '/id_rsa'],
                   'buffersize': 32768}

        id_rsa_pub = testUsers['testUser']['pub']
        id_rsa_priv = testUsers['testUser']['priv']

        open(self.sandbox+'/id_rsa.pub', 'w').write(id_rsa_pub)
        open(self.sandbox+'/id_rsa', 'w').write(id_rsa_priv)

        self.client = SSHClient(options)
        self.client.protocol = ClientProtocol
        self.client.connect()

        d = self.client.run('echo hi')

        def client_disconnect(data):
            log.debug('Disconnecting client')
            self.client.disconnect()
            return data

        d.addBoth(client_disconnect)

        return self.assertFailure(d, UnauthorizedLogin)

    def test_password_identity_no_passphrase_success(self):
        options = {'hostname': self.hostname,
                   'port': self.portnum,
                   'user': 'testUser2',
                   'identities': [self.sandbox + '/id_rsa2'],
                   'buffersize': 32768}

        id_rsa_pub = testUsers['testUser2']['pub']
        id_rsa_priv = testUsers['testUser2']['priv']

        open(self.sandbox+'/id_rsa2.pub', 'w').write(id_rsa_pub)
        open(self.sandbox+'/id_rsa2', 'w').write(id_rsa_priv)

        self.client = SSHClient(options)
        self.client.protocol = ClientProtocol
        self.client.connect()

        d = self.client.run('echo hi')

        def client_disconnect(data):
            log.debug('Disconnecting client')
            self.client.disconnect()
            return data

        def got_hi(data):
            log.debug('Got Data %s' % (data,))
            self.assertEqual(data.exitCode, 0)
            self.assertEqual(data.output,  'hi\n')
            return data

        d.addBoth(client_disconnect)
        d.addCallback(got_hi)

        return d



