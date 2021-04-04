from contextlib import contextmanager
from logging import getLogger
from re import compile as regex, MULTILINE

from .util import zfs,git
from .versions import *

NEWVERS_PATH = "sys/conf/newvers.sh"
NEWVERS_RE = regex(rb'^BRANCH="(?P<branch>.*)"', MULTILINE)

log = getLogger("src")

class SourceTree:
    @classmethod
    def newvers_branch(cls, commit):
        data = commit.tree[NEWVERS_PATH].data_stream.read()
        if (match := NEWVERS_RE.search(data)) is not None:
            return match.group(1).decode("ascii")

    @classmethod
    def make_tags(cls, dset, repo):
        try:
            snap = zfs.sorted_snapshots(dset).pop()
            stop_at = FreeBSDBranch.parse_str(snap.snapshot_name).long
        except IndexError:
            stop_at = "CURRENT"

        mapping = {}

        for commit in repo.iter_commits(paths=NEWVERS_PATH):
            branch = cls.newvers_branch(commit)

            if not branch or branch == cls.newvers_branch(commit.parents[0]):
                continue

            if branch == stop_at:
                break

            try:
                name = FreeBSDBranch.parse_str(branch).short
            except TypeError:
                continue
            else:
                mapping[name] = commit.hexsha

        if mapping:
            for name,hexsha in reversed(mapping.items()):
                repo.git.checkout(hexsha)
                snap = zfs.create_snapshot(dset, name)

            repo.git.checkout("HEAD")

    @classmethod
    def create_or_update(cls, env, ver):
        name = f"{env.dset_src.name}/{ver.shortrelease}"

        if (dset := zfs.get_dataset(name)) is not None:
            with git.open(dset.mountpoint) as repo:
                repo.remotes.origin.pull()
                cls.make_tags(dset, repo)

        else:
            with zfs.temp_dataset(env.dset_src) as dset:
                branch = f"releng/{ver.release}"
                log.info(f"Cloning FreeBSD src branch {branch}.")
                with git.clone_from(
                        "https://git.freebsd.org/src.git",
                        dset.mountpoint, branch=branch,
                        single_branch=True) as repo:
                    cls.make_tags(dset, repo)
                zfs.rename_dataset(dset, name)

        return name

    @classmethod
    @contextmanager
    def activate(cls, env, ver):
        name = SourceTree.create_or_update(env, ver)

        if (snap := zfs.get_snapshot(f"{name}@{ver.shortbranch}")) is None:
            raise Exception("")

        with zfs.temp_clone(snap) as dset:
            yield dset
