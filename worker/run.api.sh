#!/bin/sh

if [ -z "$1" ]; then
    echo "usage: $0 dataset"
    exit 1
fi

if ! zfs list "$1" >/dev/null; then
    exit 1
fi

POUDOMATIC_DATASET="$1" \
  exec \
    uvicorn poudomatic.worker.fastapi:app \
      --reload --host 0.0.0.0 --port 8080
