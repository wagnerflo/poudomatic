from itertools import chain
from libzfs import (
    DatasetType as ZFSDatasetType,
    Error as ZFSErrorCode,
    ZFS,
    ZFSUserProperty,
    ZFSException,
)
from ...common import (
    unblocked,
    unblockedcontextmanager,
    tempnames,
)

_zfs = ZFS()

@unblocked
def get_dataset(name):
    try:
        return _zfs.get_dataset(name)
    except ZFSException as exc:
        if exc.code != ZFSErrorCode.NOENT:
            raise

@unblocked
def create_dataset(name, fsprops=None, mount=True):
    pool,_,_ = name.partition("/")
    pool = _zfs.get(pool)
    pool.create(name, fsprops or {})
    dset = _zfs.get_dataset(name)
    if mount:
        dset.mount()
    return dset

@unblocked
def rename_dataset(dset, newname):
    dset.rename(newname)
    return _zfs.get_dataset(newname)

@unblocked
def set_properties(dset, props):
    for key,value in props.items():
        dset.properties[key] = ZFSUserProperty(str(value))

def get_property(dset, prop):
    if (prop := dset.properties.get(prop)) is not None:
        return prop.value

def is_filesystem(dset):
    return dset.type == ZFSDatasetType.FILESYSTEM

@unblocked
def get_snapshot(name):
    try:
        return _zfs.get_snapshot(name)
    except ZFSException as exc:
        if exc.code != ZFSErrorCode.NOENT:
            raise

@unblocked
def create_snapshot(dset, name):
    name = f"{dset.name}@{name}"
    dset.snapshot(name)
    return _zfs.get_snapshot(name)

@unblocked
def sorted_snapshots(dset, key=None, reverse=False):
    if key is None:
        key = lambda s: s.snapshot_name
    return sorted(dset.snapshots, key=key, reverse=reverse)

@unblocked
def create_clone(snap, name, fsprops=None, mount=True):
    snap.clone(name, fsprops or {})
    dset = _zfs.get_dataset(name)
    if mount:
        dset.mount()
    return dset

def _destroy_dataset(dset):
    for dep in dset.dependents:
        if is_filesystem(dep) and dep.mountpoint:
            dep.umount(True)
        dep.delete()
    dset.umount(True)
    dset.delete()

@unblockedcontextmanager
def temp_dataset(root, fsprops=None, mount=True):
    fsprops = fsprops or {}
    pool,_,_ = root.name.partition("/")
    pool = _zfs.get(pool)
    for name in tempnames:
        try:
            name = f"{root.name}/{name}"
            pool.create(name, fsprops)
            break
        except ZFSException as exc:
            if exc.code == ZFSErrorCode.EXISTS:
                continue
    dset = _zfs.get_dataset(name)
    if mount:
        dset.mount()
    try:
        yield dset
    finally:
        try:
            _destroy_dataset(dset)
        except ZFSException as exc:
            if exc.code != ZFSErrorCode.NOENT:
                raise

@unblockedcontextmanager
def temp_clone(snap, fsprops=None, mount=True):
    fsprops = fsprops or {}
    prefix = snap.parent.name

    for name in tempnames:
        try:
            name = f"{prefix}/{name}"
            snap.clone(name, fsprops)
            break
        except ZFSException as exc:
            if exc.code == ZFSErrorCode.EXISTS:
                continue

    dset = _zfs.get_dataset(name)
    if mount:
        dset.mount()

    try:
        yield dset
    finally:
        try:
            _destroy_dataset(dset)
        except ZFSException as exc:
            if exc.code != ZFSErrorCode.NOENT:
                raise

class props(dict):
    def __add__(self, other):
        return self.__class__(chain(self.items(), other.items()))

COMPRESSION   = props( compression = "zstd" )
NOCOMPRESSION = props( compression = "off"  )
NOATIME       = props( atime       = "off"  )
