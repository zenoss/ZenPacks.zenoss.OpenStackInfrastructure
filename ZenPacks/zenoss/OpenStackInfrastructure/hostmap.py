##############################################################################
#
# Copyright (C) Zenoss, Inc. 2016-2018, all rights reserved.
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


class InvalidHostIdException(Exception):
        pass

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
    hostref_sources = {}
    asserted_same = {}
    asserted_host_id = {}
    resolved_hostnames = {}    

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
        self.hostref_sources = defaultdict(set)
        self.asserted_same = defaultdict(dict)
        self.asserted_host_id = {}
        self.resolved_hostnames = {}

    def normalize_hostref(self, hostref):
        # convert to lowercase and strip leading or trailing whitespace.
        if hostref:
            return hostref.lower().strip()

    def clean_hostref(self, hostref):
        # this takes things further than normalize_hostref does, also stripping
        # all whitespace and anything after a @ or :

        # Strip anything after an '@' or ':" and convert to lowercase.
        clean_hostref = re.sub(r'[@:].*$', '', hostref).lower()

        # Remove any whitespace.
        clean_hostref = re.sub(r'\s', '', clean_hostref)

        return clean_hostref

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

    def has_hostref(self, hostref):
        """
        Check if there exists a hostref in self.mapping
        """
        hostref = self.normalize_hostref(hostref)
        return hostref in self.mapping

    def check_hostref(self, hostref, source):
        hostref = self.normalize_hostref(hostref)
        if not self.has_hostref(hostref):
            log.error("Hostref: '%s' from source: '%s' is not in known mapping! "
                      "Please check that this is a valid host...", hostref, source)

    def add_hostref(self, hostref, source="Unknown"):
        """
        Notify the host mapper about a host reference.
        """
        hostref = self.normalize_hostref(hostref)
        self.mapping_complete = False

        # a 'None' hostref is useless, just ignore it and return.
        if hostref is None:
            log.debug("Ignoring null hostref (source=%s)", source)
            return

        if hostref in self.frozen_mapping:
            log.debug("Tracking hostref %s (frozen to ID %s) (source=%s)", hostref, self.frozen_mapping[hostref], source)
        else:
            log.debug("Tracking hostref %s (source=%s)", hostref, source)

        self.hostref_sources[hostref].add(source)

        if not self.has_hostref(hostref):
            self.mapping[hostref] = None

    def assert_host_id(self, hostref, hostid):
        hostref = self.normalize_hostref(hostref)


        log.debug("assert_host_id: %s=%s", hostref, hostid)
        self.asserted_host_id[hostref] = hostid

    def assert_same_host(self, hostref1, hostref2, source="Unknown", oneway=False):
        """
        Firmly assert that two hostrefs  (names, IPs, etc) refer to the
        same host.
        """

        hostref1 = self.normalize_hostref(hostref1)
        hostref2 = self.normalize_hostref(hostref2)
        if not self.has_hostref(hostref1):
            log.warning("assert_same_host: (Source=%s): %s is not a valid host reference -- ignoring", source, hostref1)
            return

        if not self.has_hostref(hostref2):
            log.warning("assert_same_host: (Source=%s): %s is not a valid host reference -- ignoring", source, hostref2)
            return

        if hostref1 == hostref2:
            return

        log.debug("assert_same_host: (Source=%s) %s=%s", source, hostref1, hostref2)
        self.asserted_same[hostref1][hostref2] = source

        if not oneway:
            log.debug("assert_same_host: (Source=%s) %s=%s  (symmetric)", source, hostref2, hostref1)
            self.asserted_same[hostref2][hostref1] = source

    def all_asserted_same(self, hostref_a, seen=None, sources=None):
        # recursively search for all hostrefs that are the same as the one
        # passed in.

        hostref_a = self.normalize_hostref(hostref_a)
        if seen is None:
            seen = set(hostref_a)

        if sources is None:
            sources = []

        same = []
        for hostref_b, source in self.asserted_same[hostref_a].iteritems():
            if hostref_b not in seen:
                path_source = sources + ["%s: %s" % (hostref_b, source)]
                seen.add(hostref_b)
                same.append((hostref_b, path_source))
                same.extend(self.all_asserted_same(hostref_b, seen=seen, sources=path_source))

        return same

    @defer.inlineCallbacks
    def resolve_and_assert_hostnames(self):
        log.debug("Resolving all referenced hostnames")

        # (ignore the obviously bogus ones, just to save time)
        hostnames = [x for x in self.mapping.keys()
                     if (":" not in x and "@" not in x)]

        resolved = yield resolve_names(hostnames)
        resolved_by_ip = defaultdict(set)
        for name, ip in resolved.iteritems():
            if ip is not None:
                if ip.startswith("127."):
                    log.debug("  %s resolves to an apparent local IP (%s) - ignoring it.", name, ip)
                    continue

                resolved_by_ip[ip].add(name)

            # If the name and IP are known references, but might not
            # be known to be identical, add that assertion.
            if self.has_hostref(name) and self.has_hostref(ip):
                self.assert_same_host(name, ip, source="DNS Resolution")

        for ip, hostnames in resolved_by_ip.iteritems():
            # all possible combinations of hostnames that share an IP
            # are interchangeable.  Add those assertions where
            # we have seen both versions of the name.
            for hostref1, hostref2 in itertools.combinations(hostnames, 2):
                if self.has_hostref(hostref1) and self.has_hostref(hostref2):
                    self.assert_same_host(hostref1, hostref2, source="Resolve to same IP")

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

        # Resolve all the hostnames and assert equality between hostnames with
        # the same IP
        yield self.resolve_and_assert_hostnames()

        # Determine "naive" mappings for all hostrefs.  These are
        # simple IDs based on the hostref with a host-prefix and a little
        # light cleanup.
        naive_mapping = {}
        for hostref in self.mapping:
            clean_hostref = self.clean_hostref(hostref)

            # If that "cleaned up" hostref (that is, after we stripped
            # off suffixes and whitespace) has also been seen, we can
            # safely assume that they're the same underlying host.
            if clean_hostref in self.mapping:
                self.assert_same_host(
                    hostref, clean_hostref,
                    source="Cleaned name vs original name", oneway=True)

            naive_mapping[hostref] = prepId("host-{0}".format(clean_hostref))

        new_mapping = {}
        for hostref in self.mapping:
            if hostref in new_mapping:
                log.debug("Since hostref %s is already mapped to %s, skipping it", hostref, self.mapping[hostref])
                continue

            naive_hostid = naive_mapping[hostref]
            log.debug("Potential host mapping: %s -> %s", hostref, naive_hostid)
            new_mapping[hostref] = naive_hostid

        already_logged = set()
        for hostref in new_mapping:
            # Apply the same mapping for other hostrefs that have been
            # asserted (directly or indirectly) to be equivalent.

            all_same = self.all_asserted_same(hostref)

            other_hostrefs = set()
            other_hostids = set()
            for hostref_b, source_b in all_same:
                other_hostrefs.add(hostref_b)
                other_hostids.add(naive_mapping[hostref_b])

            if len(other_hostids) > 1:
                # choose the longest host ID as the one to use for all
                # of these hostrefs.   Seems deterministic, and it's no
                # more right or wrong than any other selection..
                best_hostid = max(other_hostids, key=len)

                ids = tuple(sorted(set(list(other_hostrefs) + [hostref])))
                if ids not in already_logged:
                    already_logged.add(ids)
                    log.debug(
                        "[%s] Multiple possible host IDs found for %s.  Selected %s",
                        hostref,
                        ", ".join(ids),
                        best_hostid)

                # Store that.
                new_mapping[hostref] = best_hostid
                # Store it for the other equivalent hostrefs too.
                for hostref_b in other_hostrefs:
                    source_b = ", ".join(itertools.chain.from_iterable([x[1] for x in all_same if x[0] == hostref_b]))
                    if new_mapping[hostref_b] != best_hostid:
                        log.debug(
                            "  Extending potential mapping to %s -> %s same because of (%s)",
                            hostref_b, best_hostid, source_b)
                        new_mapping[hostref_b] = best_hostid

        # apply user-asserted host IDs
        for hostref in new_mapping:
            if hostref in self.asserted_host_id:
                log.debug("Forcing ID of %s to %s (asserted host ID)", hostref, self.asserted_host_id[hostref])
                new_mapping[hostref] = self.asserted_host_id[hostref]

                # Note that this does not pull in other host references
                # that have been asserted to be the same as this one-
                # if a user is having to drop down to this level, they
                # might have a reason to do something other than what we expect.
                continue

            if hostref in self.frozen_mapping and new_mapping[hostref] != self.frozen_mapping[hostref]:
                # if this hostref was previously mapped to a specific ID,
                # maintain that mapping.
                log.debug("Maintaining frozen mapping of host %s to ID %s", hostref, self.frozen_mapping[hostref])
                new_mapping[hostref] = self.frozen_mapping[hostref]

        log.debug("Final mapping:")
        for hostref, host_id in new_mapping.iteritems():
            self.mapping[hostref] = new_mapping[hostref]
            log.debug("  %s -> %s", hostref, host_id)

        self.mapping_complete = True

        # Determine IPs for all hostnames, if possible
        all_hostnames = [self.get_hostname_for_hostid(x) for x in self.all_hostids()]
        self.resolved_hostnames = yield resolve_names(all_hostnames)

        yield None

    def all_hostids(self):
        return sorted(set(self.mapping.values()))

    def get_hostid(self, hostref):
        """
        For a host reference, return the canonical host ID to use.
        """

        hostref = self.normalize_hostref(hostref)
        if not self.mapping_complete:
            raise Exception("perform_mapping must be called before get_hostid")

        if not self.has_hostref(hostref):
            raise Exception("Host reference %s unrecognized. Ensure that add_hostref(%s) is done before attempting to get_hostid(%s)" % (hostref, hostref, hostref))

        return self.mapping[hostref]

    def get_ip_for_hostid(self, hostid):
        """
        Returns the IP corresponding to the hostname for this hostid, if
        it resolves, or None if it does not.
        """
        hostname = self.get_hostname_for_hostid(hostid)
        return self.resolved_hostnames.get(hostname, None)

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
            log.debug("Invalid hostid: '%s' found in hostmap!", hostid)
            raise InvalidHostIdException("get_hostname_for_hostid must be supplied with a valid hostid")

        # despite what I said above, at the moment, the algorithm for selecting
        # a hostid is probably the best bet for selecting a hostname, as well.
        # So just strip off the host- prefix and go with that.  This may
        # not always be the way this works in the future, though!
        return hostid[5:]

    def get_sources_for_hostid(self, hostid):
        if not self.mapping_complete:
            raise Exception("perform_mapping must be called before get_sources_for_hostid")

        sources = set()
        for hostref, mapped_hostid in self.mapping.iteritems():
            if mapped_hostid == hostid:
                sources.update(self.hostref_sources[hostref])

        return list(sources)

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
