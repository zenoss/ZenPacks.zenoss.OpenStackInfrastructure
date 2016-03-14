##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################
"""
Utilities for DNS, domains, dominant domains, and hostname filtering
"""

from collections import Counter
import re

import logging
log = logging.getLogger('OSI.lib.domains')


def validate_fqdn(dn):
    if dn.endswith('.'):
        dn = dn[:-1]
    if len(dn) < 1 or len(dn) > 253:
        return False
    ldh_re = re.compile('^[a-z\d]([a-z\d-]{0,61}[a-z\d])?$', re.IGNORECASE)
    return all(ldh_re.match(x) for x in dn.split('.'))


def extract_valid_hostname(host):
    '''Return valid IP, else hostname, else ''
       Do this by splitting each part on dot, then comparing to valid pattern.
       Once each part is valid, re-add it into string.
    '''
    if not host or host.startswith('.'):
        return

    host = host.lower()

    ldh_re = re.compile('^'
                        '(?P<crud>[^a-z\d]*)'                       # crud
                        '(?P<good>[a-z\d]([a-z\d-]{0,61}[a-z\d])?)' # good part
                        '\.?'                                       # ending '.'
                        '(?P<bad>[^a-z\d\-]*)'                      # illegal
                        '.*'                                        # all else
                        '$',
                        re.IGNORECASE)
    good_parts = []
    # Split each domain component and check: if each part good, recombine
    # Else, short-circuit and give the largest possible valide host.
    for part in host.split('.'):
        part_search = ldh_re.search(part)
        if part_search:
            if part_search.group('crud'):
                return '.'.join(good_parts)
            if part_search.group('good'):
                good_parts.append(part_search.group('good'))
            if part_search.group('bad'):
                return '.'.join(good_parts)

    newhost = '.'.join(good_parts)
    if host != newhost:
        log.debug('Hostname %s extracted to %s', host, newhost)

    return newhost


def extract_domainname(host):
    '''Return valid IP, else hostname, else ''
       Do this by splitting each part on dot, then comparing to valid pattern.
       Once each part is valid, re-add it into string.
    '''
    hostname = extract_valid_hostname(host)
    if not hostname:
        return

    domain_RX = re.compile(
                         '^'
                         '(?P<hostname>[a-z\d]+[a-z\d\-]*)' # Hostname part
                         '\.'
                         '(?P<domain>[\w\-\.]*?\w)'     # Don't be greedy
                         '(\.localhost|\.localdomain)*' # Remove localhost etc
                         '\.?'                          # Optional trailing dot
                         '$',
                         re.I
                         )

    domain_search = domain_RX.search(hostname)
    if domain_search:
        return domain_search.group('domain')


def get_domains(hostnames):
    domains = set()

    for host in hostnames:
        d = extract_domainname(host)
        if d:
            domains.add(d)

    return domains


def get_dominant_domain(hostnames):

    if not hostnames:
        log.debug('get_dominant_domain: No hostnames available')
        return

    hostnames = [h for h in hostnames if re.search('[a-zA-Z]', h)]

    # Safety: Convert all to lowercase in set
    hostnames = set(h.lower() for h in hostnames)
    domains = get_domains(hostnames)

    def getKey(item):
        return item[0]

    dc = Counter()
    for d in domains:
        dc.update(d.lower() for n in hostnames if d.lower() in n.lower())

    dc_max = [x for x in dc.items() if x[1] == dc.most_common()[0][1]]
    dc_sorted = [a for a in sorted(dc_max, key=getKey)]

    if not dc_sorted:
        log.debug('No domain names found from hosts: %s', hostnames)
        return

    dominant_domain = dc_sorted[0][0]

    if '.' not in dominant_domain:
        log.debug('Domain ({}) has single domain component'.format(dominant_domain))

    return dominant_domain


def main():

    hostnames = set()
    hostnames.add('Zrap.example.com')
    hostnames.add('other.example.com')
    hostnames.add('angstrom.example.com')
    hostnames.add('this.example.com')
    hostnames.add('other.Example.com.localhost')
    hostnames.add('other.Junk.com')
    hostnames.add('other.junk.com.localdomain')
    hostnames.add('next.junk.com.localdomain')
    hostnames.add('xxx.Crud.com')
    hostnames.add('xxx.crud.com')
    domain = get_dominant_domain(hostnames)

    print domain

if __name__ == '__main__':

    main()
#
