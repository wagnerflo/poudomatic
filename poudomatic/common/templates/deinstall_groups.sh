#!/bin/sh
set -e
set -u
set -f

% include "need_pw.sh"

% for group,grpconf in rendervars.groups.items()
if ${PW} groupshow {{ group }} >/dev/null 2>&1; then
    echo "==> You should manually remove the '{{ group }}' group."
fi

% endfor
