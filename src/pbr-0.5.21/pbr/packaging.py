# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
# Copyright 2012-2013 Hewlett-Packard Development Company, L.P.
# All Rights Reserved.
#
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

"""
Utilities with minimum-depends for use in setup.py
"""

import email
import os
import re
import subprocess
import sys

from distutils.command import install as du_install
import distutils.errors
from distutils import log
import pkg_resources
from setuptools.command import easy_install
from setuptools.command import egg_info
from setuptools.command import install
from setuptools.command import install_scripts
from setuptools.command import sdist

try:
    import cStringIO as io
except ImportError:
    import io

from pbr import extra_files

log.set_verbosity(log.INFO)
TRUE_VALUES = ('true', '1', 'yes')
REQUIREMENTS_FILES = ('requirements.txt', 'tools/pip-requires')
TEST_REQUIREMENTS_FILES = ('test-requirements.txt', 'tools/test-requires')
# part of the standard library starting with 2.7
# adding it to the requirements list screws distro installs
BROKEN_ON_27 = ('argparse', 'importlib')


def get_requirements_files():
    files = os.environ.get("PBR_REQUIREMENTS_FILES")
    if files:
        return tuple(f.strip() for f in files.split(','))
    return REQUIREMENTS_FILES


def append_text_list(config, key, text_list):
    """Append a \n separated list to possibly existing value."""
    new_value = []
    current_value = config.get(key, "")
    if current_value:
        new_value.append(current_value)
    new_value.extend(text_list)
    config[key] = '\n'.join(new_value)


def _parse_mailmap(mailmap_info):
    mapping = dict()
    for l in mailmap_info:
        try:
            canonical_email, alias = re.match(
                r'[^#]*?(<.+>).*(<.+>).*', l).groups()
        except AttributeError:
            continue
        mapping[alias] = canonical_email
    return mapping


def _wrap_in_quotes(values):
    return ["'%s'" % value for value in values]


def _make_links_args(links):
    return ["-f '%s'" % link for link in links]


def _pip_install(links, requires, root=None, option_dict=dict()):
    if get_boolean_option(
            option_dict, 'skip_pip_install', 'SKIP_PIP_INSTALL'):
        return
    root_cmd = ""
    if root:
        root_cmd = "--root=%s" % root
    _run_shell_command(
        "%s -m pip.__init__ install %s %s %s" % (
            sys.executable,
            root_cmd,
            " ".join(links),
            " ".join(_wrap_in_quotes(requires))),
        throw_on_error=True, buffer=False)


def read_git_mailmap(root_dir=None, mailmap='.mailmap'):
    if not root_dir:
        root_dir = _run_shell_command('git rev-parse --show-toplevel')

    mailmap = os.path.join(root_dir, mailmap)
    if os.path.exists(mailmap):
        return _parse_mailmap(open(mailmap, 'r').readlines())

    return dict()


def canonicalize_emails(changelog, mapping):
    """Takes in a string and an email alias mapping and replaces all
       instances of the aliases in the string with their real email.
    """
    for alias, email_address in mapping.items():
        changelog = changelog.replace(alias, email_address)
    return changelog


def _any_existing(file_list):
    return [f for f in file_list if os.path.exists(f)]


# Get requirements from the first file that exists
def get_reqs_from_files(requirements_files):
    for requirements_file in _any_existing(requirements_files):
        with open(requirements_file, 'r') as fil:
            return fil.read().split('\n')
    return []


def parse_requirements(requirements_files=None):

    if requirements_files is None:
        requirements_files = get_requirements_files()

    def egg_fragment(match):
        # take a versioned egg fragment and return a
        # versioned package requirement e.g.
        # nova-1.2.3 becomes nova>=1.2.3
        return re.sub(r'([\w.]+)-([\w.-]+)',
                      r'\1>=\2',
                      match.group(1))

    requirements = []
    for line in get_reqs_from_files(requirements_files):
        # Ignore comments
        if (not line.strip()) or line.startswith('#'):
            continue

        # For the requirements list, we need to inject only the portion
        # after egg= so that distutils knows the package it's looking for
        # such as:
        # -e git://github.com/openstack/nova/master#egg=nova
        # -e git://github.com/openstack/nova/master#egg=nova-1.2.3
        if re.match(r'\s*-e\s+', line):
            requirements.append(re.sub(r'\s*-e\s+.*#egg=(.*)$',
                                       egg_fragment,
                                       line))
        # such as:
        # http://github.com/openstack/nova/zipball/master#egg=nova
        # http://github.com/openstack/nova/zipball/master#egg=nova-1.2.3
        elif re.match(r'\s*https?:', line):
            requirements.append(re.sub(r'\s*https?:.*#egg=(.*)$',
                                       egg_fragment,
                                       line))
        # -f lines are for index locations, and don't get used here
        elif re.match(r'\s*-f\s+', line):
            pass
        elif line in BROKEN_ON_27 and sys.version_info >= (2, 7):
            pass
        else:
            requirements.append(line)

    return requirements


