##############################################################################
#
# Copyright (C) Zenoss, Inc. 2020, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

"""Twisted manhole support.

Allows SSH connections into the running process for troubleshooting purposes.

"""

from twisted import cred
from twisted.conch import manhole, manhole_ssh
from twisted.conch.insults import insults
from twisted.conch.ssh.keys import Key
from twisted.internet import reactor

import logging
import socket

log = logging.getLogger('zen.manhole')

MANHOLE_PRIVATE_KEY = """
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA4wso+ziJNL4m/C7ycjpDGVEIcutNdenoCRoUelOjyCXnoBIA
fX61iUy0bNSQElewyQWhKvR/FuvxdzgDeukeNdjZC4ECzcm4SoP3my42Qx0Ye8+n
xhpWMKW5rPGudTNGAJSrayals/Q8DQxWHZnTfH0YaImLnl5OC4CIcKeGh5vpgDyR
72P4m+dRmocXnH/snyNlGmsOwTBCMiKV8pksxdjwmbxLhFmTCrrx/4IZpMHBB36q
MqGvlVJ5+kkJg+MIOEq4q+UNJnQB4nW+DMTNfuwywV9YWb/wFTy3zCTRB9+NUjZ5
kMhcbeSKCXXCUmdH0zvaOwEVirmcA92+17WvnQIDAQABAoIBACYEkmIuv1rjlGeZ
/OL/uoictwt3N0tNVZtgkJlDNCOppTV6jjZ1ZzSMcZHfrhhEMsgWdzxYIIfYDmDm
Mj78liByJTX17mBDLObdXjLP9CoczyK8TN2xP0l6FrNM7OeXJFuoiWOx3wFZHk0Z
Cbp/LZik4ddvYL+uDueCKFak1rQSKLPaBr3o3znYNyFmMY0w/2WThFIxS0uyt6bw
KrAXpj3F3S7O8WhSr71a4qsUWdT/kHZFo6jMK+0kJvuk+fbO4ByfOoaE3DJgoQP/
D1cRF7GJfx3HUSU2FfdwUMLEIum0svNFHG3qEgEApbsmDjb5sEH4V4Qkn0WdZCaQ
JQfhGokCgYEA8YhE00M30FUD63miZkEqw8N3i6P7iqgPIb2fA+WcnTcDooDnBU4D
6MKvuhMvxXr6OVaWjc3b7oUzwpvhdS2RwRZ+/ZpctfmEoeHGztjCUP5tkfvOmX/B
z4kdSjWs6/rNTOy0eeswml10fpHKct0kup9IJbVSCMCyV/k164l11k8CgYEA8KS3
iF3kp32JAQjVsbKc2xHROR0ZTuMx8CC5d3NvR4jzv7wUHU/ySXhFcbr7kxH/w0Yz
4aTVsYrqgXCCCtkG+wBn3FcEbZaLW/nGyntt9qHHcT8X7qlNUjM8rTNxpn1Jkeeh
FA7iFSIO7+YPxmf3IIy5Td5HoLqd1E1dytBSjFMCgYB+IGnIZI6N1QdR/NeITDl3
tugDXKNrWa1lMi8KiunI00SrpGJ/S6kQ8DFxmrlUh46JSKUf8cMKgDZyRpJqbVxy
lzvDVMtbH6xaGJuHwntebi5rkDHnyGY96N0JtpPROsvggq8QB3f+9BR0T8+HQeH/
LlQvlMr81RuMgw/cKpEFUwKBgDHv/KYv1eNsCaJNUwstJZ/QcrqHb1kPjK1oHRTM
v6r4oJyJSyNKE91rN/4B73L1qT28s8d/jVjqmv+BeXsGzowH6YWwCRs0wnazvq0G
MCueJuU5Up4URBdqyoymwE7scPf2OVcQP5pjFvZxp5RkvsPicBHYrsSL9XS5GV2d
HYRBAoGBALNkTGTtZG3g5BrJ1cHnaWmstBBRQ+g9ISrdmxgP2qVQGRCl+y2ikPrO
wtDFlhVzud1wOmTWuKCR2wYyUA3SOGk3vnYAqPJV1Bnw4iqsqIFQDxAnnxU2T9Gg
7Q8KbcSz2ELLqPv/xL9THmq+LUC/SFZ5MXRGOyCzJ8uBEhYjf4UU
-----END RSA PRIVATE KEY-----
""".strip()

MANHOLE_PUBLIC_KEY = """
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDjCyj7OIk0vib8LvJyOkMZUQhy60116egJGhR6U6PIJeegEgB9frWJTLRs1JASV7DJBaEq9H8W6/F3OAN66R412NkLgQLNybhKg/ebLjZDHRh7z6fGGlYwpbms8a51M0YAlKtrJqWz9DwNDFYdmdN8fRhoiYueXk4LgIhwp4aHm+mAPJHvY/ib51Gahxecf+yfI2Uaaw7BMEIyIpXymSzF2PCZvEuEWZMKuvH/ghmkwcEHfqoyoa+VUnn6SQmD4wg4Srir5Q0mdAHidb4MxM1+7DLBX1hZv/AVPLfMJNEH341SNnmQyFxt5IoJdcJSZ0fTO9o7ARWKuZwD3b7Xta+d
""".strip()


def get_manhole_port(base_port_number):
    """
    Returns an unused port number by starting with base_port_number
    and incrementing until an unbound port is found.
    """

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    port_number = base_port_number
    while True:
        try:
            s.bind(('', port_number))
        except socket.error:
            port_number += 1
            continue

        return port_number


def setup(port, username, password, namespace=None):
    port = get_manhole_port(port)
    namespace = namespace or {}

    checker = cred.checkers.InMemoryUsernamePasswordDatabaseDontUse()
    checker.addUser(username, password)

    realm = manhole_ssh.TerminalRealm()
    realm.chainedProtocolFactory = lambda: insults.ServerProtocol(
        manhole.ColoredManhole, namespace)

    portal = cred.portal.Portal(realm)
    portal.registerChecker(checker)

    factory = manhole_ssh.ConchFactory(portal)
    factory.privateKeys["ssh-rsa"] = Key.fromString(MANHOLE_PRIVATE_KEY)
    factory.publicKeys["ssh-rsa"] = Key.fromString(MANHOLE_PUBLIC_KEY)

    log.debug("Starting manhole on port %d", port)
    reactor.listenTCP(port, factory)
