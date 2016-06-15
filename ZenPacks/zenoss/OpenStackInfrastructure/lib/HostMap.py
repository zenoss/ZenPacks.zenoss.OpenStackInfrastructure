###########################################################################
# This program is part of Zenoss Core, an open source monitoring platform.
# Copyright (C) 2014, Zenoss Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 2 or (at your
# option) any later version as published by the Free Software Foundation.
#
# For complete information please visit: http://www.zenoss.com/oss/
###########################################################################

import logging
log = logging.getLogger('osi.lib.HostMap')
logging.basicConfig(level=logging.DEBUG)

import socket
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet import reactor

from ZenPacks.zenoss.OpenStackInfrastructure.lib.domains import (
                                                        get_dominant_domain,
                                                        extract_valid_hostname,
                                                        )
from Products.ZenUtils.Utils import prepId
from Products.ZenUtils.IpUtil import isip


@inlineCallbacks
def resolve_name(name):
    ## If you have an IP already, return it.
    # if isip(name):
    #    returnValue((name, name))
    ip = yield reactor.resolve(name)
    returnValue((name, ip))


@inlineCallbacks
def resolve_names(names):
    """Resolve names to IP addresses in parallel.
    Names must be an iterable of names.

    Example return value:

        {
            'example.com': '192.168.1.2',
            'www.google.com': '8.7.6.5',
            'doesntexist': None,
        }
    """
    from twisted.internet.defer import DeferredList
    results = yield DeferredList(
        [resolve_name(n) for n in names],
        consumeErrors=True)

    result_map = {n: None for n in names}
    for success, result in results:
        if success:
            result_map[result[0]] = result[1]

    returnValue(result_map)


@inlineCallbacks
def resolve_names_with_retries(names, retries=2):
    result_map = {n: None for n in names}
    for i in range(retries):
        todo = [n for n in names if not result_map.get(n)]
        if todo:
            results = yield resolve_names(todo)
            result_map.update(results)

    returnValue(result_map)


# ==============================================================================
class hostMapError(Exception):
    """Parent class of all exceptions raised by api clients."""
    pass


class HostResolver(object):
    """
    Create a host-ip relationship that can be referenced later as an object.
    """
    def __init__(self):
        self.resolved_hostnames = {}
        self.locked = False

    def lock(self):
        self.locked = True

    def unlock(self):
        self.locked = False

    def add_hostnames(self, mapping):

        # Ensure all hostname keys are valid
        mapping = dict((extract_valid_hostname(k), v) for k, v in mapping.iteritems())

        # Force addition of map: mapping must be a dict of form {name: ip}
        if self.locked:
            log.warn("Denied: add_hostnames() to locked HostResolver")
        else:
            self.resolved_hostnames.update(mapping)

    @inlineCallbacks
    def bulk_update_names(self, hostnames):
        # Resolve and update from a list of names.
        if self.locked:
            log.warn("Denied: add hostnames to locked HostResolver")
            return

        # Ensure that all hostnames are valid
        hostnames = set(extract_valid_hostname(h) for h in hostnames)
        resolved_map = yield resolve_names_with_retries(hostnames)
        self.resolved_hostnames.update(resolved_map)

        # If hostnames don't resolve, we still need to add them without IP
        # because hosts resolution could be broken..
        for host in hostnames:
            if host not in self.resolved_hostnames:
                log.debug("Adding hostname: %s without IP. Check DNS!", host)
                self.resolved_hostnames.update(host = None)

    def add_hostname(self, name, ip=None):
        # Add single hostname-ip pair. Ensure valid format
        if self.locked:
            log.warn("Denied: add hostname:ip pair to locked HostResolver")
            return
        if not isip(ip):
            log.ERROR("Denied: Can't add invalid IP: %s", ip)
            return

        valid_name = extract_valid_hostname(name)
        if not valid_name:
            log.ERROR("Denied: Can't add invalid Hostname: %s", name)

        self.resolved_hostnames[valid_name] = ip

    def getIpFromName(self, hostname):
        ip = self.resolved_hostnames.get(hostname)
        if not ip:
            log.debug("resolved_hostnames: Missing IP for host %s", hostname)
        return ip

    def hasIpFromName(self, name):
        if name in self.resolved_hostnames:
            return True

    def get_ip_addresses(self):
        return set(self.resolved_hostnames.values())

    def get_resolved(self):
        return self.resolved_hostnames


