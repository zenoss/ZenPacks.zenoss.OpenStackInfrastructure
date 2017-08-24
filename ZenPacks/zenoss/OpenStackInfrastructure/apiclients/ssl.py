###########################################################################
#
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2017, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
#
###########################################################################


import attr
from socket import inet_ntop, AF_INET, AF_INET6
import warnings

from service_identity import VerificationError, CertificateError, SubjectAltNameWarning
from service_identity.pyopenssl import decode, GeneralNames, extract_ids as si_extract_ids
from service_identity._common import DNS_ID, _is_ip_address, text_type, verify_service_identity

from twisted.python.failure import Failure
from twisted.web.iweb import IPolicyForHTTPS
from twisted.internet.ssl import CertificateOptions
from twisted.internet._sslverify import (
    ClientTLSOptions, _maybeSetHostNameIndication,
    SSL_CB_HANDSHAKE_START, SSL_CB_HANDSHAKE_DONE)
from twisted.web.client import BrowserLikePolicyForHTTPS

from zope.interface.declarations import implementer


# Provides a new contextFactory, PermissiveBrowserLikePolicyForHTTPS, which
# fixes some problems in twisted.web.client.Agent's SSL support.
#
# In particular, this adds in support for connecting to URLs that contain
# IP addresses rather than hostnames (validating against a subjectAltName
# with a type of iPAddress)
#
# This necessary because of two problems upstream:
#   - In twisted (15.5.0), twisted.internet._sslverify._identityVerifyingInfoCallback
#      calls service_identity.verify_hostname on the host being connected to.  This
#      throws an error if the host is an IP address.
#   - In service_identity (16.0.0), service_identity.pyopenssl.extract_ids
#      (called by the forementioned verify_hostname) does not support
#      subjectAltName entries of type iPAddress, which are necessary to securely
#      connect to a URL by IP address.  This issue is identified in
#      https://github.com/pyca/service_identity/issues/12 but not yet fixed.
#
#  This file provides the following
#   - support for iPAdddress(IPADDRESS_ID, IPADDRESSPattern, IPAddressMismatch)
#   - Modified version of verifyHostname which supports wraps the default one,
#     adding IP support
#   - A twisted.web.client.Agent context factory (PermissiveBrowserLikePolicyForHTTPS)
#   - Glue between that factory and the modified version of verifyHostname
#     (PermissiveClientTLSOptions)


@attr.s
class IPADDRESSMismatch(object):
    mismatched_id = attr.ib()


@attr.s(init=False)
class IPADDRESSPattern(object):
    pattern = attr.ib()

    def __init__(self, pattern):
        if not isinstance(pattern, bytes):
            raise TypeError("The IP Address pattern must be a bytes string.")

        try:
            if len(pattern) == 4:
                self.pattern = inet_ntop(AF_INET, pattern)
            elif len(pattern) == 16:
                self.pattern = inet_ntop(AF_INET6, pattern)
            else:
                raise ValueError("Unrecognized length for iPAddress: %d" % len(pattern))

        except ValueError:
            raise CertificateError(
                "Invalid IP Address pattern {0!r}.".format(pattern)
            )


@attr.s(init=False)
class IPADDRESS_ID(object):
    ip_address = attr.ib()

    pattern_class = IPADDRESSPattern
    error_on_mismatch = IPADDRESSMismatch

    def __init__(self, ip_address):
        if not isinstance(ip_address, text_type):
            raise TypeError("IPADDRESS-ID must be a unicode string.")

        ip_address = ip_address.strip()
        if not _is_ip_address(ip_address):
            raise ValueError("Invalid IPADDRESS-ID.")

        self.ip_address = ip_address

    def verify(self, pattern):
        if pattern.pattern == self.ip_address:
            return True


# Modified version of service_identity.pyopenssl.verify_hostname with support
# for iPAddress in subjectAltName
def verifyHostname(connection, hostname):
    if _is_ip_address(hostname):
        hostname_id = IPADDRESS_ID(hostname)
    else:
        hostname_id = DNS_ID(hostname)

    cert = connection.get_peer_certificate()
    patterns = []

    # Capture iPAddress IDs from subjectAltnames (which are missing due to
    # a bug in service_identity, https://github.com/pyca/service_identity/issues/12)
    suppress_warning = False
    for i in range(cert.get_extension_count()):
        ext = cert.get_extension(i)
        if ext.get_short_name() == b"subjectAltName":
            names, _ = decode(ext.get_data(), asn1Spec=GeneralNames())
            for n in names:
                name_string = n.getName()
                if name_string == "iPAddress":
                    patterns.append(IPADDRESSPattern(n.getComponent().asOctets()))
                    suppress_warning = True

    with warnings.catch_warnings():

        # si_extract_ids will warn that no subjectAltNames were found,
        # but it's not looking for iPAddresses.  so, if we found those,
        # we can turn off that warning.
        if suppress_warning:
            warnings.simplefilter("ignore", SubjectAltNameWarning)

        # Add in the other standard IDs.
        patterns.extend(si_extract_ids(cert))

    verify_service_identity(
        cert_patterns=patterns,
        obligatory_ids=[hostname_id],
        optional_ids=[],
    )


# These classes are used to tweak the SSL policy so that we ignore SSL host
# verification errors that occur with a self-signed certificate.
class PermissiveClientTLSOptions(ClientTLSOptions):

    # This function is copied from twisted.internet._sslverify verbatim.
    # The only change is that it will call our implementation of verifyHostname,
    # rather than service_identity.pyopenssl.verify_hostname.
    def _identityVerifyingInfoCallback(self, connection, where, ret):
        if where & SSL_CB_HANDSHAKE_START:
            _maybeSetHostNameIndication(connection, self._hostnameBytes)
        elif where & SSL_CB_HANDSHAKE_DONE:
            try:
                verifyHostname(connection, self._hostnameASCII)
            except VerificationError:
                f = Failure()
                transport = connection.get_app_data()
                transport.failVerification(f)


@implementer(IPolicyForHTTPS)
class PermissiveBrowserLikePolicyForHTTPS(BrowserLikePolicyForHTTPS):
    def creatorForNetloc(self, hostname, port):
        certificateOptions = CertificateOptions(
            trustRoot=self._trustRoot)

        return PermissiveClientTLSOptions(
            hostname.decode("ascii"),
            certificateOptions.getContext())
