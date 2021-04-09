#!/bin/sh
set -e

case "$2" in
% for target,scripts in targets.items() if scripts
  {{ target }})
    script=$(mktemp)
    chmod +x "${script}"
%   for script in scripts
    ex=0
    cat > "${script}" <<{{ script|heredoc }}
    "${script}" "$@" || ex=$?
    if [ ${ex} -ne 0 ]; then
      rm "${script}"
      exit ${ex}
    fi
%   endfor
    rm "${script}"
  ;;
% endfor
esac
