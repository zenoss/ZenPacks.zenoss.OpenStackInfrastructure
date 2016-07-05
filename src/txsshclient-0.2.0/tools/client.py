#!/usr/local/bin/python
from twisted.internet import reactor
from twisted.python import failure

from sshclient import SSHClient

import logging
logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.INFO)
from twisted.python import log as twistedlog
observer = twistedlog.PythonLoggingObserver()
observer.start()
log = logging.getLogger('txsshclient.client')

options = {'hostname': '127.0.0.1',
           'port': 2222,
           'user': 'eedgar',
           'password': 'foo',
           'buffersize': 32768}

client = SSHClient(options)
client.connect()


def retry():
    log.debug('retrying')
    d = client.run('sleep 5 && ls')

    def failed_or_success(result):
        if isinstance(result, failure.Failure):
            log.info("Failed %s" % (result, ))
        else:
            log.info("Success %s" % (result, ))

    d.addBoth(failed_or_success)

    d2 = client.run('sleep 5 && ls', timeout=6)
    d2.addBoth(failed_or_success)
    reactor.callLater(6, retry)

reactor.callLater(1, retry)
reactor.callLater(20, reactor.stop)
reactor.run()
