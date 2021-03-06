#!/bin/sh
set -e
set -u
set -f

% include "scripts/need_pw.sh"

% for login,userconf in rendervars.users.items()
if ! ${PW} usershow {{ login }} >/dev/null 2>&1; then
    echo "===> Creating user '{{ login }}' with uid '{{ userconf.uid }}'."
    ${PW} useradd \
          -n {{ login }} \
          -u {{ userconf.uid }} -g {{ userconf.gid }} \
% if userconf.groups
          -G {{ userconf.groups|join(",") }} \
% endif
          -c "{{ userconf.gecos }}" \
          -d {{ userconf.home }} \
          -s {{ userconf.shell }}
else
    echo "===> Using existing user '{{ login }}'."
fi

% endfor
