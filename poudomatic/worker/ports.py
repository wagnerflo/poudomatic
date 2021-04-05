from contextlib import asynccontextmanager
from dataclasses import dataclass,field,InitVar
from git import Repo
from re import compile as regex

from ..common import head
from .util import zfs,git

BRANCH_RE = regex(r"^(2\d{3})Q([1-4])(?:@(\d+))?$")

@dataclass(frozen=True)
class BranchVersion:
    branch: InitVar[str]
    year: str = field(init=False)
    quarter: str = field(init=False)
    snap: int = field(init=False)

    def __post_init__(self, branch):
        if (match := BRANCH_RE.match(branch)) is not None:
            snap = match.group(3)
            object.__setattr__(self, "year",    int(match.group(1)))
            object.__setattr__(self, "quarter", int(match.group(2)))
            object.__setattr__(self, "snap",    None if snap is None else int(snap))
        else:
            raise Exception()

    @property
    def shortname(self):
        return f"{self.year}Q{self.quarter}"

    @property
    def fullname(self):
        if self.snap:
            return f"{self.shortname}@{self.snap}"
        else:
            return self.shortname

class Ports:
    PROP_TIMESTAMP = "poudomatic:timestamp"
    PROP_GITSHA    = "poudomatic:gitsha"

    FSPROPS = zfs.COMPRESSION + zfs.NOATIME
    GIT_URL = "https://git-dev.freebsd.org/ports.git"

    def __init__(self, env, snap):
        _,_,ver = snap.name.rpartition("/")
        self.env = env
        self.snap = snap
        self.ver = BranchVersion(ver)

    @asynccontextmanager
    async def install(self):
        async with zfs.temp_clone(self.snap) as dset:
            name = self.ver.shortname
            await self.env.poudriere.remember_ports(
                name,
                dset.mountpoint,
                zfs.get_property(dset, self.PROP_TIMESTAMP),

            )
            try:
                yield name
            finally:
                await self.env.poudriere.forget_ports(name)

    @classmethod
    async def get(cls, env, branch):
        ver = BranchVersion(branch)
        name = f"{env.dset_ports.name}/{ver.fullname}"

        if ver.snap:
            if (snap := await zfs.get_snapshot(name)) is None:
                return
        else:
            dset = await zfs.get_dataset(name)
            if dset is None:
                return
            snap = head(
                await zfs.sorted_snapshots(
                    dset, key=lambda s: int(s.snapshot_name), reverse=True
                )
            )
            if snap is None:
                return

        return cls(env, snap)

    @classmethod
    async def create(cls, env, branch):
        ver = BranchVersion(branch)

        # see if we can find a ports tree of exactly that version
        if (ports := await cls.get(env, branch)) is not None:
            return ports

        # fresh installation
        async with zfs.temp_dataset(env.dset_ports, cls.FSPROPS) as dset:
            prefix,_,name = dset.name.rpartition("/")
            repo = await git.clone_from(
                cls.GIT_URL, dset.mountpoint,
                depth=1, single_branch=True, branch=branch,
            )
            head = repo.head.commit

            await zfs.set_properties(dset, {
                cls.PROP_GITSHA:    head.hexsha,
                cls.PROP_TIMESTAMP: head.committed_date,
            })
            repo.close()

            name = f"{prefix}/{ver.shortname}"
            snap = await zfs.create_snapshot(dset, "0")
            await zfs.rename_dataset(dset, name)
            snap = await zfs.get_snapshot(f"{name}@0")

        return cls(env, snap)
