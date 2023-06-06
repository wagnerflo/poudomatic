import anyio
import codecs
import os
import pathlib
import re
import select
import sys
import threading

KQ_FILTER_USER      = -11          # EVFILT_USER
KQ_NOTE_FFNOP       = 0x00000000   # NOTE_FFNOP
KQ_NOTE_TRIGGER     = 0x01000000   # NOTE_TRIGGER

RE_LINEBREAK = re.compile(br"\r\n|\n|\r")

class Future:
    def __init__(self):
        self._evt = anyio.Event()
        self._result = None

    async def result(self):
        await self._evt.wait()
        return self._result

    def set(self, result):
        self._result = result
        self._evt.set()

class DirectoryFollower:
    def __init__(self, path):
        self._path = pathlib.Path(path).resolve()
        self._pathfd = os.open(self._path, os.O_DIRECT)

        self._kq = select.kqueue()
        self._kqfd = self._kq.fileno()
        self._files = {}
        self._fds = {}

        self._closed = False
        self._modify_lock = threading.Lock()
        self._decoder = codecs.getdecoder(sys.getdefaultencoding())

        with self._modify_lock:
            self._add_user(self._kqfd)
            self._set_events(
                select.kevent(
                    self._pathfd,
                    select.KQ_FILTER_VNODE,
                    select.KQ_EV_ADD | select.KQ_EV_CLEAR,
                    select.KQ_NOTE_WRITE
                )
            )

    def __del__(self):
        os.close(self._pathfd)

    def __bool__(self):
        return not self._closed or bool(self._fds)

    def _decode(self, b):
        return self._decoder(b)[0]

    def _set_events(self, *evts):
        self._kq.control(evts, 0, 0)

    def _add_user(self, fd):
        self._set_events(
            select.kevent(
                fd,
                KQ_FILTER_USER,
                select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
                KQ_NOTE_FFNOP
            )
        )

    def _trigger_user(self, fd):
        self._set_events(
            select.kevent(
                fd,
                KQ_FILTER_USER,
                select.KQ_EV_ENABLE,
                KQ_NOTE_TRIGGER
            )
        )

    def close(self):
        self._trigger_user(self._kqfd)

    def remove(self, filename):
        if fd := self._files.get(filename):
            self._trigger_user(fd)

    def wait(self, timeout=None):
        to_close = set()
        to_add = set()

        for kev in self._kq.control(None, len(self._fds) * 2 + 2, timeout):
            fd = kev.ident

            if kev.filter == KQ_FILTER_USER:
                if fd == self._kqfd:
                    self._closed = True
                else:
                    to_close.add(fd)

            elif kev.filter == select.KQ_FILTER_VNODE and fd == self._pathfd:
                for entry in os.scandir(fd):
                    if entry.is_file(follow_symlinks=False):
                        path = (self._path / entry.name).resolve()
                        if path not in self._files:
                            to_add.add(path)

            elif kev.filter == select.KQ_FILTER_READ:
                fp,filename,buf = self._fds[fd]
                *lines,last = RE_LINEBREAK.split(fp.read())
                if lines:
                    yield (filename, self._decode(buf + lines.pop(0)))
                    buf.clear()
                if last:
                    buf.extend(last)
                for line in lines:
                    yield (filename, self._decode(line))

        if not to_close and not to_add:
            return

        with self._modify_lock:
            for fd in to_close:
                fp,filename,_ = self._fds[fd]
                fp.close()
                del self._files[filename]
                del self._fds[fd]

            events = []

            for filename in to_add:
                fp = filename.open(mode="rb", buffering=0)
                fd = fp.fileno()
                self._files[filename] = fd
                self._fds[fd] = (fp, filename, bytearray())
                events.extend([
                    select.kevent(
                        fd,
                        KQ_FILTER_USER,
                        select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
                        KQ_NOTE_FFNOP
                    ),
                    select.kevent(
                        fd,
                        select.KQ_FILTER_READ,
                        select.KQ_EV_ADD | select.KQ_EV_CLEAR,
                        0
                    ),
                ])

            self._set_events(*events)

    def __iter__(self):
        while self:
            for evt in self.wait():
                yield evt

class Watcher:
    ATTRIB = select.KQ_NOTE_ATTRIB
    WRITE  = select.KQ_NOTE_WRITE

    def __init__(self):
        self.kq = select.kqueue()
        self.kqfd = self.kq.fileno()
        self.fds = set()
        self.to_close = set()
        self.fut = None

    def __del__(self):
        for fd in self.to_close:
            os.close(fd)

    def add(self, fp, fflags):
        if isinstance(fp, str):
            fd = os.open(fp, os.O_RDONLY)
            self.to_close.add(fd)
        elif callable(getattr(fp, "fileno", None)):
            fd = fp.fileno()
        else:
            fd = fp

        if fd in self.fds:
            raise Exception()

        self.kq.control(
            [ select.kevent(
                fd,
                select.KQ_FILTER_VNODE,
                select.KQ_EV_ADD | select.KQ_EV_CLEAR,
                fflags) ],
            0, 0
        )
        self.fds.add(fd)
        return fd

    def wait(self, timeout=None):
        return [
            (kev.ident, kev.fflags)
            for kev in self.kq.control(None, len(self.fds), timeout)
        ]

    async def async_wait(self):
        if self.fut is not None:
            return await self.fut.result()
        else:
            self.fut = Future()
            await anyio.wait_socket_readable(self.kqfd)
            res = self.wait(timeout=0)
            self.fut.set(res)
            self.fut = None
            return res

__all__ = (
    "DirectoryFollower",
    "Watcher",
)
