from asyncio import (
    create_subprocess_exec,
    create_task,
    wait as wait_aws,
    CancelledError,
)
from asyncio.subprocess import (
    DEVNULL,
    PIPE,
    STDOUT,
)

class process:
    def __init__(self, executable, *args, exit_ok=(0,)):
        self.args = (executable,) + args
        self.exit_ok = exit_ok
        self.stdin = []
        self.pipe_to = []
        self.proc = None

    def __lshift__(self, item):
        if isinstance(item, str):
            self.stdin.append(item)
        else:
            self.stdin.extend(item)
        return self

    def __rshift__(self, func):
        self.pipe_to.append(func)
        return self

    @property
    def stdin_lines(self):
        for line in self.stdin:
            yield f"{line}\n".encode()

    async def _check_exit(self, err):
        if await self.proc.wait() not in self.exit_ok:
            raise Exception(err)

    async def _redirect_to(self, stream):
        try:
            while line := await stream.readline():
                line = line.decode().rstrip()
                for func in self.pipe_to:
                    await func(line)
        except CancelledError:
            pass

    async def _write_stdin(self, stream):
        if self.stdin:
            stream.writelines(self.stdin_lines)
            await stream.drain()
            stream.close()
            await stream.wait_closed()

    async def _redirector(self):
        await wait_aws((
            create_task(self._write_stdin(self.proc.stdin)),
            create_task(self._redirect_to(self.proc.stdout)),
            create_task(self._redirect_to(self.proc.stderr)),
        ))
        await self._check_exit('')

    async def _waiter(self):
        stdout,stderr = await self.proc.communicate(
            b''.join(self.stdin_lines) if self.stdin else None
        )
        await self._check_exit(stderr.decode())
        return stdout.decode()

    async def _start(self):
        self.proc = await create_subprocess_exec(
            *self.args,
            stdin=PIPE if self.stdin else DEVNULL,
            stdout=PIPE, stderr=PIPE,
        )
        # run a task that redirects stdout and stderr
        if self.pipe_to:
            return self._redirector()
        # coroutine that waits for end
        else:
            return self._waiter()

    def __await__(self):
        return self._start().__await__()
