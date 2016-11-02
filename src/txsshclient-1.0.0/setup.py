
import os
import re
from setuptools import setup, find_packages


# Utility function to read the README file.
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


def get_version(filename):
    pattern = re.compile(r"^__version__ = ['\"]([^'\"]*)['\"]")

    for line in open(filename).readlines():
        match = pattern.search(line)
        if match:
            return match.group(1)
    raise Exception('Unable to find version string in %s.' % filename)


requires = [
    'twisted',
    'pyasn1',
    'PyCrypto'
]

setup(
    name='txsshclient',
    packages=find_packages(),

    version=get_version("sshclient/__init__.py"),
    description="Twisted python asynchronous library for issueing commands and receiving or sending files over ssh.",
    long_description=read('README'),

    # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Other Environment',
        'Framework :: Twisted',
        'Intended Audience :: Developers',
        'License :: Other/Proprietary License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],

    keywords="twisted ssh",
    author='Zenoss, Inc.',
    author_email='support@zenoss.com',
    url='http://github.com/zenoss/txsshclient',
    license='All Rights Reserved',
    requires=requires,
    setup_requires=requires,
    install_requires=requires,
)

