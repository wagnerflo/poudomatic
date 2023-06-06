#!/bin/sh
_dir=$(dirname $(readlink -f "$0"))
PIP_USER=true \
PYTHONUSERBASE=${_dir}/.pyenv \
PYTHONPATH=${_dir} \
    python3 -m poudomatic.client "$@"
