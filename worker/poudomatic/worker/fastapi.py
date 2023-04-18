from fastapi import FastAPI, Path, Body, Request, HTTPException

from .storage import AsyncStorage
from .tasks import *

TASK_ID_Path = Path(regex="^[0-9a-f]{32}$")

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    app.store = AsyncStorage("/srv/poudomatic/etc/taskdb/taskdb.sqlite")
    await app.store.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await app.store.disconnect()

@app.put("/depends/{task_id}")
async def depends(request: Request,
                  task_id: str = TASK_ID_Path,
                  item: GetDependsTask = Body()):
    await request.app.store.enqueue(task_id, item)
    return "ok"

@app.put("/build/{task_id}")
async def build(request: Request,
                task_id: str = TASK_ID_Path,
                item: RunBuildTask = Body()):
    await request.app.store.enqueue(task_id, item)
    return "ok"

@app.put("/ports/{task_id}")
async def ports(request: Request,
                task_id: str = TASK_ID_Path,
                item: UpdatePortsTask = Body()):
    await request.app.store.enqueue(task_id, item)
    return "ok"

@app.put("/jail/{task_id}")
async def jail(request: Request,
               task_id: str = TASK_ID_Path,
               item: CreateJailTask = Body()):
    await request.app.store.enqueue(task_id, item)
    return "ok"

@app.get("/result/{task_id}")
async def result(request: Request, task_id: str = TASK_ID_Path):
    if result := await request.app.store.get_result(task_id):
        return result
    else:
        raise HTTPException(status_code=404, detail="Task not found")
