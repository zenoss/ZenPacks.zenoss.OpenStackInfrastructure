from twisted.conch.ssh import connection
import logging
log = logging.getLogger('txsshclient.connection')


class Connection(connection.SSHConnection):
    def __init__(self, factory, deferred):
        self.factory = factory
        self.deferred = deferred
        connection.SSHConnection.__init__(self)

    def serviceStarted(self):
        log.debug('Connection serviceStarted')
        self.deferred.callback(self)
