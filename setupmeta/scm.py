from distutils.version import LooseVersion
import re

import setupmeta


def strip_dash(text):
    """ Strip leading dashes from 'text' """
    if not text:
        return text
    return text.strip('-')


class Version:

    text = None         # type: str
    version = None      # type: LooseVersion

    major = 0           # type: int # Major part of version
    minor = 0           # type: int # Minor part of version
    patch = 0           # type: int # Patch part of version
    changes = 0         # type: int # Number of changes since last tag
    commitid = None     # type: str # Commit id
    dirty = False       # type: bool # Local changes are present

    def __init__(
            self,
            main=None,
            changes=0,
            commitid=None,
            dirty=False,
            text=None
    ):
        self.changes = changes or 0
        self.commitid = (commitid or 'initial').strip()
        self.dirty = dirty
        main = (main or '0.0.0').strip()
        self.text = text or "v%s-%s-%s" % (main, self.changes, self.commitid)
        self.version = LooseVersion(main)
        triplet = self.bump_triplet()
        self.major = triplet[0]
        self.minor = triplet[1]
        self.patch = triplet[2]

    def __repr__(self):
        return self.text

    def bump_triplet(self):
        """
        :return int, int, int: Major, minor, patch
        """
        version = list(self.version.version)
        major = version and version.pop(0) or 0
        minor = version and version.pop(0) or 0
        patch = version and version.pop(0) or 0
        return major, minor, patch

    def to_dict(self, parts=None):
        result = {}
        for key in dir(self):
            if key.startswith('_'):
                continue
            value = getattr(self, key)
            if value is None or callable(value):
                continue
            if not parts or key in parts:
                result[key] = value
            else:
                result[key] = ''
        return result

    @property
    def alpha(self):
        if self.changes:
            return 'a%s' % self.changes
        return ''

    @property
    def beta(self):
        if self.changes:
            return 'b%s' % self.changes
        return ''

    @property
    def devmarker(self):
        if self.dirty:
            return '.%s' % self.commitid
        return ''


class Scm:

    def __init__(self):
        self.root = setupmeta.project_path()

    def get_branch(self):
        pass

    def get_version(self):
        pass

    def commit_files(self, commit, relative_paths, next_version):
        pass

    def apply_tag(self, commit, branch, next_version):
        pass


class Hg(Scm):

    def get_branch(self):
        setupmeta.abort("get_branch() not implemented for hg")

    def get_version(self):
        setupmeta.abort("get_version() not implemented for hg")

    def commit_files(self, commit, relative_paths, next_version):
        setupmeta.abort("commit_files() not implemented for hg")

    def apply_tag(self, commit, branch, next_version):
        setupmeta.abort("apply_tag() not implemented for hg")


class Git(Scm):

    # Output expected from git describe
    re_describe = re.compile(
        r'^v?(.+?)(-\d+)?(-g\w+)?$',
        re.IGNORECASE
    )

    def get_branch(self):
        branch = self.get_git_output(
            'rev-parse',
            '--abbrev-ref',
            'HEAD'
        )
        return branch and branch.strip()

    def is_dirty(self):
        exitcode = self.get_git_output(
            'diff',
            '--quiet',
            '--ignore-submodules',
            capture=False
        )
        return exitcode != 0

    def get_version(self):
        main = None
        changes = None
        commitid = None
        dirty = self.is_dirty()
        text = self.get_git_output(
            'describe',
            '--tags',
            '--long',
            '--match', 'v*.*'
        )
        if text:
            m = self.re_describe.match(text)
            if m:
                main = m.group(1)
                changes = strip_dash(m.group(2))
                changes = setupmeta.to_int(changes, default=0)
                commitid = strip_dash(m.group(3))

        if not text or not main:
            dirty = True
            commitid = self.get_git_output('rev-parse', '--short', 'HEAD')
            commitid = 'g%s' % commitid if commitid else ''
            changes = self.get_git_output('rev-list', 'HEAD')
            changes = changes.count('\n') + 1 if changes else 0

        return Version(main, changes, commitid, dirty, text)

    def commit_files(self, commit, relative_paths, next_version):
        if not relative_paths:
            return
        self.run_git(commit, 'add', *relative_paths)
        self.run_git(commit, 'commit', '-m', "Version %s" % next_version)

    def apply_tag(self, commit, branch, next_version):
        bump_msg = "Version %s" % next_version
        tag = "v%s" % next_version
        self.run_git(commit, 'tag', '-a', tag, '-m', bump_msg)
        self.run_git(commit, 'push', '--tags', 'origin', branch)

    def get_git_output(self, *args, **kwargs):
        capture = kwargs.pop('capture', True)
        return setupmeta.run_program(
            'git',
            *args,
            capture=capture,
            cwd=self.root,
            **kwargs
        )

    def run_git(self, commit, *args):
        return self.get_git_output(
            *args,
            capture=None,
            fatal=True,
            dryrun=not commit
        )
