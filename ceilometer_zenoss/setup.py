##############################################################################
#
# Copyright (C) Zenoss, Inc. 2014, all rights reserved.
#
# This content is made available according to terms specified in
# License.zenoss under the directory where your Zenoss product is installed.
#
##############################################################################

import os
from setuptools import setup, find_packages


# Utility function to read the README file.
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

requires = [
    'ceilometer',
    'kombu',
    'eventlet'
]


setup(
    name='ceilometer_zenoss',
    packages=find_packages(),
    entry_points={
        'ceilometer.dispatcher': 'zenoss = ceilometer_zenoss.dispatcher.zenoss:ZenossDispatcher'
    },

    version='2.0.0dev',
    description="Ceilometer dispatcher plugin to ship data to Zenoss.",
    long_description=read('README.rst'),

    # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Environment :: OpenStack',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: Other/Proprietary License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2',
        'Topic :: System :: Monitoring',
        'Natural Language :: English',
    ],

    keywords="openstack ceilometer zenoss",
    author='Zenoss, Inc.',
    author_email='support@zenoss.com',
    url='http://github.com/zenoss/ZenPacks.zenoss.OpenStackInfrastructure',
    license=read('LICENSE'),

    requires=requires,
    install_requires=requires,
    zip_safe=False
)
