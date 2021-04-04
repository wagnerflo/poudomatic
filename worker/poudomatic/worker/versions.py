from pydantic import BaseModel
from re import compile as regex, VERBOSE

_FreeBSDBranch_RE = regex(
    r"""
    ^
    (?:
        (?:
            (?P<short_pre>[abc])
            (?P<short_pre_ver>[1-9]\d*)
        )?
        p
        (?P<short_lvl>\d+)
    )
    |
    (?:
        (?:
            RELEASE
            |
            (?:
                (?P<long_pre>ALPHA|BETA|RC)
                (?P<long_pre_ver>[1-9]\d*)
            )
        )
        (?:-p(?P<long_lvl>[1-9]\d*))?
    )
    $
    """,
    VERBOSE
)

_FreeBSDBranch_TYPE_MAP = {
    "ALPHA":   "a",
    "BETA":    "b",
    "RC":      "c",
    "RELEASE": "",
}

_FreeBSDBranch_TYPE_MAP_REV = {
    v: k for k,v in _FreeBSDBranch_TYPE_MAP.items()
}

class FreeBSDBranch(BaseModel):
    class Config:
        allow_mutation = False

    type: str
    ver: str
    lvl: int

    @classmethod
    def __get_validators__(cls):
        yield cls.parse_str

    @classmethod
    def parse_str(cls, val):
        if not isinstance(val, str):
            raise TypeError("string required")

        if (match := _FreeBSDBranch_RE.match(val)) is None:
            raise TypeError(f"Invalid FreeBSD branch specification '{val}'.")

        groups = match.groupdict()

        if lvl := groups.get("short_lvl"):
            lvl = int(lvl)
            if type := groups.get("short_pre"):
                type = _FreeBSDBranch_TYPE_MAP_REV[type]
                ver = groups.get("short_pre_ver")
            else:
                ver = ""
        else:
            lvl = int(groups.get("long_lvl") or "0")
            if type := groups.get("long_pre"):
                ver = groups.get("long_pre_ver")
            else:
                ver = ""
        if not ver:
            type = "RELEASE"

        return cls(type=type, ver=ver, lvl=lvl)

    @property
    def short(self):
        return f"{_FreeBSDBranch_TYPE_MAP[self.type]}{self.ver}p{self.lvl}"

    @property
    def lvlprefix(self):
        return f"-p{self.lvl}" if self.lvl else ""

    @property
    def long(self):
        return f"{self.type}{self.ver}{self.lvlprefix}"


_FreeBSDVersion_RE = regex(
    r"""
    ^
    (?:
        (?:(?P<release>[1-9]\d*\.[0-4])-)
        |
        (?:(?P<major>[1-9]\d*)(?P<minor>[0-4]))
    )
    (?P<branch>.*)
    $
    """,
    VERBOSE
)

class FreeBSDVersion(BaseModel):
    class Config:
        allow_mutation = False

    release: str
    branch: FreeBSDBranch

    @classmethod
    def __get_validators__(cls):
        yield cls.parse_str

    @classmethod
    def parse_str(cls, val):
        if not isinstance(val, str):
            raise TypeError("string required")

        if (match := _FreeBSDVersion_RE.match(val)) is None:
            raise TypeError(f"Invalid FreeBSD version specification '{val}'.")

        if (release := match.group("release")) is None:
            release = f"{match.group('major')}.{match.group('minor')}"

        return cls(release=release, branch=match.group("branch"))

    @property
    def shortrelease(self):
        return self.release.replace(".", "")

    @property
    def shortbranch(self):
        return self.branch.short

    @property
    def shortname(self):
        return f"{self.shortrelease}{self.shortbranch}"

    @property
    def longbranch(self):
        return self.branch.long

    @property
    def longname(self):
        return f"{self.release}-{self.longbranch}"


_PortsBranchVersion_RE = regex(r"^(2\d{3})Q([1-4])$")

class PortsBranchVersion(BaseModel):
    class Config:
        allow_mutation = False

    year: int
    quarter: int

    @classmethod
    def __get_validators__(cls):
        yield cls.parse_str

    @classmethod
    def parse_str(cls, val):
        if not isinstance(val, str):
            raise TypeError("string required")

        if (match := _PortsBranchVersion_RE.match(val)) is None:
            raise Exception(f"Invalid ports tree branch specification '{val}'.")

        year,quarter = match.groups()

        return cls(year=year, quarter=quarter)

    @property
    def name(self):
        return f"{self.year}Q{self.quarter}"


__all__ = (
    'FreeBSDBranch',
    'FreeBSDVersion',
    'PortsBranchVersion',
)
