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

import logging
log = logging.getLogger('zen.OpenStack.txapiclient')

import attr
from socket import inet_ntop, inet_pton, AF_INET, AF_INET6
import warnings

from service_identity import VerificationError, CertificateError, SubjectAltNameWarning
from service_identity.pyopenssl import (
    decode, GeneralNames, IA5String, ID_ON_DNS_SRV)
from service_identity._common import (
    DNS_ID, DNSPattern, URIPattern, SRVPattern,
    _is_ip_address, text_type, verify_service_identity)

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
    ids = []

    # Basically the same as service_identity.pyopenssl.extract_ids, but with
    # subjectAltName support for iPAddress IDs and IP Addresses stuck in dNSName ids
    for i in range(cert.get_extension_count()):
        ext = cert.get_extension(i)
        if ext.get_short_name() == b"subjectAltName":
            names, _ = decode(ext.get_data(), asn1Spec=GeneralNames())
            for n in names:
                name_string = n.getName()

                if name_string == "iPAddress":
                    ids.append(IPADDRESSPattern(n.getComponent().asOctets()))

                elif name_string == "dNSName" and _is_ip_address(n.getComponent().asOctets().strip()):
                    # If an IP Address is passed as a dNSName, it will
                    # cause service_identity to throw an exception, as
                    # it doesn't consider this valid.   From reading the
                    # RFCs, i think it's a gray area, so i'm going to
                    # allow it, since we've seen it happen with a customer.
                    try:
                        ip_string = n.getComponent().asOctets().strip()
                        if ":" in ip_string:
                            value = inet_pton(AF_INET6, ip_string)
                        else:
                            value = inet_pton(AF_INET, ip_string)

                        ids.append(IPADDRESSPattern(value))
                    except CertificateError as e:
                        log.warning(
                            "Ignoring invalid dNSName record in subjectAltName: %s", e)

                # Normal behavior below:
                elif name_string == "dNSName":
                    ids.append(DNSPattern(n.getComponent().asOctets()))
                elif name_string == "uniformResourceIdentifier":
                    ids.append(URIPattern(n.getComponent().asOctets()))
                elif name_string == "otherName":
                    comp = n.getComponent()
                    oid = comp.getComponentByPosition(0)
                    if oid == ID_ON_DNS_SRV:
                        srv, _ = decode(comp.getComponentByPosition(1))
                        if isinstance(srv, IA5String):
                            ids.append(SRVPattern(srv.asOctets()))
                        else:  # pragma: nocover
                            raise CertificateError(
                                "Unexpected certificate content.")

    if not ids:
        # http://tools.ietf.org/search/rfc6125#section-6.4.4
        # A client MUST NOT seek a match for a reference identifier of CN-ID if
        # the presented identifiers include a DNS-ID, SRV-ID, URI-ID, or any
        # application-specific identifier types supported by the client.
        warnings.warn(
            "Certificate has no `subjectAltName`, falling back to check for a "
            "`commonName` for now.  This feature is being removed by major "
            "browsers and deprecated by RFC 2818.",
            SubjectAltNameWarning
        )
        ids = [DNSPattern(c[1])
               for c
               in cert.get_subject().get_components()
               if c[0] == b"CN"]

    verify_service_identity(
        cert_patterns=ids,
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
