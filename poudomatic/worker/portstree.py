from contextlib import asynccontextmanager
from dataclasses import dataclass,field,InitVar
from pathlib import Path
from re import compile as regex
from tempfile import mkdtemp

from ..common import head,asyncinit,unblocked
from .util import zfs,git

PROP_TIMESTAMP = "poudomatic:timestamp"
PROP_GITSHA    = "poudomatic:gitsha"

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

class ActivePortsTree:
    @asyncinit
    async def new(self, env, ver, snap):
        self.env = env
        self.ver = ver
        self.name = ver.shortname
        self.dset = await asyncinit.push_del(zfs.temp_clone(snap))

        self.path = Path(self.dset.mountpoint)
        self.workdir = Path(await unblocked(mkdtemp, dir=self.path))

        await asyncinit.push_del(
            env.poudriere.activate_ports(
                self.name, self.path,
                zfs.get_property(self.dset, PROP_TIMESTAMP)
            )
        )

class PortsTree:
    FSPROPS = zfs.COMPRESSION + zfs.NOATIME
    GIT_URL = "https://git-dev.freebsd.org/ports.git"

    def __init__(self, env, snap):
        _,_,ver = snap.name.rpartition("/")
        self.env = env
        self.snap = snap
        self.ver = BranchVersion(ver)

    def activate(self):
        return ActivePortsTree.new(self.env, self.ver, self.snap)

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

            async with git.clone_from(
                    cls.GIT_URL, dset.mountpoint,
                    depth=1, single_branch=True, branch=branch) as repo:
                head = repo.head.commit
                await zfs.set_properties(dset, {
                    PROP_GITSHA:    head.hexsha,
                    PROP_TIMESTAMP: head.committed_date,
                })

            name = f"{prefix}/{ver.shortname}"
            snap = await zfs.create_snapshot(dset, "0")
            await zfs.rename_dataset(dset, name)
            snap = await zfs.get_snapshot(f"{name}@0")

        return cls(env, snap)