def parse_dependency_links(requirements_files=None):
    if requirements_files is None:
        requirements_files = get_requirements_files()
    dependency_links = []
    # dependency_links inject alternate locations to find packages listed
    # in requirements
    for line in get_reqs_from_files(requirements_files):
        # skip comments and blank lines
        if re.match(r'(\s*#)|(\s*$)', line):
            continue
        # lines with -e or -f need the whole line, minus the flag
        if re.match(r'\s*-[ef]\s+', line):
            dependency_links.append(re.sub(r'\s*-[ef]\s+', '', line))
        # lines that are only urls can go in unmolested
        elif re.match(r'\s*https?:', line):
            dependency_links.append(line)
    return dependency_links


def _run_shell_command(cmd, throw_on_error=False, buffer=True):
    if buffer:
        out_location = subprocess.PIPE
        err_location = subprocess.PIPE
    else:
        out_location = None
        err_location = None

    if os.name == 'nt':
        output = subprocess.Popen(["cmd.exe", "/C", cmd],
                                  stdout=out_location,
                                  stderr=err_location)
    else:
        output = subprocess.Popen(["/bin/sh", "-c", cmd],
                                  stdout=out_location,
                                  stderr=err_location)
    out = output.communicate()
    if output.returncode and throw_on_error:
        raise distutils.errors.DistutilsError(
            "%s returned %d" % (cmd, output.returncode))
    if len(out) == 0 or not out[0] or not out[0].strip():
        return ''
    return out[0].strip().decode('utf-8')


def _get_git_directory():
    return _run_shell_command("git rev-parse --git-dir", None)


def get_boolean_option(option_dict, option_name, env_name):
    return ((option_name in option_dict
             and option_dict[option_name][1].lower() in TRUE_VALUES) or
            str(os.getenv(env_name)).lower() in TRUE_VALUES)


def write_git_changelog(git_dir=None, dest_dir=os.path.curdir,
                        option_dict=dict()):
    """Write a changelog based on the git changelog."""
    should_skip = get_boolean_option(option_dict, 'skip_changelog',
                                     'SKIP_WRITE_GIT_CHANGELOG')
    if not should_skip:
        new_changelog = os.path.join(dest_dir, 'ChangeLog')
        # If there's already a ChangeLog and it's not writable, just use it
        if (os.path.exists(new_changelog)
                and not os.access(new_changelog, os.W_OK)):
            return
        log.info('[pbr] Writing ChangeLog')
        if git_dir is None:
            git_dir = _get_git_directory()
        if git_dir:
            git_log_cmd = 'git --git-dir=%s log' % git_dir
            changelog = _run_shell_command(git_log_cmd)
            mailmap = read_git_mailmap()
            with open(new_changelog, "wb") as changelog_file:
                changelog_file.write(canonicalize_emails(
                    changelog, mailmap).encode('utf-8'))