class HostMap(object):
    '''
    HostMap represents known hosts in the OSI cluster.
    It requires a valid HostResolver instance object in order to get
    pre-resolved IP addresses. When fully populated, objects have:
    @locked: lock host from updates
    @ip: The IP address
    @hostname: The optional hostname
    @canonical_hostname: The hostname that represents this host, deterministic
    '''

    def __new__(cls, ip=None, hostname=None, canonical=None):
        if not (ip or hostname):
            log.error("Missing IP and Hostname for HostMap creation!")
            return
        else:
            return object.__new__(cls)

    def __init__(self, ip=None, hostname=None, canonical=None):

        if not (ip or hostname):
            log.error("Missing IP or Hostname for HostMap creation!")
            # raise Exception("Missing IP or Hostname for HostMap creation!")

        self.locked = False

        if not ip:
            log.debug("Missing IP for HostMap creation. Check DNS")
            self.ip = None
        elif not isip(ip):
            log.warn("Bad IP in HostMap creation!")
            self.ip = None
        else:
            self.ip = ip

        self.hostnames = set()
        if hostname:
            self.add_hostname(hostname)

        self.canonical_hostname = None
        if canonical:
            self.canonical_hostname = canonical

    def __eq__(self, other):
        # Allows set(HostMap) to determine equailty based on contents
        if isinstance(other, HostMap):
            return self.ip == other.ip and self.hostnames == other.hostnames
        return False

    def __ne__(self, other):
        # Allows set(HostMap) to determine equailty based on contents
        return (not self.__eq__(other))

    def __repr__(self):
        # Allows set(HostMap) to determine equailty based on contents
        return 'H({s.ip!r}, {s.hostnames!r})'.format(s=self)

    def __hash__(self):
        # Allows set(HostMap) to determine equailty based on contents
        return hash(repr(self))

    def lock(self):
        self.locked = True

    def unlock(self):
        self.locked = False

    def get_id(self):
        # NOTE: process information in self.hostnames in order to synthesize a
        # unique hostname. Typically we will take the most fully qualified
        # domain name that is found.
        if not self.hostnames:
            log.warn("get_id: No hostnames available")
            return

        return prepId('host-{}'.format(self.canonical_hostname))

    def get_ip(self):
        return self.ip

    def get_canonical_hostname(self):
        # NOTE: process information in self.hostnames in order to synthesize a
        # unique hostname. Take the first host in alphabetical order
        # Use cached value if available
        if not self.hostnames:
            log.warn("get_canonical: No hostnames for HostMap %s", self.ip)
            return

        if self.canonical_hostname:
            return self.canonical_hostname

        domain = get_dominant_domain(self.hostnames)
        if not domain:
            log.debug("Missing domain for %s: Returning first host", self.ip)
            hosts = sorted(self.hostnames)
            canonical = next((x for x in hosts if not isip(x)), hosts[0])
            return canonical

        host_candidates = [h for h in self.hostnames if domain in h]
        return sorted(host_candidates)[0]

    def set_canonical_hostname(self):
        # NOTE: process information in self.hostnames in order to synthesize a
        # unique hostname. Typically we will take the most fully qualified
        # domain name that is found.
        if self.locked:
            log.warn("Won't update canonical on locked HostMap %s", self.ip)
            return

        self.canonical_hostname = None
        self.canonical_hostname = self.get_canonical_hostname()

    def add_hostname(self, hostname, ip=None):
        # NOTE: We don't update self.canonica_hostname here. Must do manually.
        if self.locked:
            log.warn("Won't add %s to locked HostMap %s", hostname, self.ip)
            return

        # If hostname is in hostnames, pass, else check IP: add it
        hostname = extract_valid_hostname(hostname)
        if hostname in self.hostnames:
            log.debug("add_hostname: host alreay exists!")
            return

        if not self.ip and ip:
            log.debug("adding hostname %s, ip: %s", hostname, self.ip)
            self.ip = ip
            self.hostnames.add(hostname)
            return

        if ip and self.ip:
            if self.ip == ip:
                log.debug("adding hostname, ip: %s -> %s", hostname, self.ip)
                self.hostnames.add(hostname)
            else:
                log.debug("add_hostname: IPs don't match! %s, %s for %s",
                        self.ip, ip, hostname)
            return

        self.hostnames.add(hostname)

    def update_hostnames(self, hostnames):
        # Add hostnames in batch.
        # We blindly assume that these hostnames are valid for this host.
        if self.locked:
            log.warn("Won't add hosts to locked HostMap %s", self.ip)
            return

        if isinstance(hostnames, (list, set)):
            for host in hostnames:
                self.add_hostname(extract_valid_hostname(host))

    def has_ip(self, ip):
        if ip == self.ip:
            return True

    def has_hostname(self, hostname):
        if hostname.lower() in self.hostnames:
            return True

    def is_equal(self, hostMap):
        # This is comparison of two objects.
        # NOTE: Comparison of hostnames is suspect: Why can't they differ?
        if hostMap.get_ip() in self.ip and hostMap.hostnames == self.hostnames:
            return True

    def valid_hostname_ip(self):
        # Check if hostname corresponds to a valid IP via socket call
        # NOTE: socket calls are blocking; this can be slow!
        if socket.gethostbyname(self.get_canonical_hostname()) == self.ip:
            return True

    def merge(self, osiHost):
        # Merge 2 host objects that have same IP's
        self.locked = False
        if self.ip == osiHost.ip:
            self.hostnames = osiHost.hostnames.union(self.hostnames)

    def is_subset(self, osiHost):
        # Merge 2 host objects that have like IP's
        if self.ip == osiHost.ip and self.hostnames < osiHost.hostnames:
            return True


