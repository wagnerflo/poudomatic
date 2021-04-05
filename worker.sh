#!/bin/sh
exec \
  sudo \
  PYTHONUSERBASE=$(pwd)/.pyenv \
  python3 -m poudomatic.worker \
  "$@"
