#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from __future__ import unicode_literals

<<<<<<< HEAD

UNSCOPED_TOKEN = {
    'token': {
        'methods': [
            'password'
        ],
        'catalog': {},
        'expires_at': '2010-11-01T03:32:15-05:00',
        'user': {
            'domain': {
                'id': '4e6893b7ba0b4006840c3845660b86ed',
                'name': 'exampledomain'
            },
            'id': 'c4da488862bd435c9e6c0275a0d0e49a',
            'name': 'exampleuser',
        }
    }
}

DOMAIN_SCOPED_TOKEN = {
    'token': {
        'methods': [
            'password'
        ],
        'catalog': [{
            'endpoints': [{
                'url':
                'http://public.com:8776/v1/None',
                'region': 'RegionOne',
                'interface': 'public'
            }, {
                'url':
                'http://internal:8776/v1/None',
                'region': 'RegionOne',
                'interface': 'internal'
            }, {
                'url':
                'http://admin:8776/v1/None',
                'region': 'RegionOne',
                'interface': 'admin'
            }],
            'type': 'volume'
        }, {
            'endpoints': [{
                'url': 'http://public.com:9292/v1',
                'region': 'RegionOne',
                'interface': 'public'
            }, {
                'url': 'http://internal:9292/v1',
                'region': 'RegionOne',
                'interface': 'internal'
            }, {
                'url': 'http://admin:9292/v1',
                'region': 'RegionOne',
                'interface': 'admin'
            }],
            'type': 'image'
        }, {
            'endpoints': [{
                'url':
                'http://public.com:8774/v1.1/None',
                'region': 'RegionOne',
                'interface': 'public'
            }, {
                'url':
                'http://internal:8774/v1.1/None',
                'region': 'RegionOne',
                'interface': 'internal'
            }, {
                'url':
                'http://admin:8774/v1.1/None',
                'region': 'RegionOne',
                'interface': 'admin'
            }],
            'type': 'compute'
        }, {
            'endpoints': [{
                'url': 'http://public.com:8773/services/Cloud',
                'region': 'RegionOne',
                'interface': 'public'
            }, {
                'url': 'http://internal:8773/services/Cloud',
                'region': 'RegionOne',
                'interface': 'internal'
            }, {
                'url': 'http://admin:8773/services/Admin',
                'region': 'RegionOne',
                'interface': 'admin'
            }],
            'type': 'ec2'
        }, {
            'endpoints': [{
                'url': 'http://public.com:5000/v3',
                'region': 'RegionOne',
                'interface': 'public'
            }, {
                'url': 'http://internal:5000/v3',
                'region': 'RegionOne',
                'interface': 'internal'
            }, {
                'url': 'http://admin:35357/v3',
                'region': 'RegionOne',
                'interface': 'admin'
            }],
            'type': 'identity'
        }],
        'expires_at': '2010-11-01T03:32:15-05:00',
        'user': {
            'domain': {
                'id': '4e6893b7ba0b4006840c3845660b86ed',
                'name': 'exampledomain'
            },
            'id': 'c4da488862bd435c9e6c0275a0d0e49a',
            'name': 'exampleuser',
        },
        'roles': [
            {
                "id": "76e72a",
                "links": {
                    "self": "http://identity:35357/v3/roles/76e72a"
                },
                "name": "admin"
            },
            {
                "id": "f4f392",
                "links": {
                    "self": "http://identity:35357/v3/roles/f4f392"
                },
                "name": "member"
            }
        ],
        'domain': {
            'id': '8e9283b7ba0b1038840c3842058b86ab',
            'name': 'anotherdomain'
        },
    }
}