def generate_authors(git_dir=None, dest_dir='.', option_dict=dict()):
    """Create AUTHORS file using git commits."""
    should_skip = get_boolean_option(option_dict, 'skip_authors',
                                     'SKIP_GENERATE_AUTHORS')
    if not should_skip:
        old_authors = os.path.join(dest_dir, 'AUTHORS.in')
        new_authors = os.path.join(dest_dir, 'AUTHORS')
        # If there's already an AUTHORS file and it's not writable, just use it
        if (os.path.exists(new_authors)
                and not os.access(new_authors, os.W_OK)):
            return
        log.info('[pbr] Generating AUTHORS')
        ignore_emails = '(jenkins@review|infra@lists)'
        if git_dir is None:
            git_dir = _get_git_directory()
        if git_dir:
            authors = []

            # don't include jenkins email address in AUTHORS file
            git_log_cmd = ("git --git-dir=" + git_dir +
                           " log --format='%aN <%aE>'"
                           " | egrep -v '" + ignore_emails + "'")
            authors += _run_shell_command(git_log_cmd).split('\n')

            # get all co-authors from commit messages
            co_authors_cmd = ("git log --git-dir=" + git_dir +
                              " | grep -i Co-authored-by:")
            co_authors = _run_shell_command(co_authors_cmd)

            co_authors = [signed.split(":", 1)[1].strip()
                          for signed in co_authors.split('\n') if signed]

            authors += co_authors

            # canonicalize emails, remove duplicates and sort
            mailmap = read_git_mailmap(git_dir)
            authors = canonicalize_emails('\n'.join(authors), mailmap)
            authors = authors.split('\n')
            authors = sorted(set(authors))

            with open(new_authors, 'wb') as new_authors_fh:
                if os.path.exists(old_authors):
                    with open(old_authors, "rb") as old_authors_fh:
                        new_authors_fh.write(old_authors_fh.read())
                new_authors_fh.write(('\n'.join(authors) + '\n')
                                     .encode('utf-8'))


def _find_git_files(dirname='', git_dir=None):
    """Behave like a file finder entrypoint plugin.

    We don't actually use the entrypoints system for this because it runs
    at absurd times. We only want to do this when we are building an sdist.
    """
    file_list = []
    if git_dir is None:
        git_dir = _get_git_directory()
    if git_dir:
        log.info("[pbr] In git context, generating filelist from git")
        git_ls_cmd = "git --git-dir=%s ls-files -z" % git_dir
        file_list = _run_shell_command(git_ls_cmd)
        file_list = file_list.split(b'\x00'.decode('utf-8'))
    return [f for f in file_list if f]


_rst_template = """%(heading)s
%(underline)s

.. automodule:: %(module)s
  :members:
  :undoc-members:
  :show-inheritance:
"""


def _find_modules(arg, dirname, files):
    for filename in files:
        if filename.endswith('.py') and filename != '__init__.py':
            arg["%s.%s" % (dirname.replace('/', '.'),
                           filename[:-3])] = True


class LocalInstall(install.install):
    """Runs python setup.py install in a sensible manner.

    Force a non-egg installed in the manner of
    single-version-externally-managed, which allows us to install manpages
    and config files.

    Because non-egg installs bypass the depend processing machinery, we
    need to do our own. Because easy_install is evil, just use pip to
    process our requirements files directly, which means we don't have to
    do crazy extra processing.

    Bypass installation if --single-version-externally-managed is given,
    so that behavior for packagers remains the same.
    """

    command_name = 'install'

    def run(self):
        option_dict = self.distribution.get_option_dict('pbr')
        if (not self.single_version_externally_managed
                and self.distribution.install_requires):
            links = _make_links_args(self.distribution.dependency_links)
            _pip_install(
                links, self.distribution.install_requires, self.root,
                option_dict=option_dict)

        return du_install.install.run(self)


def _newer_requires_files(egg_info_dir):
    """Check to see if any of the requires files are newer than egg-info."""
    for target, sources in (('requires.txt', get_requirements_files()),
                            ('test-requires.txt', TEST_REQUIREMENTS_FILES)):
        target_path = os.path.join(egg_info_dir, target)
        for src in _any_existing(sources):
            if (not os.path.exists(target_path) or
                    os.path.getmtime(target_path)
                    < os.path.getmtime(src)):
                return True
    return False


def _copy_test_requires_to(egg_info_dir):
    """Copy the requirements file to egg-info/test-requires.txt."""
    with open(os.path.join(egg_info_dir, 'test-requires.txt'), 'w') as dest:
        for source in _any_existing(TEST_REQUIREMENTS_FILES):
            dest.write(open(source, 'r').read().rstrip('\n') + '\n')


