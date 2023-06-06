import anyio
import pickle
import sqlite3

from .util import Watcher

if sqlite3.threadsafety != 3:
    raise Exception()

class Storage:
    pickle_protocol = 3
    schema = """
        CREATE TABLE IF NOT EXISTS tasks (
          tid    VARCHAR(32)  PRIMARY KEY NOT NULL,
          data   BLOB         NOT NULL,
          status INTEGER      CHECK(status IN (1, 2, 3)) NOT NULL DEFAULT 1,
          result BLOB
        );

        CREATE TABLE IF NOT EXISTS log (
          tid    VARCHAR(32)  NOT NULL,
          data   BLOB
        );
    """

    def __init__(self, path):
        self._path = path
        self._conn = None

    def __enter__(self):
        if self._conn is None:
            self._conn = sqlite3.connect(
                self._path,
                isolation_level=None,
                check_same_thread=False,
            )
            self._conn.execute("PRAGMA journal_mode=wal")
            self._conn.executescript(self.schema)
            self._watcher = Watcher()
            self._watcher.add(f"{self._path}-wal", Watcher.WRITE)
        return self

    def __exit__(self, type, value, traceback):
        if self._conn is not None:
            self._watcher = None
            self._conn.close()
            self._conn = None

    def _sql(self, query, *params, results=False):
        with self._conn:
            res = self._conn.execute(query, params or ())
            if results:
                if isinstance(results, bool):
                    return res.fetchall()
                else:
                    if results == 1:
                        return res.fetchone()
                    else:
                        return [res.fetchone() for _ in range(results)]


    def _to_binary(self, data):
        return sqlite3.Binary(pickle.dumps(data, self.pickle_protocol))

    def _from_binary(self, data):
        return pickle.loads(data)

    def wait_for_changes(self):
        self._watcher.wait()

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
        self._sql("INSERT INTO log VALUES (?, NULL)", tid)

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

    def add_log(self, tid, data):
        if data is None:
            raise Exception()
        self._sql(
            "INSERT INTO log VALUES (?,?)",
            tid, self._to_binary(data)
        )

    def _get_log_sync(self, tid, start=0):
        complete = False
        results = []

        for rowid,data in self._sql(
                "SELECT rowid,data FROM log WHERE tid=? AND rowid>? ORDER BY rowid ASC",
                tid, start, results=True
            ):
            if data is None:
                complete = True
                break
            results.append((rowid, self._from_binary(data)))

        return (complete, results)

    async def _get_log(self,  tid, start=0):
        return await anyio.to_thread.run_sync(self._get_log_sync, tid, start)

    async def get_log(self, tid, start=0):
        _,entries = await self._get_log(tid, start)
        return entries

    async def watch_log(self, tid, running=None):
        maxid = 0
        while running is not None and await running():
            complete,entries = await self._get_log(tid, maxid)
            for id,data in entries:
                maxid = max(maxid, id)
                yield id,data
            if complete:
                return
            await self._watcher.async_wait()
