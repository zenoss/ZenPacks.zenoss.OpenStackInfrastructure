from twisted.internet import defer
from twisted.conch.ssh import transport
from twisted.cred.error import UnauthorizedLogin

import logging
log = logging.getLogger('txsshclient.SSHTransport')


class SSHTransport(transport.SSHClientTransport):
    def __init__(self):
        log.debug('Initialized the Transport Protocol')

    def verifyHostKey(self, hostKey, fingerprint):
        'Assume all host keys are valid even if they changed'
        return defer.succeed(True)

    def connectionSecure(self):
        log.debug('Transport connectionSecure setting dTransport')

        # We are connected to the otherside.
        self.factory.dTransport.callback(self)

    def sendDisconnect(self, reason, desc):
        log.debug('sending transport disconnect [%s]' % reason)
        transport.SSHClientTransport.sendDisconnect(self, reason, desc)

        # Tell the factory we had an unauthorized login exception
        if reason == 14:
            log.debug('login failure, telling the factory about it')
            self.factory.resetConnection(UnauthorizedLogin())
