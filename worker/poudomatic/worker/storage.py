import anyio
import anyio.from_thread
import contextlib
import functools
import pickle
import queue
import sqlite3
import threading

class Storage:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, type, value, traceback):
        self.disconnect()

    def _sql(self, query, *params, results=False):
        with self._conn:
            res = self._conn.execute(query, params or ())
            if results:
                if isinstance(results, int):
                    if results == 1:
                        return res.fetchone()
                    else:
                        return [res.fetchone() for _ in range(results)]
                else:
                    return res.fetchall()

    def connect(self):
        self._conn = sqlite3.connect(self.path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=wal")
        self._conn.executescript(self.schema)

    def disconnect(self):
        self._conn.close()

    pickle_protocol = 3
    schema = """
        CREATE TABLE IF NOT EXISTS tasks (
          tid    VARCHAR(32)  PRIMARY KEY NOT NULL,
          data   BLOB         NOT NULL,
          status INTEGER      CHECK(status IN (1, 2, 3)) NOT NULL DEFAULT 1,
          result BLOB
        )
    """

    def _to_binary(self, data):
        return sqlite3.Binary(pickle.dumps(data, self.pickle_protocol))

    def _from_binary(self, data):
        return pickle.loads(data)

    def start_next_task(self):
        with self._conn:
            res = self._conn.execute("""
                SELECT tid,data
                FROM tasks
                WHERE status=1
                ORDER BY rowid LIMIT 1
            """)
            if (task := res.fetchone()) is None:
                return None
            tid,data = task
            self._conn.execute(
                "UPDATE tasks SET status=2 WHERE tid=?",
                (tid,)
            )
            return (tid, self._from_binary(data))

    def end_task(self, tid, result=None):
        self._sql(
            "UPDATE tasks SET status=3,result=? WHERE tid=?",
            None if result is None else self._to_binary(result), tid
        )

    def enqueue(self, tid, data):
        self._sql(
            "INSERT INTO tasks (tid,data) VALUES (?,?)",
            tid, self._to_binary(data)
        )

    def get_result(self, tid):
        result = self._sql(
            "SELECT status,result FROM tasks WHERE tid=?",
            tid, results=1
        )
        if result is not None:
            status,result = result
            return (
                status,
                None if result is None else self._from_binary(result),
            )

class AsyncStorage:
    def __init__(self, path):
        self.store = Storage(path)
        self.stack = contextlib.AsyncExitStack()
        self.queue = queue.Queue()

    async def connect(self):
        portal = await self.stack.enter_async_context(
            anyio.from_thread.BlockingPortal()
        )

        def run_loop():
            while True:
                result,function = self.queue.get()
                if function is None:
                    portal.call(result.set, None, _EMPTY)
                    break
                try:
                    portal.call(result.set, function(), _EMPTY)
                except Exception as e:
                    portal.call(result.set, _EMPTY, e)

        thread = threading.Thread(target=run_loop)
        thread.start()

        await self._run(self.store.connect)

    async def disconnect(self):
        await self._run(self.store.disconnect)
        await self._run(None)
        await self.stack.aclose()

    async def _run(self, func, *args, **kwargs):
        if func is not None:
            func = functools.partial(func, *args, **kwargs)
        res = AsyncResult()
        self.queue.put((res, func))
        return await res

    async def start_next_task(self, *args, **kwargs):
        return await self._run(self.store.start_next_task, *args, **kwargs)

    async def end_task(self, *args, **kwargs):
        return await self._run(self.store.end_task, *args, **kwargs)

    async def enqueue(self, *args, **kwargs):
        return await self._run(self.store.enqueue, *args, **kwargs)

    async def get_result(self, *args, **kwargs):
        return await self._run(self.store.get_result, *args, **kwargs)


_EMPTY = object()

class AsyncResult:
    def __init__(self):
        self.event = anyio.Event()
        self.result = _EMPTY
        self.exception = _EMPTY

    def set(self, result, exception):
        self.result = result
        self.exception = exception
        self.event.set()

    def __await__(self):
        async def closure():
            await self.event.wait()
            if self.exception is not _EMPTY:
                raise self.exception
            return self.result
        return closure().__await__()
