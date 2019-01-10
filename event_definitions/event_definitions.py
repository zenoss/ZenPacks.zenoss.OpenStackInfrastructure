# Parses various versions of the ceilometer event_definitions.yaml file into
# a form that can be easily queried and compared.

import yaml
from urllib2 import urlopen
from fnmatch import fnmatch
from decorator import decorator
import os.path


@decorator
def memoize(f, *args, **kwargs):
    sig = repr((args, kwargs))
    cache = f._m_cache = getattr(f, '_m_cache', {})
    if sig not in cache:
        cache[sig] = f(*args, **kwargs)
    return cache[sig]


class EventDefinitions(object):
    definitions = None
    url = None

    def __init__(self, url=None, with_additions=False):
        if url:
            self.url = url

        if self.url is None:
            raise ValueError("Event Definitions URL Not Set")

        if with_additions:
            with open(os.path.dirname(__file__) + "/zenoss_additions.yaml") as za:
                self.load_definitions(urlopen(self.url).read() + za.read())
        else:
            self.load_definitions(urlopen(self.url).read())

    def load_definitions(self, definitions_yaml):
        defs = yaml.safe_load(definitions_yaml)

        # A single block in the yaml file can contain multiple event_type patterns.
        # It's easier for us to work with if we flatten that out, so go ahead
        # and make a more convenient structure:
        # [
        #    (single_event_type_pattern, { traitname => [ fields ] }), ...
        # ]
        # this is kept in the order of the original definition file.

        self.definitions = []
        for d in defs:
            if not isinstance(d['event_type'], list):
                d['event_type'] = [d['event_type']]

            for event_type_pattern in d['event_type']:
                traits = {}

                for traitname, trait in d['traits'].iteritems():
                    if not isinstance(trait['fields'], list):
                        trait['fields'] = [trait['fields']]

                    traits[traitname] = trait['fields']

                self.definitions.append(
                    (event_type_pattern, traits)
                )

        # the definitions in the file are to be processed in reverse order, with
        # the first matching one being used.  (yaml merge syntax is used in the
        # file to explicitly include earlier blocks)
        self.definitions.reverse()

    @memoize
    def get_traits(self, event_type):
        for definition in self.definitions:
            event_type_pattern, traits = definition

            if fnmatch(event_type, event_type_pattern):
                return traits

    def has_trait(self, event_type, trait_name):
        return trait_name in self.get_traits(event_type)

    @memoize
    def trait_fields(self, event_type, trait_name):
        if self.has_trait(event_type, trait_name):
            return self.get_traits(event_type)[trait_name]
        else:
            return []


def get_event_definitions(version, with_additions=True):
    version_urls = {
        'legacy': 'https://raw.githubusercontent.com/zenoss/ceilometer_zenoss/1.2.0/ceilometer_zenoss/event_definitions.yaml',
        'newton': 'https://raw.githubusercontent.com/openstack/ceilometer/newton-eol/etc/ceilometer/event_definitions.yaml',
        'ocata': 'https://raw.githubusercontent.com/openstack/ceilometer/stable/ocata/etc/ceilometer/event_definitions.yaml',
        'pike': 'https://raw.githubusercontent.com/openstack/ceilometer/9.0.6/ceilometer/pipeline/data/event_definitions.yaml',
        'queens': 'https://raw.githubusercontent.com/openstack/ceilometer/10.0.1/ceilometer/pipeline/data/event_definitions.yaml',
        'rocky': 'https://raw.githubusercontent.com/openstack/ceilometer/11.0.1/ceilometer/pipeline/data/event_definitions.yaml',
    }

    if version == 'legacy':
        return EventDefinitions(url=version_urls.get(version), with_additions=False)
    else:
        return EventDefinitions(url=version_urls.get(version), with_additions=with_additions)
