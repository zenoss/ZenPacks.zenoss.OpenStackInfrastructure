##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import logging
log = logging.getLogger('zen.OpenStack.hostmap')

from collections import defaultdict
import itertools
import re
from twisted.internet import defer

from Products.ZenUtils.Utils import prepId
from ZenPacks.zenoss.OpenStackInfrastructure.utils import resolve_names


class HostMap(object):
    """
    The concept of the HostMap is to accept all of the "host references"
    (names by which hosts are referred to during modeling of an openstack
    environment) and to produce a canonical host ID (ID of a host component
    in ZODB) and host name (label to apply to this component) for each.

    This is done by creating a HostMap object, adding all of the hostrefs (host
    references, which may be hostnames, host IPs, or hostnames with prefixes
    or suffixes.. whatever that OpenStack APIs return), and telling the
    HostMap to "do its thing", and then retrieving the generated host IDs.

    The process can be guided in two ways:
        - by extending the "perform_mapping" function, to make it aware
          of new and interesting ways to determine an ID for a host reference
        - by calling "assert_same_host", which tells the mapper that two
          host references refer to the same host.  For instance, a host
          and its IP, or a host's short name and its FQDN.   These assertions
          are interpreted as authoritative, and unless contradictory, will
          be considered law.

    For a given reference, the same ID should always be returned, unless new
    information (such as an assert_same_host directive) makes that impossible.
    This persistence is achieved by storing the results of freeze_mappings
    in the database, and passing that into thaw_mappings during the next
    modeling cycle.
    """

    mapping_complete = False
    frozen_mapping = {}
    mapping = {}
    asserted_same = {}
    asserted_host_id = {}

    def __init__(self):
        self.clear_mappings()

    def clear_mappings(self):
        """
        Called when the HostMap is created, or any time afterwards, this clears
        all stored state and initializes a blank HostMap.
        """

        self.mapping_complete = False
        self.frozen_mapping = {}
        self.mapping = {}
        self.asserted_same = defaultdict(dict)
        self.asserted_host_id = {}

    def thaw_mappings(self, from_db):
        """
        Given a value (previously returned by freeze_mappings() and stored)
        initialize the HostMap so that those mappings will be retained
        whenever possible.   This is the basis for returning deterministic
        host IDs for any hostref over multiple modeling passes.

        Note that frozen mappings may be overridden by new information, most
        particularly, by "same_host" assertions telling the mapper to
        treat two host references as interchangeable (see "assert_same_host").
        """

        for hostref, hostid in from_db.iteritems():
            self.frozen_mapping[hostref] = hostid

    def add_hostref(self, hostref, source="Unknown"):
        """
        Notify the host mapper about a host reference.
        """

        self.mapping_complete = False

        if hostref in self.mapping:
            return

        if hostref in self.frozen_mapping:
            log.debug("Tracking hostref %s (frozen to ID %s) (source=%s)", hostref, self.frozen_mapping[hostref], source)
        else:
            log.debug("Tracking hostref %s (source=%s)", hostref, source)

        self.mapping[hostref] = None

    def assert_host_id(self, hostref, hostid):
        self.asserted_host_id[hostref] = hostid

    def assert_same_host(self, hostref1, hostref2, source="Unknown", oneway=False):
        """
        Firmly assert that two hostrefs  (names, IPs, etc) refer to the
        same host.
        """

        if hostref1 == hostref2:
            return

        if hostref1 not in self.mapping:
            log.warning("assert_same_host(source=%s): %s is not a valid host reference -- ignoring", source, hostref1)
            return

        if hostref2 not in self.mapping:
            log.warning("assert_same_host(source=%s): %s is not a valid host reference -- ignoring", source, hostref2)
            return

        self.asserted_same[hostref1][hostref2] = source

        if not oneway:
            self.asserted_same[hostref2][hostref1] = source

    @defer.inlineCallbacks
    def perform_mapping(self):
        """
        Once all hostrefs have been registered, and all assertions made,
        perform_mapping is called to resolve all these hostrefs to host IDs.

        It takes into account frozen mappings and assertions, as well other
        rules about how to map hosts to IDs and hostnames.

        Once this is called, the all_hostids, get_hostid, and
        get_hostname_for_hostid functions are available.
        """

        log.debug("Resolving all referenced hostnames")

        # (ignore the obviously bogus ones, just to save time)
        hostnames = [x for x in self.mapping.keys()
                     if (":" not in x and "@" not in x)]

        resolved = yield resolve_names(hostnames)
        resolved_by_ip = defaultdict(set)
        for name, ip in resolved.iteritems():
            if ip is not None:
                resolved_by_ip[ip].add(name)

            # If the name and IP are known references, but might not
            # be known to be identical, add that assertion.
            if name in self.mapping and ip in self.mapping:
                self.assert_same_host(name, ip, source="DNS Resolution")

        for ip, hostnames in resolved_by_ip.iteritems():
            # all possible combinations of hostnames that share an IP
            # are interchangeable.  Add those assertions where
            # we have seen both versions of the name.
            for hostref1, hostref2 in itertools.combinations(hostnames, 2):
                if hostref1 in self.mapping and hostref2 in self.mapping:
                    self.assert_same_host(hostref1, hostref2, source="Resolve to same IP")

        new_mapping = {}
        original_name = {}
        for hostref in self.mapping:
            # Strip anything after an '@' or ':" and convert to lowercase.
            clean_hostref = re.sub(r'[@:].*$', '', hostref).lower()

            # Remove any whitespace.
            clean_hostref = re.sub(r'\s', '', clean_hostref)

            # Remember what the original one was.
            original_name[clean_hostref] = hostref

            naive_hostid = prepId("host-{0}".format(clean_hostref))

            log.debug("Potential host mapping: %s -> %s", hostref, naive_hostid)
            new_mapping[hostref] = naive_hostid

        # when we've seen both the cleaned name and the original name in
        # different places, it's important to remember that they're the same.
        for clean, orig in original_name.iteritems():
            if clean in new_mapping and orig in new_mapping:
                self.assert_same_host(orig, clean, source="Cleaned name vs original name", oneway=True)

        for hostref in new_mapping:
            if hostref in self.asserted_host_id:
                log.debug("Forcing ID of %s to %s (asserted host ID)", hostref, self.asserted_host_id[hostref])
                new_mapping[hostref] = self.asserted_host_id[hostref]
                continue

            # Enforce assertions about different identifiers referring to the same host.
            if hostref in self.asserted_same:
                same_as_keys = set([new_mapping[x] for x in self.asserted_same[hostref]])

                if len(same_as_keys) > 1:
                    log.warning("The host referred to as '%s' is asserted to be identical to multiple hosts with conflicting IDs", hostref)
                    for same_as in sorted(self.asserted_same[hostref]):
                        log.error(" %s = %s = %s", hostref, same_as, new_mapping[same_as])
                    same_as = sorted(self.asserted_same[hostref].keys())[0]
                    if new_mapping[hostref] != new_mapping[same_as]:
                        log.warning(" Selected %s (%s)", same_as, new_mapping[same_as])
                        new_mapping[hostref] = new_mapping[same_as]
                elif len(same_as_keys) == 1:
                    same_as = self.asserted_same[hostref].keys()[0]
                    if new_mapping[hostref] != new_mapping[same_as]:
                        # choose the longest of the keys and use that for both.
                        new_key = max([new_mapping[hostref], new_mapping[same_as]], key=len)

                        log.debug("Since host %s is asserted to be identical to host %s, using ID %s for both", hostref, same_as, new_key)
                        new_mapping[hostref] = new_key
                        new_mapping[same_as] = new_key
            elif hostref in self.frozen_mapping and new_mapping[hostref] != self.frozen_mapping[hostref]:
                # if this hostref was previously mapped to a specific ID,
                # maintain that mapping.
                log.debug("Maintaining frozen mapping of host %s to ID %s", hostref, self.frozen_mapping[hostref])
                new_mapping[hostref] = self.frozen_mapping[hostref]

        log.debug("Final mapping:")
        for hostref, host_id in new_mapping.iteritems():
            self.mapping[hostref] = new_mapping[hostref]
            log.debug("  %s -> %s", hostref, host_id)

        self.mapping_complete = True

        yield None

    def all_hostids(self):
        return sorted(set(self.mapping.values()))

    def get_hostid(self, hostref):
        """
        For a host reference, return the canonical host ID to use.
        """

        if not self.mapping_complete:
            raise Exception("perform_mapping must be called before get_hostid")

        if hostref not in self.mapping:
            raise Exception("Host reference %s unrecognized. Ensure that add_hostref(%s) is done before attempting to get_hostid(%s)" % (hostref, hostref, hostref))

        return self.mapping[hostref]

    def get_hostname_for_hostid(self, hostid):
        """
        For a host ID, return a suitable host name (label) to use.

        Note that while host IDs mappings are intended to be stable, hostnames
        are allowed to change, because many host references may map to the same
        host ID, and the "best" of those references to use as a title may vary
        based on the selection criteria and information at hand.

        Because of this, hostnames returned by this function should be used
        as labels, never as internal identifiers.  (use the hostid for that!)
        """

        if not self.mapping_complete:
            raise Exception("perform_mapping must be called before get_hostname_for_hostid")

        if not hostid.startswith("host-"):
            raise Exception("get_hostname_for_hostid must be supplied with a valid hostid")

        # despite what I said above, at the moment, the algorithm for selecting
        # a hostid is probably the best bet for selecting a hostname, as well.
        # So just strip off the host- prefix and go with that.  This may
        # not always be the way this works in the future, though!
        return hostid[5:]

    def freeze_mappings(self):
        """
        Returns a set of mappings that should be persisted and passed back
        into thaw_mappings()
        """

        if not self.mapping_complete:
            raise Exception("perform_mapping must be called before freeze_mappings")

        frozen = {}
        for hostref, hostid in self.mapping.iteritems():
            frozen[hostref] = hostid

        for hostref, hostid in self.frozen_mapping.iteritems():
            if hostref not in frozen:
                frozen[hostref] = hostid

        return frozen