class _PipInstallTestRequires(object):
    """Mixin class to install test-requirements.txt before running tests."""

    def install_test_requirements(self):

        links = _make_links_args(
            parse_dependency_links(TEST_REQUIREMENTS_FILES))
        if self.distribution.tests_require:
            option_dict = self.distribution.get_option_dict('pbr')
            _pip_install(
                links, self.distribution.tests_require,
                option_dict=option_dict)

    def pre_run(self):
        self.egg_name = pkg_resources.safe_name(self.distribution.get_name())
        self.egg_info = "%s.egg-info" % pkg_resources.to_filename(
            self.egg_name)
        if (not os.path.exists(self.egg_info) or
                _newer_requires_files(self.egg_info)):
            ei_cmd = self.get_finalized_command('egg_info')
            ei_cmd.run()
            self.install_test_requirements()
            _copy_test_requires_to(self.egg_info)

try:
    from pbr import testr_command

    class TestrTest(testr_command.Testr, _PipInstallTestRequires):
        """Make setup.py test do the right thing."""

        command_name = 'test'

        def run(self):
            self.pre_run()
            # Can't use super - base class old-style class
            testr_command.Testr.run(self)

    _have_testr = True

except ImportError:
    _have_testr = False


def have_testr():
    return _have_testr

try:
    from nose import commands

    class NoseTest(commands.nosetests, _PipInstallTestRequires):
        """Fallback test runner if testr is a no-go."""

        command_name = 'test'

        def run(self):
            self.pre_run()
            # Can't use super - base class old-style class
            commands.nosetests.run(self)

    _have_nose = True

except ImportError:
    _have_nose = False


def have_nose():
    return _have_nose


_script_text = """# PBR Generated from %(group)r

import sys

from %(module_name)s import %(import_target)s


if __name__ == "__main__":
    sys.exit(%(invoke_target)s())
"""


def override_get_script_args(
        dist, executable=os.path.normpath(sys.executable), is_wininst=False):
    """Override entrypoints console_script."""
    header = easy_install.get_script_header("", executable, is_wininst)
    for group in 'console_scripts', 'gui_scripts':
        for name, ep in dist.get_entry_map(group).items():
            if not ep.attrs or len(ep.attrs) > 2:
                raise ValueError("Script targets must be of the form "
                                 "'func' or 'Class.class_method'.")
            script_text = _script_text % dict(
                group=group,
                module_name=ep.module_name,
                import_target=ep.attrs[0],
                invoke_target='.'.join(ep.attrs),
            )
            yield (name, header+script_text)


class LocalInstallScripts(install_scripts.install_scripts):
    """Intercepts console scripts entry_points."""
    command_name = 'install_scripts'

    def run(self):
        if os.name != 'nt':
            get_script_args = override_get_script_args
        else:
            get_script_args = easy_install.get_script_args

        import distutils.command.install_scripts

        self.run_command("egg_info")
        if self.distribution.scripts:
            # run first to set up self.outfiles
            distutils.command.install_scripts.install_scripts.run(self)
        else:
            self.outfiles = []
        if self.no_ep:
            # don't install entry point scripts into .egg file!
            return

        ei_cmd = self.get_finalized_command("egg_info")
        dist = pkg_resources.Distribution(
            ei_cmd.egg_base,
            pkg_resources.PathMetadata(ei_cmd.egg_base, ei_cmd.egg_info),
            ei_cmd.egg_name, ei_cmd.egg_version,
        )
        bs_cmd = self.get_finalized_command('build_scripts')
        executable = getattr(
            bs_cmd, 'executable', easy_install.sys_executable)
        is_wininst = getattr(
            self.get_finalized_command("bdist_wininst"), '_is_running', False
        )
        for args in get_script_args(dist, executable, is_wininst):
            self.write_script(*args)


class LocalManifestMaker(egg_info.manifest_maker):
    """Add any files that are in git and some standard sensible files."""

    def _add_pbr_defaults(self):
        for template_line in [
            'include AUTHORS',
            'include ChangeLog',
            'exclude .gitignore',
            'exclude .gitreview',
            'global-exclude *.pyc'
        ]:
            self.filelist.process_template_line(template_line)

    def add_defaults(self):
        option_dict = self.distribution.get_option_dict('pbr')

        sdist.sdist.add_defaults(self)
        self.filelist.append(self.template)
        self.filelist.append(self.manifest)
        self.filelist.extend(extra_files.get_extra_files())
        should_skip = get_boolean_option(option_dict, 'skip_git_sdist',
                                         'SKIP_GIT_SDIST')
        if not should_skip:
            rcfiles = _find_git_files()
            if rcfiles:
                self.filelist.extend(rcfiles)
        elif os.path.exists(self.manifest):
            self.read_manifest()
        ei_cmd = self.get_finalized_command('egg_info')
        self._add_pbr_defaults()
        self.filelist.include_pattern("*", prefix=ei_cmd.egg_info)


