from codecs import getincrementaldecoder
from concurrent.futures import ThreadPoolExecutor, wait
from functools import wraps
from json import dumps as _encode_json, loads as decode_json
from queue import Queue
from re import compile as regex
from time import sleep
from urllib.request import (
    Request,
    urlopen,
    HTTPError,
    URLError,
)
from uuid import uuid4

SSE_EOF = regex(r'\r\n\r\n|\r\r|\n\n')
SSE_LINE = regex(r'([^:]*):?(?: ?(.*))?')

def encode_json(data):
    return _encode_json(data, ensure_ascii=False).encode("utf-8")

def generate_task_id(f):
    @wraps(f)
    def wrapper(self, *args, **kwds):
        return f(self, uuid4().hex, *args, **kwds)
    return wrapper

class PoudomaticClient:
    _HEADERS = {
        "Content-Type": "application/json",
    }
    _SSE_HEADERS = {
        **_HEADERS,
        "Cache-Control": "no-cache",
        "Accept": "text/event-stream",
    }

    def __init__(self, endpoints):
        self.endpoints = endpoints

    def __enter__(self):
        self.pool = ThreadPoolExecutor(max_workers=len(self.endpoints))
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.pool.shutdown()

    def req(self, method, url, data=None):
        data = None if data is None else encode_json(data)
        def run(endpoint):
            req = Request(
                f"{endpoint}/{url}",
                data=data,
                headers=self._HEADERS,
                method=method,
            )
            with urlopen(req, timeout=5) as resp:
                return decode_json(resp.fp.read())
        return self._request_run(run)

    def _request_run(self, run):
        done,_ = wait([
            self.pool.submit(run, endpoint)
            for endpoint in self.endpoints
        ])
        results = {}
        for endpoint,fut in zip(self.endpoints, done):
            try:
                results[endpoint] = fut.result()
            except Exception as e:
                e.add_note(f"Error occured on endpoint: {endpoint}.")
                raise
        return results

    def _follow_log_request(self, task_id, endpoint, queue):
        req = Request(
            f"{endpoint}/log/{task_id}",
            headers=self._SSE_HEADERS,
        )
        with urlopen(req, timeout=30) as resp:
            charset = resp.headers.get_content_charset()
            decoder = getincrementaldecoder(charset)(errors="replace")
            buf = ""

            while (data := resp.read1()):
                buf = buf + decoder.decode(data)
                if not buf:
                    continue
                *messages,buf = SSE_EOF.split(buf)
                for msg in messages:
                    data = ""
                    event = None

                    for line in msg.splitlines():
                        match = SSE_LINE.match(line)
                        if match is None:
                            continue

                        name,value = match.groups()
                        if not name:
                            continue

                        match name:
                            case "event":
                                event = value
                            case "data":
                                data = f"{data}\n{value}" if data else value

                    if event is None:
                        queue.put((endpoint, data))

            queue.put((endpoint, None))

    def follow_log(self, task_id):
        queue = Queue()
        futures = [
            self.pool.submit(
                self._follow_log_request,
                task_id, endpoint, queue
            )
            for endpoint in self.endpoints
        ]
        while not queue.empty() or not all(fut.done() for fut in futures):
            endpoint,data = queue.get()
            if data is not None:
                yield endpoint,decode_json(data)

    def get_result(self, task_id):
        def run(endpoint):
            while True:
                req = Request(
                    f"{endpoint}/result/{task_id}",
                    headers=self._HEADERS,
                )
                with urlopen(req, timeout=5) as resp:
                    status,res = decode_json(resp.fp.read())
                    if status == 3:
                        return res
                    sleep(2.5)
        return self._request_run(run)

    def info(self):
        portsbranches = set()
        jails = set()

        for results in self.req("GET", "info").values():
            portsbranches.update(results["portsbranches"])
            jails.update(results["jails"])

        return {
            "portsbranches": sorted(portsbranches),
            "jails": sorted(jails),
        }

    @generate_task_id
    def build(self, task_id, jail_version, ports_branch, origins, portja_targets):
        self.req("PUT", f"build/{task_id}", {
            "jail_version": jail_version,
            "ports_branch": ports_branch,
            "origins": origins,
            "portja_targets": portja_targets,
        })
        return task_id

    @generate_task_id
    def updateports(self, task_id, ports_branch):
        self.req("PUT", f"ports/update/{task_id}", {
            "branch": ports_branch,
        })
        return task_id

__all__ = (
    "API",
)