class HostGroup(object):
    '''
    Class that contains a collection of HostMap objects.
    '''

    def __init__(self, hostResolver=None):
        if not isinstance(hostResolver, HostResolver):
            raise hostMapError("Invalid HostResolver instance for HostGroup")
        self.hostResolver = hostResolver
        self.hosts = set()

    def update_Resolver(self, hostResolver):
        if not isinstance(hostResolver, HostResolver):
            raise hostMapError("Invalid HostResolver instance for HostGroup")
        else:
            self.hostResolver = hostResolver

    def get_host_by_name_or_ip(self, thing):
        # Determine if thing is valid ip
        thing = extract_valid_hostname(thing)
        if isip(thing):
            return self.get_host_by_ip(thing)

        # Find host by name only
        host = self.get_host_by_name(thing)
        if host:
            return host

        # Be careful: Need to convert name to ip and check again
        ip = self.hostResolver.getIpFromName(thing)
        if ip:
            return self.get_host_by_ip(ip)

    def get_host_by_ip(self, ip):
        # Determine if ip is valid
        if not isip(ip):
            log.debug("Invalid IP: %s", ip)
            return

        # Find the proper host in hosts set given host_or_ip
        for host in self.hosts:
            if ip == host.get_ip():
                return host

    def get_host_by_name(self, name):
        # Determine if name is valid
        name = extract_valid_hostname(name)

        # Find the proper host in hosts set given host_or_ip
        for host in self.hosts:
            if name in host.hostnames:
                return host

    def has_equivalent(self, osiHost):
        # Boolean: Test if self has equiv osiHost buy value
        if not isinstance(osiHost, HostMap):
            log.warn("host is non-HostMap. Unable to compare.")
            return

        # Find the proper host in hosts set given host_or_ip
        for host in self.hosts:
            if osiHost.ip == host.ip and osiHost.hostnames == host.hostnames:
                return True
        return False

    def is_subset_host(self, osiHost):
        # If osiHost is subset of some host in set, return True
        if not isinstance(osiHost, HostMap):
            log.warn("host is non-HostMap. Unable to compare.")
            return

        for host in self.hosts:
            if osiHost.is_subset(host):
                return True

        return False

    def get_subset_host(self, osiHost):
        # Return host that is subset of this host
        if not isinstance(osiHost, HostMap):
            log.warn("host is non-HostMap. Unable to compare.")
            return

        for host in self.hosts:
            if osiHost.is_subset(host):
                return host

    def has_hostname(self, hostname):
        # Boolean: Test if osiHost IP is in hosts set
        for host in self.hosts:
            if hostname in host.hostnames:
                return True
        return False

    def has_ip(self, ip):
        # Boolean: Test if osiHost IP is in hosts set
        for host in self.hosts:
            if host.ip == ip:
                return True

        return False

    def add_host(self, osiHost):
        # Add HostMap instance to set, but only if unique. Otherwise merge.
        if not isinstance(osiHost, HostMap):
            log.warn("Can't add an non HostMap object")
            return

        if self.has_equivalent(osiHost) or self.is_subset_host(osiHost):
            log.debug("osiHost %s is Subset", osiHost)
            return

        host_subset = self.get_subset_host(osiHost)
        if host_subset:
            log.debug("Found subset: %s of %s", host_subset, osiHost)
            host_subset.merge(osiHost)
        else:
            self.hosts.add(osiHost)

    def remove_host(self, osiHost):
        # Delete HostMap object
        if not isinstance(osiHost, HostMap):
            log.debug("Can't remove an non HostMap object")
            return

        self.hosts.remove(osiHost)

    def update_canonical_hostnames(self):
        # Update canaonical_hostname for all hosts
        for host in self.hosts:
            host.set_canonical_hostname()

    def add_hostname(self, name):
        # Add hostname if it is not already in set.
        name = extract_valid_hostname(name)
        if not name:
            log.warn("Missing name for add_hostname!")
            return

        # If host already in the set, find it and return host
        found = self.get_host_by_name_or_ip(name)
        if found:
            found.add_hostname(name)
            return

        # If new host is an IP, add it as such
        if isip(name):
            self.add_host(HostMap(ip=name))
            return

        # Host is new hostname, so add it as such. IP can be None:
        ip = self.hostResolver.getIpFromName(name)
        if ip:
            osiHost = HostMap(ip)
            osiHost.add_hostname(name)
        else:
            log.warn("Adding host %s to a baren (missing ip) host!", name)
            osiHost = HostMap(hostname=name)

        self.add_host(osiHost)

    def add_hostnames(self, hostnames):
        # Add an HostMap for each corresponding name in hostnames
        for host in hostnames:
            self.add_hostname(host)
# ==============================================================================
