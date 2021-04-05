from contextlib import asynccontextmanager
from dataclasses import dataclass,field,InitVar
from re import compile as regex, VERBOSE
from shlex import quote as shquote

from ..common import tempnames
from .util import zfs,process

VERSION_RE = regex(
    r"""
    ^
    (?P<release>[1-9]\d*\.[0-4])
    -
    (?:
        (?:(?P<pre>BETA|RC)(?P<level>[1-9]\d*))
        |
        (?:(?P<rel>RELEASE)(?:-p(?P<patch>[1-9]\d*))?)
    )
    $
    """,
    VERBOSE
)

TYPE_MAP = {
    "RELEASE": "p",
    "BETA":    "b",
    "RC":      "c",

}

@dataclass(frozen=True)
class JailVersion:
    version: InitVar[str]
    release: str = field(init=False)
    type: str = field(init=False)
    level: str = field(init=False)

    def __post_init__(self, version):
        if (match := VERSION_RE.match(version)) is not None:
            object.__setattr__(self, "release", match.group('release'))
            if match.group('pre'):
                object.__setattr__(self, "type",  match.group('pre'))
                object.__setattr__(self, "level", match.group('level'))
            else:
                object.__setattr__(self, "type",  match.group('rel'))
                object.__setattr__(self, "level", match.group('patch'))
        else:
            raise Exception()

    @property
    def shortname(self):
        return (
            f"{self.release.replace('.', '')}"
            f"{TYPE_MAP[self.type]}"
            f"{0 if self.level is None else self.level}"
        )

class JailExec:
    def __init__(self, jailname):
        self.cmd = ("/usr/sbin/jexec", "-U", "root", shquote(jailname))

    def __call__(self, *args):
        return process(*self.cmd + args)

class Jail:
    FSPROPS = zfs.COMPRESSION + zfs.NOATIME

    def __init__(self, env, dataset):
        self.env = env
        self.dset = dataset

    @asynccontextmanager
    async def start(self, portsname):
        _,_,jailname = self.dset.name.rpartition("/")
        mastername = next(tempnames)
        await (
            await (
                self.env.poudriere.api() << (
                    f"export SET_STATUS_ON_START=0",
                    f"export MUTABLE_BASE=yes",
                    f"export MASTERNAME={shquote(mastername)}",
                    f"_mastermnt MASTERMNT",
                    f"export MASTERMNT",
                    f"jail_start {shquote(jailname)} {shquote(portsname)}",
                )
                >> self.env.runtime.log
            )
        )
        try:
            yield JailExec(mastername)
        finally:
            await (
                await (
                    self.env.poudriere.api() << (
                        f"export MASTERNAME={shquote(mastername)}",
                        f"_mastermnt MASTERMNT",
                        f"export MASTERMNT",
                        f"jail_stop",
                    )
                    >> self.env.runtime.log
                )
            )

    @classmethod
    async def get(cls, env, version):
        ver = JailVersion(version)
        name = f"{env.dset_jails.name}/{ver.shortname}"
        if (dset := await zfs.get_dataset(name)) is not None:
            return cls(env, dset)

    @classmethod
    async def _upgrade_dset(cls, env, dset):
        raise NotImplementedError()

    @classmethod
    async def create(cls, env, version):
        ver = JailVersion(version)

        # see if we can find a jail of exactly that version
        if (jail := await cls.get(env, version)) is not None:
            return jail

        # fresh installation
        async with zfs.temp_dataset(env.dset_jails, cls.FSPROPS) as dset:
            prefix,_,name = dset.name.rpartition("/")

            # install jail and update to latest patch
            await (
                await (
                    env.poudriere(
                        "jail", "-c", "-j", name, "-v", version,
                        "-f", "none", "-m", "http",
                    )
                    >> env.runtime.log
                )
            )

            if ver.type == "RELEASE":
                await cls._upgrade_dset(env, dset)

            # get the actually installed version
            ver = JailVersion(
                await env.poudriere.jget(name, "version")
            )

            # rename dataset and update mountpoint
            newname = ver.shortname
            dset = await zfs.rename_dataset(dset, f"{prefix}/{newname}")
            await env.poudriere.jset(name, mnt=dset.mountpoint, method="null")
            await env.poudriere.rename_jail_conf(name, newname)

        return cls(env, dset)
