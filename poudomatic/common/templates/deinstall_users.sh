#!/bin/sh
set -e
set -u
set -f

% include "need_pw.sh"

% for login,userconf in rendervars.users.items()
if ${PW} usershow {{ login }} >/dev/null 2>&1; then
    echo "==> You should manually remove the '{{ login }}' user."
fi

% endfor