class LocalEggInfo(egg_info.egg_info):
    """Override the egg_info command to regenerate SOURCES.txt sensibly."""

    command_name = 'egg_info'

    def find_sources(self):
        """Generate SOURCES.txt only if there isn't one already.

        If we are in an sdist command, then we always want to update
        SOURCES.txt. If we are not in an sdist command, then it doesn't
        matter one flip, and is actually destructive.
        """
        manifest_filename = os.path.join(self.egg_info, "SOURCES.txt")
        if not os.path.exists(manifest_filename) or 'sdist' in sys.argv:
            log.info("[pbr] Processing SOURCES.txt")
            mm = LocalManifestMaker(self.distribution)
            mm.manifest = manifest_filename
            mm.run()
            self.filelist = mm.filelist
        else:
            log.info("[pbr] Reusing existing SOURCES.txt")
            self.filelist = egg_info.FileList()
            for entry in open(manifest_filename, 'r').read().split('\n'):
                self.filelist.append(entry)


class LocalSDist(sdist.sdist):
    """Builds the ChangeLog and Authors files from VC first."""

    command_name = 'sdist'

    def run(self):
        option_dict = self.distribution.get_option_dict('pbr')
        write_git_changelog(option_dict=option_dict)
        generate_authors(option_dict=option_dict)
        # sdist.sdist is an old style class, can't use super()
        sdist.sdist.run(self)

try:
    from sphinx import apidoc
    from sphinx import application
    from sphinx import config
    from sphinx import setup_command

    class LocalBuildDoc(setup_command.BuildDoc):

        command_name = 'build_sphinx'
        builders = ['html', 'man']

        def _get_source_dir(self):
            option_dict = self.distribution.get_option_dict('build_sphinx')
            if 'source_dir' in option_dict:
                source_dir = os.path.join(option_dict['source_dir'][1], 'api')
            else:
                source_dir = 'doc/source/api'
            if not os.path.exists(source_dir):
                os.makedirs(source_dir)
            return source_dir

        def generate_autoindex(self):
            log.info("[pbr] Autodocumenting from %s"
                     % os.path.abspath(os.curdir))
            modules = {}
            source_dir = self._get_source_dir()
            for pkg in self.distribution.packages:
                if '.' not in pkg:
                    for dirpath, dirnames, files in os.walk(pkg):
                        _find_modules(modules, dirpath, files)
            module_list = list(modules.keys())
            module_list.sort()
            autoindex_filename = os.path.join(source_dir, 'autoindex.rst')
            with open(autoindex_filename, 'w') as autoindex:
                autoindex.write(""".. toctree::
    :maxdepth: 1

    """)
                for module in module_list:
                    output_filename = os.path.join(source_dir,
                                                   "%s.rst" % module)
                    heading = "The :mod:`%s` Module" % module
                    underline = "=" * len(heading)
                    values = dict(module=module, heading=heading,
                                  underline=underline)

                    log.info("[pbr] Generating %s"
                             % output_filename)
                    with open(output_filename, 'w') as output_file:
                        output_file.write(_rst_template % values)
                    autoindex.write("   %s.rst\n" % module)

        def _sphinx_tree(self):
                source_dir = self._get_source_dir()
                apidoc.main(['apidoc', '.', '-H', 'Modules', '-o', source_dir])

        def _sphinx_run(self):
            if not self.verbose:
                status_stream = io.StringIO()
            else:
                status_stream = sys.stdout
            confoverrides = {}
            if self.version:
                confoverrides['version'] = self.version
            if self.release:
                confoverrides['release'] = self.release
            if self.today:
                confoverrides['today'] = self.today
            sphinx_config = config.Config(self.config_dir, 'conf.py', {}, [])
            if self.builder == 'man' and len(sphinx_config.man_pages) == 0:
                return
            app = application.Sphinx(
                self.source_dir, self.config_dir,
                self.builder_target_dir, self.doctree_dir,
                self.builder, confoverrides, status_stream,
                freshenv=self.fresh_env, warningiserror=True)

            try:
                app.build(force_all=self.all_files)
            except Exception as err:
                from docutils import utils
                if isinstance(err, utils.SystemMessage):
                    sys.stder.write('reST markup error:\n')
                    sys.stderr.write(err.args[0].encode('ascii',
                                                        'backslashreplace'))
                    sys.stderr.write('\n')
                else:
                    raise

            if self.link_index:
                src = app.config.master_doc + app.builder.out_suffix
                dst = app.builder.get_outfilename('index')
                os.symlink(src, dst)

        def run(self):
            option_dict = self.distribution.get_option_dict('pbr')
            tree_index = get_boolean_option(option_dict,
                                            'autodoc_tree_index_modules',
                                            'AUTODOC_TREE_INDEX_MODULES')
            auto_index = get_boolean_option(option_dict,
                                            'autodoc_index_modules',
                                            'AUTODOC_INDEX_MODULES')
            if not os.getenv('SPHINX_DEBUG'):
                #NOTE(afazekas): These options can be used together,
                # but they do a very similar thing in a difffernet way
                if tree_index:
                    self._sphinx_tree()
                if auto_index:
                    self.generate_autoindex()

            for builder in self.builders:
                self.builder = builder
                self.finalize_options()
                self.project = self.distribution.get_name()
                self.version = self.distribution.get_version()
                self.release = self.distribution.get_version()
                if 'warnerrors' in option_dict:
                    self._sphinx_run()
                else:
                    setup_command.BuildDoc.run(self)

    class LocalBuildLatex(LocalBuildDoc):
        builders = ['latex']
        command_name = 'build_sphinx_latex'

    _have_sphinx = True

