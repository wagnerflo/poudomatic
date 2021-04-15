#!/bin/sh
set -e
set -u
set -f

% include "scripts/need_pw.sh"

% for group,grpconf in rendervars.groups.items()
if ! ${PW} groupshow {{ group }} >/dev/null 2>&1; then
    echo "===> Creating group '{{ group }}' with gid '{{ grpconf.gid }}'."
    ${PW} groupadd -n {{ group }} -g {{ grpconf.gid }}
else
    echo "===> Using existing group '{{ group }}'."
fi

% endfor
