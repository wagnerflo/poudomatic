from dataclasses import dataclass,field,InitVar
from re import compile as regex, VERBOSE

from ..zfs import (
    get_dataset,
    temp_dataset,
    rename_dataset,
    COMPRESSION,
    NOATIME,
)

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

class Jail:
    FSPROPS = dict(**COMPRESSION, **NOATIME)

    def __init__(self, dataset):
        self.dset = dataset

    @classmethod
    async def get(cls, env, version):
        ver = JailVersion(version)
        name = f"{env.dset_jails.name}/{ver.shortname}"
        if (dset := await get_dataset(name)) is not None:
            return cls(dset)

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
        async with temp_dataset(env.dset_jails, cls.FSPROPS) as dset:
            prefix,_,name = dset.name.rpartition("/")

            # install jail and update to latest patch
            await (
                await (
                    env.poudriere(
                        "jail", "-c", "-f", "none", "-j", name, "-v", version,
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
            dset = await rename_dataset(dset, f"{prefix}/{newname}")
            await env.poudriere.jset(name, "mnt", dset.mountpoint)
            await env.poudriere.rename_jail_conf(name, newname)

        return cls(dset)
