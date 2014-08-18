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
MIIEpQIBAAKCAQEAoplZwXoxPBnVVYyP76UkJDsH30la5pjWNRW0O+oEPM6mePh/
ZwcUS8NHRhzvfLaYQ2Pr8RzGz2nMNhrTHSDyOvrvltHLiMl997jXdhTukfffbA+X
k4uF4HoOA0SmvsIDIJ+1MCFExvXqWtv8crQFjc/Nl1gdY9ZJIW3WeN+4gjYCRc/F
QwaY8BXQuGTj4Tjpo21s9K+VTOdzhdC+tTBmN625oUSb/MNautS2cONt0wh2sWJ7
rYhj+gSfotZc/zE8C+0jcIdr4Pj5kRuC5XtBFAUv9OeLLE5LYMzgcGA79ZrmxX1z
uvHFhiACMnlJtaSqokmfzJvcdMyWYniaHmOrvwIDAQABAoIBAQCZX0E0qQfsAwoi
KfZTPFh8/FmOmujtftj/NbvOkAzzNpH8pZm3Gwxf8pE2Z3DXGH1Dg+s4gcZeOxNv
LZpZbYxPage5Iad1HWp+0pIaReBLO545lfOKLx9XAIpbNtR6NxMwILWN8rOnYKtw
jPTxVTGv9IWe7nS6iZRtveeCGLU3zC0sOV+ESbUL3g1puj9td1KAQF1ESHZ8Gvgb
/iGTpCYmwWZlmPKpfQNU4dgohIfS/pzxn/8MOLjfG6UxHZJ0Pd7T+YATcKCDY2+W
zpZram5+7DW/4JpnIxXHHYCPftwyB8ZPRXI5r5nZMMS8w8nA6j9BDgbdvkhJYY4R
MYVe58sRAoGBAM2YAoV1drgnl9SV5+kc5gmyCI8afCjttrTrmK7za4pVK+nNpDHs
F1lX3gZ3e68QrVVUNkRMm/tEeIxKI+GVNGR6fJjrvF5WAs5FXnVzKObPUA6fMuiF
hiqeG+6CF4Az/uk8j/nqk6wghxc412awisuh+NfUcJY+NOijaEnbjBcVAoGBAMp2
y9WCIzuLEMKIHUe6WUCZnSF7yopX6Zb5vRhJ6FVM+pjk0LUxWONr3t8KnxhJDwpW
hKC/AQLUDqu9M1/NJJfRvh0WiyVyGR3gnQ14rdTzG0yAjqJ4aSzNYOFx2iHABO07
F0M0Gsxs6plWcUid745Ee4S+B8BDhZ37XHN522yDAoGAaTOSfrYXlK313DsE210F
PQrTpF5aEBtrdXJkw4kdi0B/4vhuP3lejUIQA2Eacf9nopUf250T5+Qmhyrc526Q
y6V9okZmMiNy9he6+QB/enO0tHaz9xV0DNSw2D/LRLfWhYSO68Qj4l0Wo0RbvFkz
/HUaP16eadLVAgGzuK9WJO0CgYEAufhgxt9gyYK1hFpOuuH6tZHkeSsiIe0ajSkc
fkD0/dVVojcbVjPbuBoPf8Rb2ozRGefar2SC4zwxtaJ2nBrs798ix8k7SswBMiZt
XEBrO92KR70WRzpfMV39DVfsy297lwTeG0azDu9EllCGgfNAZeeVpZp/uCTNiQ2o
IBHgcU0CgYEAolQ0dJ6lIVXl51ojRLpGmikvXEZQCabegh3HJbeS4KMb1hExF5M0
J8tWGLWBnRmXsyDkb0CZtf9NP/5/Td88sXbNxWxk9Ru8hqe7lvrpuFNMSI3NK5ow
IpJHlV9qhu8gSGOIS9moOmTQbtPtjDdZxA2bHlht7H9QiFwK+DmpJIo=
-----END RSA PRIVATE KEY-----'''

pubkey = '''ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCimVnBejE8GdVVjI/vpSQkOwffSVrmmNY1FbQ76gQ8zqZ4+H9nBxRLw0dGHO98tphDY+vxHMbPacw2GtMdIPI6+u+W0cuIyX33uNd2FO6R999sD5eTi4Xgeg4DRKa+wgMgn7UwIUTG9epa2/xytAWNz82XWB1j1kkhbdZ437iCNgJFz8VDBpjwFdC4ZOPhOOmjbWz0r5VM53OF0L61MGY3rbmhRJv8w1q61LZw423TCHaxYnutiGP6BJ+i1lz/MTwL7SNwh2vg+PmRG4Lle0EUBS/054ssTktgzOBwYDv1mubFfXO68cWGIAIyeUm1pKqiSZ/Mm9x0zJZieJoeY6u/ eedgar@eedgar-mb.local'''


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


