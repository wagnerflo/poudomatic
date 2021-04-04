from contextlib import asynccontextmanager
from dataclasses import dataclass,field,InitVar
from git import Repo
from re import compile as regex

from ..util import first
from ..agit import (
    clone_from,
)
from ..zfs import (
    get_dataset,
    get_snapshot,
    create_snapshot,
    sorted_snapshots,
    temp_dataset,
    temp_clone,
    set_properties,
    rename_dataset,
    COMPRESSION,
    NOATIME,
)
from .properties import (
    POUDOMATIC_GITSHA,
    POUDOMATIC_TIMESTAMP,
)

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
    FSPROPS = dict(**COMPRESSION, **NOATIME)
    GIT_URL = "https://git-dev.freebsd.org/ports.git"

    def __init__(self, env, snap):
        _,_,ver = snap.name.rpartition("/")
        self.env = env
        self.snap = snap
        self.ver = BranchVersion(ver)

    @asynccontextmanager
    async def install(self):
        async with temp_clone(self.snap) as dset:
            name = self.ver.shortname
            await self.env.poudriere.remember_ports(name, dset)
            try:
                yield name
            finally:
                await self.env.poudriere.forget_ports(name)

    @classmethod
    async def get(cls, env, branch):
        ver = BranchVersion(branch)
        name = f"{env.dset_ports.name}/{ver.fullname}"

        if ver.snap:
            if (snap := await get_snapshot(name)) is None:
                return
        else:
            dset = await get_dataset(name)
            if dset is None:
                return
            snap = first(
                await sorted_snapshots(
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
        async with temp_dataset(env.dset_ports, cls.FSPROPS) as dset:
            prefix,_,name = dset.name.rpartition("/")
            repo = await clone_from(
                cls.GIT_URL, dset.mountpoint,
                depth=1, single_branch=True, branch=branch,
            )
            head = repo.head.commit

            await set_properties(dset, {
                POUDOMATIC_GITSHA:    head.hexsha,
                POUDOMATIC_TIMESTAMP: head.committed_date,
            })
            repo.close()

            name = f"{prefix}/{ver.shortname}"
            snap = await create_snapshot(dset, "0")
            await rename_dataset(dset, name)
            snap = await get_snapshot(f"{name}@0")

        return cls(env, snap)