PROJECT_SCOPED_TOKEN = {
    'token': {
        'methods': [
            'password'
        ],
        'catalog': [{
            'endpoints': [{
                'url':
                'http://public.com:8776/v1/225da22d3ce34b15877ea70b2a575f58',
                'region': 'RegionOne',
                'interface': 'public'
            }, {
                'url':
                'http://internal:8776/v1/225da22d3ce34b15877ea70b2a575f58',
                'region': 'RegionOne',
                'interface': 'internal'
            }, {
                'url':
                'http://admin:8776/v1/225da22d3ce34b15877ea70b2a575f58',
                'region': 'RegionOne',
                'interface': 'admin'
            }],
            'type': 'volume'
        }, {
            'endpoints': [{
                'url': 'http://public.com:9292/v1',
                'region': 'RegionOne',
                'interface': 'public'
            }, {
                'url': 'http://internal:9292/v1',
                'region': 'RegionOne',
                'interface': 'internal'
            }, {
                'url': 'http://admin:9292/v1',
                'region': 'RegionOne',
                'interface': 'admin'
            }],
            'type': 'image'
        }, {
            'endpoints': [{
                'url':
                'http://public.com:8774/v2/225da22d3ce34b15877ea70b2a575f58',
                'region': 'RegionOne',
                'interface': 'public'
            }, {
                'url':
                'http://internal:8774/v2/225da22d3ce34b15877ea70b2a575f58',
                'region': 'RegionOne',
                'interface': 'internal'
            }, {
                'url':
                'http://admin:8774/v2/225da22d3ce34b15877ea70b2a575f58',
                'region': 'RegionOne',
                'interface': 'admin'
            }],
            'type': 'compute'
        }, {
            'endpoints': [{
                'url': 'http://public.com:8773/services/Cloud',
                'region': 'RegionOne',
                'interface': 'public'
            }, {
                'url': 'http://internal:8773/services/Cloud',
                'region': 'RegionOne',
                'interface': 'internal'
            }, {
                'url': 'http://admin:8773/services/Admin',
                'region': 'RegionOne',
                'interface': 'admin'
            }],
            'type': 'ec2'
        }, {
            'endpoints': [{
                'url': 'http://public.com:5000/v3',
                'region': 'RegionOne',
                'interface': 'public'
            }, {
                'url': 'http://internal:5000/v3',
                'region': 'RegionOne',
                'interface': 'internal'
            }, {
                'url': 'http://admin:35357/v3',
                'region': 'RegionOne',
                'interface': 'admin'
            }],
            'type': 'identity'
        }],
        'expires_at': '2010-11-01T03:32:15-05:00',
        'user': {
            'domain': {
                'id': '4e6893b7ba0b4006840c3845660b86ed',
                'name': 'exampledomain'
            },
            'id': 'c4da488862bd435c9e6c0275a0d0e49a',
            'name': 'exampleuser',
        },
        'roles': [
            {
                "id": "76e72a",
                "links": {
                    "self": "http://identity:35357/v3/roles/76e72a"
                },
                "name": "admin"
            },
            {
                "id": "f4f392",
                "links": {
                    "self": "http://identity:35357/v3/roles/f4f392"
                },
                "name": "member"
            }
        ],
        'project': {
            'domain': {
                'id': '4e6893b7ba0b4006840c3845660b86ed',
                'name': 'exampledomain'
            },
            'id': '225da22d3ce34b15877ea70b2a575f58',
            'name': 'exampleproject',
        },
    }
}
=======
from keystoneclient import fixture


def unscoped_token():
    return fixture.V3Token(user_id='c4da488862bd435c9e6c0275a0d0e49a',
                           user_name='exampleuser',
                           user_domain_id='4e6893b7ba0b4006840c3845660b86ed',
                           user_domain_name='exampledomain',
                           expires='2010-11-01T03:32:15-05:00')


def domain_scoped_token():
    f = fixture.V3Token(user_id='c4da488862bd435c9e6c0275a0d0e49a',
                        user_name='exampleuser',
                        user_domain_id='4e6893b7ba0b4006840c3845660b86ed',
                        user_domain_name='exampledomain',
                        expires='2010-11-01T03:32:15-05:00',
                        domain_id='8e9283b7ba0b1038840c3842058b86ab',
                        domain_name='anotherdomain')

    f.add_role(id='76e72a', name='admin')
    f.add_role(id='f4f392', name='member')
    region = 'RegionOne'

    s = f.add_service('volume')
    s.add_standard_endpoints(public='http://public.com:8776/v1/None',
                             internal='http://internal.com:8776/v1/None',
                             admin='http://admin.com:8776/v1/None',
                             region=region)

    s = f.add_service('image')
    s.add_standard_endpoints(public='http://public.com:9292/v1',
                             internal='http://internal:9292/v1',
                             admin='http://admin:9292/v1',
                             region=region)

    s = f.add_service('compute')
    s.add_standard_endpoints(public='http://public.com:8774/v1.1/None',
                             internal='http://internal:8774/v1.1/None',
                             admin='http://admin:8774/v1.1/None',
                             region=region)

    s = f.add_service('ec2')
    s.add_standard_endpoints(public='http://public.com:8773/services/Cloud',
                             internal='http://internal:8773/services/Cloud',
                             admin='http://admin:8773/services/Admin',
                             region=region)

    s = f.add_service('identity')
    s.add_standard_endpoints(public='http://public.com:5000/v3',
                             internal='http://internal:5000/v3',
                             admin='http://admin:35357/v3',
                             region=region)

    return f


