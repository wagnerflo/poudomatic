PW=/usr/sbin/pw

if [ -n "${PKG_ROOTDIR}" ] && [ "${PKG_ROOTDIR}" != "/" ]; then
    PW="${PW} -R ${PKG_ROOTDIR}"
fi
