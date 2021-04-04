from json import dumps as _encode_json, loads as decode_json
from time import sleep
from urllib.request import Request, urlopen, HTTPError
from uuid import uuid4

def encode_json(data):
    return _encode_json(data, ensure_ascii=False).encode("utf-8")

class API:
    _HEADERS = {
        "Content-Type": "application/json",
    }

    def __init__(self, base="http://localhost:8080"):
        self.base = base

    def generate_task_id(self):
        return uuid4().hex

    def req(self, method, url, data=None):
        req = Request(
            f"{self.base}/{url}",
            data=None if data is None else encode_json(data),
            headers=self._HEADERS,
            method=method,
        )
        try:
            with urlopen(req) as resp:
                return (resp, decode_json(resp.fp.read()))
        except HTTPError as e:
            return (e, decode_json(e.fp.read()))

    def get_result(self, task_id):
        while True:
            resp,data = self.req("GET", f"result/{task_id}")
            if resp.status != 200:
                return None
            status,res = data
            if status == 3:
                return res
            sleep(2.5)

__all__ = (
    "API",
)
