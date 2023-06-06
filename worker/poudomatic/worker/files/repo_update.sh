#!/bin/sh
set -e

msg () {
    echo "$@" >/dev/stderr
}

find_pkg () {
    for file in "$1/$2".pkg "$1/$2".*; do
        if real=$(realpath -q "${file}"); then
            printf '%s' "${real}"
            return 0
        fi
    done
    return 1
}

compile_tool () {
    cc -I"${PREFIX}/include" -L"${PREFIX}/lib" -lpkg -o"$1" -xc -
}

# bootstrap pkg
pkgpackage=$(find_pkg /pkg/Latest pkg)
tar xf "${pkgpackage}" -C /tmp -s ',.*/,,' '*/pkg-static'
/tmp/pkg-static add "${pkgpackage}"

# compile tools
PREFIX=$(pkg query %p pkg)
PKG_PRINTF=/tmp/pkg_printf
PKG_LATEST=/tmp/pkg_latest

compile_tool ${PKG_PRINTF} <<EOF
§{pkg_printf_c}
EOF

compile_tool ${PKG_LATEST} <<EOF
§{pkg_latest_c}
EOF

pkg_get_files () {
    local prefix=$(${PKG_PRINTF} "$1" "%p")
    ${PKG_PRINTF} "$1" "%F%{%Fn %Fu:%Fg:%Fp %Fs\n%}" | \
        sed -e s@^${prefix}/share/licenses/[^/]*@__LICENSE_DIR__@
}

pkg_equal () {
    for query in "%n" \
                 "%o" \
                 "%p" \
                 "%C%{%Cn\n%}" \
                 "%m" \
                 "%c" \
                 "%e" \
                 "%L" \
                 "%w" \
                 "%q" \
                 "%M" \
                 "%O%{%On: %Ov [default: %Od] <%OD>\n%}" \
                 "%A%{%An: %Av\n%}" \
                 "%U%{%Un, %|%}" \
                 "%G%{%Gn\n%}" \
                 "%d%{%dn-%dv (%do)\n%}" \
                 "%B%{%Bn\n%}" \
                 "%D%{%Dn %Du:%Dg:%Dp\n%}" \
                 "%b%{%bn\n%}"; \
    do
        r1=$(${PKG_PRINTF} "$1" "${query}")
        r2=$(${PKG_PRINTF} "$2" "${query}")
        if [ "${r1}" != "${r2}" ]; then
            msg "===> difference found in pkg_printf(3) query ${query}"
            return 1
        fi
    done
    r1=$(pkg_get_files "$1")
    r2=$(pkg_get_files "$2")
    if [ "${r1}" != "${r2}" ]; then
        msg "===> difference found in file list"
        return 1
    fi
    return 0
}

mkdir -p /pkg/repo/All
mkdir -p /pkg/repo/Latest
rebuild=0

for pkg in §{packages}; do
    src=$(find_pkg /pkg/All "${pkg}")
    latest=$(find /pkg/repo/All -type f -mindepth 1 -maxdepth 1 -print0 | \
                 ${PKG_LATEST} $(${PKG_PRINTF} "${src}" %n))

    if [ -n "${latest}" ]; then
        msg "Comparing new ${pkg} to existing $(basename "${latest%.*}")"
        if pkg_equal "${src}" "${latest}"; then
            msg "===> identical to latest version"
            continue
        fi
    fi

    msg "Committing ${pkg}"
    ln -f "${src}" "/pkg/repo/All/$(basename "${src}")"
    rebuild=1
done

if [ ${rebuild} -eq 1 ]; then
    pkg repo -l /pkg/repo
    cp -HRf /pkg/Latest/ /pkg/repo/Latest
fi