except ImportError:
    _have_sphinx = False


def have_sphinx():
    return _have_sphinx


def _get_revno(git_dir):
    """Return the number of commits since the most recent tag.

    We use git-describe to find this out, but if there are no
    tags then we fall back to counting commits since the beginning
    of time.
    """
    describe = _run_shell_command(
        "git --git-dir=%s describe --always" % git_dir)
    if "-" in describe:
        return describe.rsplit("-", 2)[-2]

    # no tags found
    revlist = _run_shell_command(
        "git --git-dir=%s rev-list --abbrev-commit HEAD" % git_dir)
    return len(revlist.splitlines())


def _get_version_from_git(pre_version):
    """Return a version which is equal to the tag that's on the current
    revision if there is one, or tag plus number of additional revisions
    if the current revision has no tag.
    """

    git_dir = _get_git_directory()
    if git_dir:
        if pre_version:
            try:
                return _run_shell_command(
                    "git --git-dir=" + git_dir + " describe --exact-match",
                    throw_on_error=True).replace('-', '.')
            except Exception:
                sha = _run_shell_command(
                    "git --git-dir=" + git_dir + " log -n1 --pretty=format:%h")
                return "%s.a%s.g%s" % (pre_version, _get_revno(git_dir), sha)
        else:
            return _run_shell_command(
                "git --git-dir=" + git_dir + " describe --always").replace(
                    '-', '.')
    return None


def _get_version_from_pkg_info(package_name):
    """Get the version from PKG-INFO file if we can."""
    try:
        pkg_info_file = open('PKG-INFO', 'r')
    except (IOError, OSError):
        return None
    try:
        pkg_info = email.message_from_file(pkg_info_file)
    except email.MessageError:
        return None
    # Check to make sure we're in our own dir
    if pkg_info.get('Name', None) != package_name:
        return None
    return pkg_info.get('Version', None)


def get_version(package_name, pre_version=None):
    """Get the version of the project. First, try getting it from PKG-INFO, if
    it exists. If it does, that means we're in a distribution tarball or that
    install has happened. Otherwise, if there is no PKG-INFO file, pull the
    version from git.

    We do not support setup.py version sanity in git archive tarballs, nor do
    we support packagers directly sucking our git repo into theirs. We expect
    that a source tarball be made from our git repo - or that if someone wants
    to make a source tarball from a fork of our repo with additional tags in it
    that they understand and desire the results of doing that.
    """
    version = os.environ.get(
        "PBR_VERSION",
        os.environ.get("OSLO_PACKAGE_VERSION", None))
    if version:
        return version
    version = _get_version_from_pkg_info(package_name)
    if version:
        return version
    version = _get_version_from_git(pre_version)
    if version:
        return version
    raise Exception("Versioning for this project requires either an sdist"
                    " tarball, or access to an upstream git repository.")
