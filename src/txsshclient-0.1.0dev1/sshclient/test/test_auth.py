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

logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.INFO)
from twisted.python import log as twistedlog
observer = twistedlog.PythonLoggingObserver()
observer.start()

log = logging.getLogger('txsshclient.test_auth')


class SSHServer(SSHFactory):
    'Simulate an OpenSSH server.'
    portal = Portal(NoRootUnixSSHRealm())
    passwdDB = checkers.InMemoryUsernamePasswordDatabaseDontUse()
    #passwdDB.addUser('testUser', 'testPassword')
    portal.registerChecker(passwdDB)

    authorizedKeys = {
    "testUser": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCcBrv9frR15xW/clDeiYK4xvq79YbIVmSnpUWRVjSqi1vAdHZ6k/s9AEcvv5yAHc6F7Ypq8pAvAIeVb29+0Zp+bBf3Y3y8/UTKkwAF+OkB6F7M8D/ORn1O/AZP1P8LE2i0mgXljvtVAQGJUnETQYlHrx7P9WUrkTUYXtQl7tx1mrEZSlQtn4ou34kXtfOuBnB45nw0t8tBMEhg1QnJla5zJkVCR/MCZE3DHVnz1ruIJcIKk7X5ESsg29pPh3Y3C+wZRhAU/vSSEivvyNm6ya2rI9Z9kHqhRT//7MqP9VOZNaeVYGifEO0UXHSL+O4boMFj1kyV3TN8pCP+aVV4z0wT",
    "testUser2": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDEDGUHXPBLvmfYeQE0iF9gmyKF+GeAtMcGnT8SzbA1e6XSsGAyFLNBst88Z6QgCy515uD77tGoCJ2R6ErPiCeiUUH6kOWkgvFnOdXpXkUajUnyrE3xGZ3W5b8JfP4jN43B5ouxsAdmGECDsFGCCOqSTl/rGwAdGKjYH9fH71wBqSqcu7Ld520jcmHu6yxJ5QFFHQ4mNk5JWlH9FbiKJ4m2tLJEhPRfiLV1z641BvM2LNp0NxKWOZbaq9ui8AArIU2eHWjXT6mLUDunXwwhGy1mikLvB/ViDhs0+hmh7/WDJC07sq0BVLtC/L7OHhhuUgf9zt6XFNaYjNykImwPGwrj"
    }

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

        id_rsa_pub = 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCcBrv9frR15xW/clDeiYK4xvq79YbIVmSnpUWRVjSqi1vAdHZ6k/s9AEcvv5yAHc6F7Ypq8pAvAIeVb29+0Zp+bBf3Y3y8/UTKkwAF+OkB6F7M8D/ORn1O/AZP1P8LE2i0mgXljvtVAQGJUnETQYlHrx7P9WUrkTUYXtQl7tx1mrEZSlQtn4ou34kXtfOuBnB45nw0t8tBMEhg1QnJla5zJkVCR/MCZE3DHVnz1ruIJcIKk7X5ESsg29pPh3Y3C+wZRhAU/vSSEivvyNm6ya2rI9Z9kHqhRT//7MqP9VOZNaeVYGifEO0UXHSL+O4boMFj1kyV3TN8pCP+aVV4z0wT'

        id_rsa_priv = '''-----BEGIN RSA PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: AES-128-CBC,4DD74F7C8DB960D19C85FF45F9EAE578

g7JxCGo18P2GN7RwIlvb2s/RoJJkO0ldRoxTHZGJXfz3ZzhMUL4+gue8txMpq1Ql
iy14ci2Y4ePtucMDgZfzeoUSLvP2yn9wzH1Nyqp0ln3xIJCALp29nCBnQymhnDTU
yfl36Cqdzvhr9x/BHYjCC89OXtETDcxk60P+moCzreO5PXGZkQ0OL6t1/J4YhOYi
8GyyyzYDX6YueHlsZRgKm4BJfVSVDEwD6DeEkIHPL4rPiHQ9hkn18w9Qt7i2g0a8
xOE9x6VLmJy1XqHXuVAtGpNo3ZvSS9owHYOVMQ0EfIJn5Xct1tb4u2PjL0HNbFYQ
4UrpsviUyVdHbjD571WU2j3QUPQZKHQKDoZzopqSE8yT4zKdz1g6C2zcJ3rdB7W2
sagX8Y2LnStJ80SyuJ48+ShW1zMocL5N9QXS7YK3AvjUTgOnxJgUNiW9ygawz4a9
9CRbYz/HlIqA9st3NHcT4wG/jgr1sg7OERD8KrEQ7YlwdKYuCqP3FzxNTY73DhkJ
B6xaYAMznbIr1qpf4WS5LRM99a+C6RSqgrT3FnbLhxyFsmJOje/p04xa79NKSpzc
XO/bVPFmxP97g8Dp/rxKpDOO5ltbgPm3BLPxied5sJzD6EcQYjKCtDAMP6hP/32h
g/KKCU5G5OQohXVsPGD9CnlKCIKFX13nrr96ir4j1ioGtNKErvwK6FMyCh9K+nKn
wxXWtr3QACQeXtqNSLDfc47Ot/9/kJimIEr1nevoVVaCzc5J0YbJRSaID6ZEjYub
D5QmWpiSBZxV4S8Ycwr87+8ndLlZ79TMbnPkA/noH3mTF4njkkkFumuDdLCdqapH
FtfO2Vo8X+TzIGndajUFzpDhiSXTM8LyBOX8OXS0AWMa9Uwirb+JFGiGDLsXm5+i
yCQU0AUFUGo+XFKOEtWkOEHwdmGuvQkHl7OZh7MlDl8CJNiA6QX4HE+7Qi8K21Dd
3D8wQ4r642BBSlDL2Tn2uuTFSgXrxwXt9ev7n+G6HtKPOep0Mp+Ev5ZMF/vLExyV
ws0XoPqsiqxkjtXah0r1zgCwyxP5/3f+RR4uQdRW3iGQKgVIrVcPI/l6hYuyOmVn
Axo0bX2IjF9InToqiH6OdoEsNz1GSZ+2wWBkwGSrdl3qwxCBtSpQmvabJZaKbCGw
UB7cUmGfcUDhfX25RJxbiHutYREmIKH8HCkuju2AcMD5i8NLbnxIxd93FHIcjBSZ
aa5WqM0OyWpMnU+b0wF/kswJcV5bRTMsxbcxCxms+709b2PFu7QseVawt+4ZrQc8
U3wK58ASo2UQ03EBQtAV93vFEWacEZnOhV0Y+wlsz+IxPHknasglPlG0LgveoQ56
bRe9UkxnTq5Nc8hRE+nj6Zmp7CipuEuQoNRPWd8wXGPhl1QzC4Y4fXRVBlldUIQS
tz++P2DN1zEq8TwfyPOeMomDNofeRD/9esEWy0xXOOVwoa3tEGnTyJjujxUcxGgy
76DIb2tcriDsRqKLG+Elt/CSlBzShCmXhnOoVbx1/203nWbSNV91W8VtknyaA0+Q
AN47K9sxuWxUMwlZVP9IbWJwKInoIn72ck/x5+Y5i+NYOOp5JfeepONzXo6Ulw6B
-----END RSA PRIVATE KEY-----'''

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

        id_rsa_pub = 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCcBrv9frR15xW/clDeiYK4xvq79YbIVmSnpUWRVjSqi1vAdHZ6k/s9AEcvv5yAHc6F7Ypq8pAvAIeVb29+0Zp+bBf3Y3y8/UTKkwAF+OkB6F7M8D/ORn1O/AZP1P8LE2i0mgXljvtVAQGJUnETQYlHrx7P9WUrkTUYXtQl7tx1mrEZSlQtn4ou34kXtfOuBnB45nw0t8tBMEhg1QnJla5zJkVCR/MCZE3DHVnz1ruIJcIKk7X5ESsg29pPh3Y3C+wZRhAU/vSSEivvyNm6ya2rI9Z9kHqhRT//7MqP9VOZNaeVYGifEO0UXHSL+O4boMFj1kyV3TN8pCP+aVV4z0wT'

        id_rsa_priv = '''-----BEGIN RSA PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: AES-128-CBC,4DD74F7C8DB960D19C85FF45F9EAE578

g7JxCGo18P2GN7RwIlvb2s/RoJJkO0ldRoxTHZGJXfz3ZzhMUL4+gue8txMpq1Ql
iy14ci2Y4ePtucMDgZfzeoUSLvP2yn9wzH1Nyqp0ln3xIJCALp29nCBnQymhnDTU
yfl36Cqdzvhr9x/BHYjCC89OXtETDcxk60P+moCzreO5PXGZkQ0OL6t1/J4YhOYi
8GyyyzYDX6YueHlsZRgKm4BJfVSVDEwD6DeEkIHPL4rPiHQ9hkn18w9Qt7i2g0a8
xOE9x6VLmJy1XqHXuVAtGpNo3ZvSS9owHYOVMQ0EfIJn5Xct1tb4u2PjL0HNbFYQ
4UrpsviUyVdHbjD571WU2j3QUPQZKHQKDoZzopqSE8yT4zKdz1g6C2zcJ3rdB7W2
sagX8Y2LnStJ80SyuJ48+ShW1zMocL5N9QXS7YK3AvjUTgOnxJgUNiW9ygawz4a9
9CRbYz/HlIqA9st3NHcT4wG/jgr1sg7OERD8KrEQ7YlwdKYuCqP3FzxNTY73DhkJ
B6xaYAMznbIr1qpf4WS5LRM99a+C6RSqgrT3FnbLhxyFsmJOje/p04xa79NKSpzc
XO/bVPFmxP97g8Dp/rxKpDOO5ltbgPm3BLPxied5sJzD6EcQYjKCtDAMP6hP/32h
g/KKCU5G5OQohXVsPGD9CnlKCIKFX13nrr96ir4j1ioGtNKErvwK6FMyCh9K+nKn
wxXWtr3QACQeXtqNSLDfc47Ot/9/kJimIEr1nevoVVaCzc5J0YbJRSaID6ZEjYub
D5QmWpiSBZxV4S8Ycwr87+8ndLlZ79TMbnPkA/noH3mTF4njkkkFumuDdLCdqapH
FtfO2Vo8X+TzIGndajUFzpDhiSXTM8LyBOX8OXS0AWMa9Uwirb+JFGiGDLsXm5+i
yCQU0AUFUGo+XFKOEtWkOEHwdmGuvQkHl7OZh7MlDl8CJNiA6QX4HE+7Qi8K21Dd
3D8wQ4r642BBSlDL2Tn2uuTFSgXrxwXt9ev7n+G6HtKPOep0Mp+Ev5ZMF/vLExyV
ws0XoPqsiqxkjtXah0r1zgCwyxP5/3f+RR4uQdRW3iGQKgVIrVcPI/l6hYuyOmVn
Axo0bX2IjF9InToqiH6OdoEsNz1GSZ+2wWBkwGSrdl3qwxCBtSpQmvabJZaKbCGw
UB7cUmGfcUDhfX25RJxbiHutYREmIKH8HCkuju2AcMD5i8NLbnxIxd93FHIcjBSZ
aa5WqM0OyWpMnU+b0wF/kswJcV5bRTMsxbcxCxms+709b2PFu7QseVawt+4ZrQc8
U3wK58ASo2UQ03EBQtAV93vFEWacEZnOhV0Y+wlsz+IxPHknasglPlG0LgveoQ56
bRe9UkxnTq5Nc8hRE+nj6Zmp7CipuEuQoNRPWd8wXGPhl1QzC4Y4fXRVBlldUIQS
tz++P2DN1zEq8TwfyPOeMomDNofeRD/9esEWy0xXOOVwoa3tEGnTyJjujxUcxGgy
76DIb2tcriDsRqKLG+Elt/CSlBzShCmXhnOoVbx1/203nWbSNV91W8VtknyaA0+Q
AN47K9sxuWxUMwlZVP9IbWJwKInoIn72ck/x5+Y5i+NYOOp5JfeepONzXo6Ulw6B
-----END RSA PRIVATE KEY-----'''

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

        id_rsa_pub = 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDEDGUHXPBLvmfYeQE0iF9gmyKF+GeAtMcGnT8SzbA1e6XSsGAyFLNBst88Z6QgCy515uD77tGoCJ2R6ErPiCeiUUH6kOWkgvFnOdXpXkUajUnyrE3xGZ3W5b8JfP4jN43B5ouxsAdmGECDsFGCCOqSTl/rGwAdGKjYH9fH71wBqSqcu7Ld520jcmHu6yxJ5QFFHQ4mNk5JWlH9FbiKJ4m2tLJEhPRfiLV1z641BvM2LNp0NxKWOZbaq9ui8AArIU2eHWjXT6mLUDunXwwhGy1mikLvB/ViDhs0+hmh7/WDJC07sq0BVLtC/L7OHhhuUgf9zt6XFNaYjNykImwPGwrj'

        id_rsa_priv = '''-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAxAxlB1zwS75n2HkBNIhfYJsihfhngLTHBp0/Es2wNXul0rBg
MhSzQbLfPGekIAsudebg++7RqAidkehKz4gnolFB+pDlpILxZznV6V5FGo1J8qxN
8Rmd1uW/CXz+IzeNweaLsbAHZhhAg7BRggjqkk5f6xsAHRio2B/Xx+9cAakqnLuy
3edtI3Jh7ussSeUBRR0OJjZOSVpR/RW4iieJtrSyRIT0X4i1dc+uNQbzNizadDcS
ljmW2qvbovAAKyFNnh1o10+pi1A7p18MIRstZopC7wf1Yg4bNPoZoe/1gyQtO7Kt
AVS7Qvy+zh4YblIH/c7elxTWmIzcpCJsDxsK4wIDAQABAoIBAHhV71Fkr66echmC
tMWtC3Y94yP+hHGRBTU/Ie8FyCob+n3nezRiVmF2TOZD648rrdn63JBnV9NfbnCX
+AuI1GMio3AMrpibM1gcPPwgvCP/I6vMLY9XHPZCUU+epFOzjtS9EXQAy5nUOw1a
Fb3OgUVKzD+AdEJn14PJj+aOOphdTd9T7T39sotVM3T0skBD3Vs1yzyTLJjjacNb
pZkpnBj5gbyuVvfVeZ6alNaWbso4Gul8hIw8lWlnbYIScG8a1F7OvsHJcM/U8C8d
4CVjHs3ZcRtgqdvc8UpvXCzjRdtiNvY6fDA/AzlIzCE8NXscdA4tPvnvuxBsBbvP
349fHokCgYEA4MGUdZOh8zK/xQ9DzaXF+k/Elkm600cgz7Kk6WRoao8g1XkBLx//
J0tQLtXa9ZO/NsHSpvStj6c84MigDEmjRo5v8RVzV2DzSRZJZPkpwPMrtA2UXGBw
gKvVdfGt7dUbyh1M+TqU2aoE2WpZ75vz8fhG2iR8qy2GzXztz648FeUCgYEA300w
YxX0S5Kg3YEXg0P38U7XBiFCtqtyVzVv7mU0tj+kVyVViGIFOMmhzw2KYkTQ8nCW
Qx0evKxsukZ3hSOwEFRRVzI9PTa+D3B4I4YVEqmtXMXIaF0hK20eaWGKSYQyNVwN
2j9tNh1JPjKQnSHnXd9J78uwz4DlUodVoXSJkScCgYEAvKFbEu7rveu6zQ2Jr1/Q
78rgx+1rUgThQc/B3mu5wq0LNn6PAtkM0RLBYf1z/iWZFsDHJf42aFlIm7Nlt8pZ
sU68Ho8NNamVpaKByK/hXiH4bO30tS7vXN5akdlbSz9PSmsa/hUvdhreZQaAIrw1
mb/w3wY+Z4AXIgEWqfWmUg0CgYBZPHGPx2A/KzOaEVKiJHFbP5RyYKxWb6Fb9IDs
lglAo6I7KTJLNFC95uYA5npc1v9hQ1jpLSPxZj51Gl/9FsvvWqK+49bRNaUyalG4
cIbPVHtxTaDPBBiTUCINHuuygV/HLyhiBWLRc1anwnFEOh5Jx0e2yoG4CtyZ5Hd1
9CpdlQKBgGd7WHZ2rjhhpeioj7SzyBiVUlIpa/5GbSBjORg3qzKh8uxr0QCv3AR9
H0sIs+ZEA3OyHETt9Oev9KUOmvIBZ2oq/Ts9PI7h6WlHx5xsGCATU0oPLz4zYT/Y
pwZnlY+/k842IzNH1I6J+Fak7ylb0ldj6SsL0NL4jPveOFBXsr8f
-----END RSA PRIVATE KEY-----'''

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



