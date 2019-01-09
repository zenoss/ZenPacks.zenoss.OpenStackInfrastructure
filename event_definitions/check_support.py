#!/usr/bin/env python

import argparse
from required_traits import zenoss_required_events
from event_definitions import get_event_definitions


# Compares the out of the box versions of event_definitions.yaml with
# the requirements of this zenpack, to see what traits are missing.not
#
# Optionally (--with-additions) include the zenoss_additions.yaml file, to
# see if that fixes what is missing.


class CheckSupport(object):
    _legacy = None
    version = None
    current = None

    @property
    def legacy(self):
        if not self._legacy:
            self._legacy = get_event_definitions('legacy')
        return self._legacy

    def __init__(self, version, with_additions=True):
        self.version = version
        self.current = get_event_definitions(self.version, with_additions=with_additions)

    def go(self):
        print "\nChecking event definitions from %s" % self.version

        for event_type, required_traits in sorted(zenoss_required_events.iteritems()):
            for required_trait in required_traits:
                if isinstance(required_trait, list):
                    # an "or" condition- as long as one of the specified traits
                    # is there, we're good.
                    found_traits_legacy = [x for x in required_trait if self.legacy.has_trait(event_type, x)]
                    found_traits_current = [x for x in required_trait if self.current.has_trait(event_type, x)]

                    if not found_traits_legacy:
                        print "%s: requires one of %s, but the legacy definition does not provide any of them" % (
                            event_type, required_trait)
                        continue

                    if not found_traits_current:
                        print "%s: requires one of %s, but the %s definition does not provide any of them" % (
                            event_type, required_trait, self.version)
                        continue

                    ok = False
                    for l in found_traits_legacy:
                        for c in found_traits_current:
                            if self.legacy.trait_fields(event_type, l) == self.current.trait_fields(event_type, c):
                                # found a trait which provides the same fields as one of
                                # the legacy ones, so i think we're good.
                                ok = True

                    # whitelist a few traits that we know are probably fine.
                    # event_definitions.yaml supports a few syntaxes that
                    # i haven't implemented (multiple field names, different
                    # split syntax, etc)
                    for whitelisted_trait in ['resource_id', 'host']:
                        if whitelisted_trait in found_traits_current:
                            # don't worry about these- it's probably fine.
                            ok = True

                    if ok:
                        continue

                    print "%s: requires one of %s.  The the %s definition provides %s, but the included fields don't appear to match any of these in the legacy version" % (
                        event_type, required_trait, self.version, found_traits_current)
                    print "  legacy:"
                    for l in found_traits_legacy:
                        print "    %s: %s" % (l, self.legacy.trait_fields(event_type, l))
                    print "  %s:" % self.version
                    for c in found_traits_current:
                        print "    %s: %s" % (c, self.current.trait_fields(event_type, c))

                else:

                    if not self.current.has_trait(event_type, required_trait):
                        print "%s: requires trait %s, but the %s definition does not provide it." % (
                            event_type, required_trait, self.version)

                        for possible_trait in self.current.get_traits(event_type):
                            if self.legacy.trait_fields(event_type, required_trait) == self.current.trait_fields(event_type, possible_trait):
                                print "  %s has matching fields (%s), however- perhaps this could be used?" % (
                                    possible_trait, self.current.trait_fields(event_type, possible_trait))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--with-additions',
        dest='with_additions',
        action='store_true',
        default=False,
        help="Append zenoss_additions.yaml to the default event_definitions.yaml files")

    args = parser.parse_args()

    for supported_version in ['pike', 'queens', 'rocky']:
        CheckSupport(supported_version, with_additions=args.with_additions).go()
