from contextlib import asynccontextmanager
from fastapi import FastAPI, Path, Body, Request, Header, HTTPException
from json import dumps as encode_json
from pydantic import BaseSettings
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from typing import Annotated

from .environment import Environment
from .tasks import *

class Settings(BaseSettings):
    class Config:
        env_prefix = "poudomatic_"

    dataset: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.env = Environment(settings.dataset, no_setup=True)
    with app.env.storage as app.store:
        yield

settings = Settings()
app = FastAPI(lifespan=lifespan)

TASK_ID_Path = Path(regex="^[0-9a-f]{32}$")

@app.get("/info")
def info(request: Request):
    return {
        "portsbranches": list(request.app.env.list_portsbranches()),
        "jails": list(request.app.env.list_jails()),
    }

@app.get("/log/{task_id}")
async def log(request: Request,
              accept: Annotated[str, Header()],
              task_id: str = TASK_ID_Path):
    if accept != "text/event-stream":
        return await request.app.store.get_log(task_id)

    async def is_connected():
        return not await request.is_disconnected()

    async def watch_log():
        async for id,data in request.app.store.watch_log(task_id, is_connected):
            yield ServerSentEvent(encode_json(data, ensure_ascii=False), id=id)

    return EventSourceResponse(watch_log())

@app.put("/depends/{task_id}")
def depends(request: Request,
            task_id: str = TASK_ID_Path,
            item: GetDependsTask = Body()):
    request.app.store.enqueue(task_id, item)
    return "ok"

@app.put("/build/{task_id}")
def build(request: Request,
          task_id: str = TASK_ID_Path,
          item: RunBuildTask = Body()):
    request.app.store.enqueue(task_id, item)
    return "ok"

@app.put("/ports/update/{task_id}")
def updateports(request: Request,
                task_id: str = TASK_ID_Path,
                item: UpdatePortsTask = Body()):
    request.app.store.enqueue(task_id, item)
    return "ok"

@app.put("/jail/{task_id}")
def jail(request: Request,
         task_id: str = TASK_ID_Path,
         item: CreateJailTask = Body()):
    request.app.store.enqueue(task_id, item)
    return "ok"

@app.get("/result/{task_id}")
def result(request: Request,
           task_id: str = TASK_ID_Path):
    if result := request.app.store.get_result(task_id):
        return result
    else:
        raise HTTPException(status_code=404, detail="Task not found")
