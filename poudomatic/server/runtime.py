from asyncio import get_running_loop

class ConsoleRuntime:
    @classmethod
    async def new(cls):
        self = cls()
        return self

    async def log(self, msg):
        print(msg)