def project_scoped_token():
    f = fixture.V3Token(user_id='c4da488862bd435c9e6c0275a0d0e49a',
                        user_name='exampleuser',
                        user_domain_id='4e6893b7ba0b4006840c3845660b86ed',
                        user_domain_name='exampledomain',
                        expires='2010-11-01T03:32:15-05:00',
                        project_id='225da22d3ce34b15877ea70b2a575f58',
                        project_name='exampleproject',
                        project_domain_id='4e6893b7ba0b4006840c3845660b86ed',
                        project_domain_name='exampledomain')

    f.add_role(id='76e72a', name='admin')
    f.add_role(id='f4f392', name='member')

    region = 'RegionOne'
    tenant = '225da22d3ce34b15877ea70b2a575f58'

    s = f.add_service('volume')
    s.add_standard_endpoints(public='http://public.com:8776/v1/%s' % tenant,
                             internal='http://internal:8776/v1/%s' % tenant,
                             admin='http://admin:8776/v1/%s' % tenant,
                             region=region)

    s = f.add_service('image')
    s.add_standard_endpoints(public='http://public.com:9292/v1',
                             internal='http://internal:9292/v1',
                             admin='http://admin:9292/v1',
                             region=region)

    s = f.add_service('compute')
    s.add_standard_endpoints(public='http://public.com:8774/v2/%s' % tenant,
                             internal='http://internal:8774/v2/%s' % tenant,
                             admin='http://admin:8774/v2/%s' % tenant,
                             region=region)

    s = f.add_service('ec2')
    s.add_standard_endpoints(public='http://public.com:8773/services/Cloud',
                             internal='http://internal:8773/services/Cloud',
                             admin='http://admin:8773/services/Admin',
                             region=region)

    s = f.add_service('identity')
    s.add_standard_endpoints(public='http://public.com:5000/v3',
                             internal='http://internal:5000/v3',
                             admin='http://admin:35357/v3',
                             region=region)

    return f

>>>>>>> 77d63f4a7a5aeaf331e82ab5c713c86b5ddbee15

AUTH_SUBJECT_TOKEN = '3e2813b7ba0b4006840c3825860b86ed'

AUTH_RESPONSE_HEADERS = {
    'X-Subject-Token': AUTH_SUBJECT_TOKEN
}

