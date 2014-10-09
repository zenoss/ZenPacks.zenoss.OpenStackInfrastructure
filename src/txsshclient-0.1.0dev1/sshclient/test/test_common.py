from twisted.internet import defer
from zope.interface import implements
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.checkers import ICredentialsChecker
from twisted.conch.ssh.factory import SSHFactory
from twisted.cred.portal import Portal
#from twisted.conch.unix import UnixSSHRealm

from twisted.conch.ssh.keys import Key
from twisted.cred import checkers
from twisted.cred import credentials
from twisted.conch.ssh import keys
import base64
from twisted.python import failure
from twisted.conch import error

#from twisted.internet.error import ConnectError
from twisted.conch.avatar import ConchUser
from twisted.conch.unix import UnixConchUser
from twisted.conch.ssh import transport
from twisted.conch.ssh import session, forwarding, filetransfer

from sshclient import SSHTransport

from zope import interface
from twisted.cred import portal
import grp
import logging
log = logging.getLogger('txsshclient.test_common')

privkey = '''-----BEGIN RSA PRIVATE KEY-----
MIICXQIBAAKBgQDwzJDCRGHSt6EUw2kTyvGUm0GYFNgcFjTLrXbQIlsoHak9ShUt
XxP2cbHy2T9FBG1CBIOpTprnP9aZP0E6+JEVIT7kkwG1tFr9CarFzBVJnXEv8itX
8IIbN+vgDxGfdW/8JFP3GVjahLhSeG46wvP0LbigZ/0Sl05vxYFrWWc5RwIDAQAB
AoGBAM1BIfdmAJh0DCs9sji72ZaZjJ0Mz3WJfDFNSCR71IXqWpMyrcCB9esw2MUv
Z132Owd1/6B2r1WEtfDk2T5iGI9p6rFKsIETIiA/nhudcd2aQqxrmqk+mBWemw00
86LdD/vRf3FGd/zfR/j0nmrQam/uaxtL0WafkszdDyXRGv1ZAkEA/bg3Tcq0LNng
D0OHHRgkW44n4FrtZAgvG6Kx4JrEOBAujV0uJwNuM46FQ5j98r7yMmYJTuqqaD7u
1QYiNPoDBQJBAPL2nt/ibN7Bw2lf93B2C2We+ehv5bhB3dGTm5/EJLp0GHaXToM8
TK1hZaeDBeQhmBY1c1XaU8JV4u0QGSy1VNsCQHFP1XsrnV4ui++lM/Gdd5dgHJUJ
Zt32/br05UYvOJTlPTUrOVJ5KL1j2EaBTGEeQCKcCWoySZq3CIkg7SQFyFUCQQDM
SB3XAmsldGdYLy8+KJJ2lA9tpr/Qh9j4wJJF58Y12y1CcP+7ijSyRsUQ7jJC2Rgl
/DUIR3TLXilZx4JTO/enAkBIBRReP2yGSJercfTcrL6zSQ0TLAV0mQf1UGLxSGCb
vjFsehaZG5++PJWrK5d+/wzjTBfOXtS78BAHQQyOKMDo
-----END RSA PRIVATE KEY-----'''

pubkey = '''ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQDwzJDCRGHSt6EUw2kTyvGUm0GYFNgcFjTLrXbQIlsoHak9ShUtXxP2cbHy2T9FBG1CBIOpTprnP9aZP0E6+JEVIT7kkwG1tFr9CarFzBVJnXEv8itX8IIbN+vgDxGfdW/8JFP3GVjahLhSeG46wvP0LbigZ/0Sl05vxYFrWWc5Rw=='''

class DummyChecker:
    '''Dummy Checker that assumes all keys pass'''

    credentialInterfaces = IUsernamePassword,
    implements(ICredentialsChecker)

    def requestAvatarId(self, credentials):
        return defer.succeed(credentials.username)

    def checkKey(self, credentials):
        return True


class PublicKeyCredentialsChecker(object):
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.ISSHPrivateKey,)

    def __init__(self, authorizedKeys):
        self.authorizedKeys = authorizedKeys

    def requestAvatarId(self, credentials):
        userKeyString = self.authorizedKeys.get(credentials.username)
        if not userKeyString:
            return failure.Failure(error.ConchError("No such user"))

        # Remove the 'ssh-rsa' type before decoding.
        if credentials.blob != base64.decodestring(
                userKeyString.split(" ")[1]):
            raise failure.failure(
                error.ConchError("I don't recognize that key"))

        if not credentials.signature:
            return failure.Failure(error.ValidPublicKey())

        userKey = keys.Key.fromString(data=userKeyString)
        if userKey.verify(credentials.signature, credentials.sigData):
            return credentials.username
        else:
            log.debug("signature check failed")
            return failure.Failure(
                error.ConchError("Incorrect signature"))


