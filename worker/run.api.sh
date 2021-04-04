#!/bin/sh
exec \
  uvicorn poudomatic.worker.fastapi:app \
    --reload --host 0.0.0.0 --port 8080
