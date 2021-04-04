#!/bin/sh
exec \
  sudo \
    PYTHONUSERBASE=$(pwd)/.pyenv \
    PATH=${PATH}:$(pwd)/../../portja/bin \
    python3 -m poudomatic.worker "$@"