class NoRootUnixConchUser(UnixConchUser):
    '''We are not forking to run the command as the user who authenticated.
       This will allow us to run this unit test as the user running the test.
       This is not secure and should not be done in a production ssh server'''

    def __init__(self, username):
        ConchUser.__init__(self)
        self.username = username
        #self.pwdData = pwd.getpwnam(self.username)

        self.pwdData = [0, 0, 0, 0, 0, 0, 0]
        self.pwdData[3] = 20
        self.pwdData[5] = '/tmp'
        self.pwdData[6] = '/bin/bash'
        l = [self.pwdData[3]]
        for groupname, password, gid, userlist in grp.getgrall():
            if username in userlist:
                l.append(gid)
        self.otherGroups = l
        self.listeners = {}  # dict mapping (interface, port) -> listener
        self.channelLookup.update(
            {"session": session.SSHSession,
             "direct-tcpip": forwarding.openConnectForwardingClient})

        self.subsystemLookup.update(
            {"sftp": filetransfer.FileTransferServer})

    def getUserGroupId(self):
        return (None, None)

    def _runAsUser(self, f, *args, **kw):
        try:
            f = iter(f)
        except TypeError:
            f = [(f, args, kw)]
        try:
            for i in f:
                func = i[0]
                args = len(i) > 1 and i[1] or ()
                kw = len(i) > 2 and i[2] or {}
                r = func(*args, **kw)
        finally:
            pass
        return r


class SlowNoRootUnixConchUser(NoRootUnixConchUser):
    ''' Same as NoRootUnixConchUser but returns group Id's slowly
        This is enough to make our ftp client timeout. '''

    def getUserGroupId(self):
        import time
        log.debug('getUserGroupId: 2 second delay')
        time.sleep(2)
        return (None, None)

    def _runAsUser(self, f, *args, **kw):
        import time
        log.debug('_runAsUser: .25 second delay %s' % f)
        time.sleep(.25)
        try:
            f = iter(f)
        except TypeError:
            f = [(f, args, kw)]
        try:
            for i in f:
                func = i[0]
                args = len(i) > 1 and i[1] or ()
                kw = len(i) > 2 and i[2] or {}
                r = func(*args, **kw)
        finally:
            pass
        return r


class NoRootUnixSSHRealm:
    '''Create a SSH Realm that will not need to fork as root.'''
    interface.implements(portal.IRealm)

    def requestAvatar(self, username, mind, *interfaces):
        user = NoRootUnixConchUser(username)
        return interfaces[0], user, user.logout


class SlowNoRootUnixSSHRealm:
    '''Create a SSH Realm that will not need to fork as root and be slow'''
    interface.implements(portal.IRealm)

    def requestAvatar(self, username, mind, *interfaces):
        user = SlowNoRootUnixConchUser(username)
        return interfaces[0], user, user.logout


class SSHServer(SSHFactory):
    'Simulate an OpenSSH server.'
    portal = Portal(NoRootUnixSSHRealm())
    portal.registerChecker(DummyChecker())

    def __init__(self):
        #pubkey = '.'.join((privkey, 'pub'))

        self.privateKeys = {'ssh-rsa': Key.fromString(data=privkey)}
        self.publicKeys = {'ssh-rsa': Key.fromString(data=pubkey)}

    def buildProtocol(self, addr):
        self.protocol = SSHFactory.buildProtocol(self, addr)
        return self.protocol


class SlowSSHServer(SSHServer):
    'Simulate an OpenSSH server.'
    portal = Portal(SlowNoRootUnixSSHRealm())
    portal.registerChecker(DummyChecker())


class ServerProtocol(transport.SSHServerTransport):
    log = logging.getLogger('txsshclient.test_common - ServerProtocol')

    def currentlyConnected(self):
        return self.factory.onConnectionLost

    def connectionMade(self):
        log.info("Server Connection Made")
        transport.SSHServerTransport.connectionMade(self)
        self.factory.onConnectionLost = defer.Deferred()

    def connectionLost(self, reason):
        log.info("Server Connection Lost")
        self.factory.onConnectionLost.callback(self)
        transport.SSHServerTransport.connectionLost(self, reason)


class ClientProtocol(SSHTransport):
    log = logging.getLogger('txsshclient.test_common - ServerProtocol')

    def connectionMade(self):
        log.info("Client Connection Made, Calling Transport connectionMade")
        SSHTransport.connectionMade(self)
        self.factory.onConnectionLost = defer.Deferred()

    def connectionLost(self, reason):
        log.info("Client Connection Lost")
        self.factory.onConnectionLost.callback(self)
        SSHTransport.connectionLost(self, reason)