<<<<<<< HEAD
AUTH_RESPONSE_BODY = {
    'token': {
        'methods': [
            'password'
        ],
        'expires_at': '2010-11-01T03:32:15-05:00',
        'project': {
            'domain': {
                'id': '123',
                'name': 'aDomain'
            },
            'id': '345',
            'name': 'aTenant'
        },
        'user': {
            'domain': {
                'id': '1',
                'name': 'aDomain'
            },
            'id': '567',
            'name': 'test',
            'roles': [
                {
                    "id": "76e72a",
                    "links": {
                        "self": "http://identity:35357/v3/roles/76e72a"
                    },
                    "name": "admin"
                },
                {
                    "id": "f4f392",
                    "links": {
                        "self": "http://identity:35357/v3/roles/f4f392"
                    },
                    "name": "member"
                }
            ],
        },
        'issued_at': '2010-10-31T03:32:15-05:00',
        'catalog': [{
            'endpoints': [{
                'url': 'https://compute.north.host/novapi/public',
                'region': 'North',
                'interface': 'public'
            }, {
                'url': 'https://compute.north.host/novapi/internal',
                'region': 'North',
                'interface': 'internal'
            }, {
                'url': 'https://compute.north.host/novapi/admin',
                'region': 'North',
                'interface': 'admin'
            }],
            'type': 'compute',
            'name': 'nova',
        }, {
            'endpoints': [{
                'url': 'http://swift.north.host/swiftapi/public',
                'region': 'South',
                'interface': 'public'
            }, {
                'url': 'http://swift.north.host/swiftapi/internal',
                'region': 'South',
                'interface': 'internal'
            }, {
                'url': 'http://swift.north.host/swiftapi/admin',
                'region': 'South',
                'interface': 'admin'
            }],
            'type': 'object-store',
            'name': 'swift',
        }, {
            'endpoints': [{
                'url': 'http://glance.north.host/glanceapi/public',
                'region': 'North',
                'interface': 'public'
            }, {
                'url': 'http://glance.north.host/glanceapi/internal',
                'region': 'North',
                'interface': 'internal'
            }, {
                'url': 'http://glance.north.host/glanceapi/admin',
                'region': 'North',
                'interface': 'admin'
            }, {
                'url': 'http://glance.south.host/glanceapi/public',
                'region': 'South',
                'interface': 'public'
            }, {
                'url': 'http://glance.south.host/glanceapi/internal',
                'region': 'South',
                'interface': 'internal'
            }, {
                'url': 'http://glance.south.host/glanceapi/admin',
                'region': 'South',
                'interface': 'admin'
            }],
            'type': 'image',
            'name': 'glance',
        }]
    }
}

TRUST_TOKEN = {
    'token': {
        'methods': [
            'password'
        ],
        'catalog': {},
        'expires_at': '2010-11-01T03:32:15-05:00',
        "OS-TRUST:trust": {
            "id": "fe0aef",
            "impersonation": False,
            "links": {
                "self": "http://identity:35357/v3/trusts/fe0aef"
            },
            "trustee_user": {
                "id": "0ca8f6",
                "links": {
                    "self": "http://identity:35357/v3/users/0ca8f6"
                }
            },
            "trustor_user": {
                "id": "bd263c",
                "links": {
                    "self": "http://identity:35357/v3/users/bd263c"
                }
            }
        },
        'user': {
            'domain': {
                'id': '4e6893b7ba0b4006840c3845660b86ed',
                'name': 'exampledomain'
            },
            'id': '0ca8f6',
            'name': 'exampleuser',
        }
    }
}
=======

def auth_response_body():
    f = fixture.V3Token(user_id='567',
                        user_name='test',
                        user_domain_id='1',
                        user_domain_name='aDomain',
                        expires='2010-11-01T03:32:15-05:00',
                        project_domain_id='123',
                        project_domain_name='aDomain',
                        project_id='345',
                        project_name='aTenant')

    f.add_role(id='76e72a', name='admin')
    f.add_role(id='f4f392', name='member')

    s = f.add_service('compute', name='nova')
    s.add_standard_endpoints(
        public='https://compute.north.host/novapi/public',
        internal='https://compute.north.host/novapi/internal',
        admin='https://compute.north.host/novapi/admin',
        region='North')

    s = f.add_service('object-store', name='swift')
    s.add_standard_endpoints(
        public='http://swift.north.host/swiftapi/public',
        internal='http://swift.north.host/swiftapi/internal',
        admin='http://swift.north.host/swiftapi/admin',
        region='South')

    s = f.add_service('image', name='glance')
    s.add_standard_endpoints(
        public='http://glance.north.host/glanceapi/public',
        internal='http://glance.north.host/glanceapi/internal',
        admin='http://glance.north.host/glanceapi/admin',
        region='North')

    s.add_standard_endpoints(
        public='http://glance.south.host/glanceapi/public',
        internal='http://glance.south.host/glanceapi/internal',
        admin='http://glance.south.host/glanceapi/admin',
        region='South')

    return f


def trust_token():
    return fixture.V3Token(user_id='0ca8f6',
                           user_name='exampleuser',
                           user_domain_id='4e6893b7ba0b4006840c3845660b86ed',
                           user_domain_name='exampledomain',
                           expires='2010-11-01T03:32:15-05:00',
                           trust_id='fe0aef',
                           trust_impersonation=False,
                           trustee_user_id='0ca8f6',
                           trustor_user_id='bd263c')
>>>>>>> 77d63f4a7a5aeaf331e82ab5c713c86b5ddbee15
