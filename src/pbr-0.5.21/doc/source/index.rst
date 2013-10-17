===================================
 pbr - Python Build Reasonableness
===================================

A library for managing setuptools packaging needs in a consistent manner.

`pbr` reads and then filters the `setup.cfg` data through a setup hook to
fill in default values and provide more sensible behaviors, and then feeds
the results in as the arguments to a call to `setup.py` - so the heavy
lifting of handling python packaging needs is still being done by
`setuptools`.

What It Does
============

PBR can and does do a bunch of things for you:

 * **Version**: Manage version number based on git revisions and tags
 * **AUTHORS**: Generate AUTHORS file from git log
 * **ChangeLog**: Generate ChangeLog from git log
 * **Sphinx Autodoc**: Generate autodoc stub files for your whole module
 * **Requirements**: Store your dependencies in a pip requirements file
 * **long_description**: Use your README file as a long_description
 * **Smart find_packages**: Smartly find packages under your root package

Version
-------

Version strings will be inferred from git. If a given revision is tagged,
that's the version. If it's not, and you don't provide a version, the version
will be very similar to git describe. If you do, then we'll assume that's the
version you are working towards, and will generate alpha version strings
based on commits since last tag and the current git sha.

AUTHORS and ChangeLog
---------------------

Why keep an AUTHORS or a ChangeLog file, when git already has all of the
information you need. AUTHORS generation supports filtering/combining based
on a standard .mailmap file.

Sphinx Autodoc
--------------

Sphinx can produce auto documentation indexes based on signatures and
docstrings of your project- but you have to give it index files to tell it
to autodoc each module. That's kind of repetitive and boring. PBR will
scan your project, find all of your modules, and generate all of the stub
files for you.

Sphinx documentation setups are altered to generate man pages by default. They
also have several pieces of information that are known to setup.py injected
into the sphinx config.

Requirements
------------

You may not have noticed, but there are differences in how pip
requirements.txt files work and how distutils wants to be told about
requirements. The pip way is nicer, because it sure does make it easier to
popuplate a virtualenv for testing, or to just install everything you need.
Duplicating the information, though, is super lame. So PBR will let you
keep requirements.txt format files around describing the requirements for
your project, will parse them and split them up approprirately, and inject
them into the install_requires and/or tests_require and/or dependency_links
arguments to setup. Voila!

long_description
----------------

There is no need to maintain two long descriptions- and your README file is
probably a good long_description. So we'll just inject the contents of your
README.rst, README.txt or README file into your empty long_description. Yay
for you.

Usage
=====
pbr requires a distribution to use distribute.  Your distribution
must include a distutils2-like setup.cfg file, and a minimal setup.py script.

A simple sample can be found in pbr s own setup.cfg
(it uses its own machinery to install itself)::

 [metadata]
 name = pbr
 author = OpenStack Foundation
 author-email = openstack-dev@lists.openstack.org
 summary = OpenStack's setup automation in a reuable form
 description-file = README
 license = Apache-2
 classifier =
     Development Status :: 4 - Beta
         Environment :: Console
         Environment :: OpenStack
         Intended Audience :: Developers
         Intended Audience :: Information Technology
         License :: OSI Approved :: Apache Software License
         Operating System :: OS Independent
         Programming Language :: Python
 keywords =
     setup
     distutils
 [files]
 packages =
     pbr
 data_files =
     etc/pbr = etc/*
     etc/init =
         pbr.packaging.conf
         pbr.version.conf
 [entry_points]
 console_scripts =
     pbr = pbr.cmd:main
 pbr.config.drivers =
     plain = pbr.cfg.driver:Plain

The minimal setup.py should look something like this::

 #!/usr/bin/env python

 from setuptools import setup

 setup(
     setup_requires=['pbr'],
     pbr=True,
 )

Note that it's important to specify `pbr=True` or else the pbr functionality
will not be enabled.

It should also work fine if additional arguments are passed to `setup()`,
but it should be noted that they will be clobbered by any options in the
setup.cfg file.

files
-----

The format of the files section is worth explaining. There are three
fundamental keys one is likely to care about, `packages`,
`namespace_packages`, and `data_files`.

`packages` is a list of top-level packages that should be installed. The
behavior of packages is similar to `setuptools.find_packages` in that it
recurses the python package heirarchy below the given top level and installs
all of it. If `packages` is not specified, it defaults to the name given
in the `[metadata]` section.

`namespace_packages` is the same, but is a list of packages that provide
namespace packages.

`data_files` lists files to be installed. The format is an indented block
that contains key value pairs which specify target directory and source
file to install there. More than one source file for a directory may be
indicated with a further indented list. Source files are stripped of leading
directories. Additionally, `pbr` supports a simple file globbing syntax
for installing entire directory structures, so::

 [files]
 data_files =
     etc/pbr = etc/pbr/*
     etc/neutron =
         etc/api-paste.ini
         etc/dhcp-agent.ini
     etc/init.d = neutron.init

Will result in `/etc/neutron` containing `api-paste.ini` and `dhcp-agent.ini`,
both of which pbr will expect to find in the `etc` directory in the root of
the source tree. Additionally, `neutron.init` from that dir will be installed
in `/etc/init.d`.

All of the files and directories located under `etc/pbr` in the source tree
will be installed into `/etc/pbr`.

entry_points
------------

The general syntax of specifying entry points is a top level name indicating
the entry point group name, followed by one or more key value pairs naming
the entry point to be installed. For instance::

 [entry_points]
 console_scripts =
     pbr = pbr.cmd:main
 pbr.config.drivers =
     plain = pbr.cfg.driver:Plain
     fancy = pbr.cfg.driver:Fancy

Will cause a console script called `pbr` to be installed that executes the
`main` function found in `pbr.cmd`. Additionally, two entry points will be
installed for `pbr.config.drivers`, one called `plain` which maps to the
`Plain` class in `pbr.cfg.driver` and one called `fancy` which maps to the
`Fancy` class in `pbr.cfg.driver`.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
