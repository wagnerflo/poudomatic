from inspect import isgenerator
from shlex import quote
from signal import SIGINT
from subprocess import (
    Popen,
    DEVNULL,
    PIPE,
    STDOUT,
)
from sys import getdefaultencoding
from threading import Thread

def shquote(*args):
    return " ".join(quote(str(arg)) for arg in args)

class CommandError(Exception):
    pass

class process:
    def __init__(self, executable, *args, exit_ok=(0,), stop_signal=SIGINT):
        self.args = (executable,) + args
        self.exit_ok = exit_ok
        self.stop_signal = stop_signal
        self.stdin = None
        self.proc = None

    def __lshift__(self, items):
        if self.stdin is None:
            self.stdin = ""
        if isinstance(items, str):
            self.stdin += items
        else:
            try:
                items = iter(items)
            except TypeError:
                items = (items,)
            for item in items:
                if not isgenerator(item):
                    item = (item,)
                for line in item:
                    self.stdin += f"{line}\n"
        return self

    def __rshift__(self, func):
        with self:
            for line in self:
                func(line.rstrip())

    def _write_stdin(self):
        with self.proc.stdin as fp:
            fp.write(self.stdin)

    def __enter__(self):
        self.proc = Popen(
            self.args,
            stdin=DEVNULL if self.stdin is None else PIPE,
            stdout=PIPE, stderr=STDOUT,
            encoding=getdefaultencoding()
        )
        if self.stdin is not None:
            Thread(target=self._write_stdin).start()
        return self

    def __exit__(self, ex_type, ex_value, ex_tb):
        ret = self.proc.wait()
        if ex_type is not KeyboardInterrupt and ret not in self.exit_ok:
            raise CommandError()

    def __iter__(self):
        try:
            for line in iter(self.proc.stdout):
                yield line
        except KeyboardInterrupt:
            self.send_stop()
            raise

    def send_stop(self):
        self.proc.send_signal(self.stop_signal)

    def run(self):
        output = None
        try:
            with self:
                output = "".join(self)
                return output
        except CommandError:
            raise CommandError(output)
