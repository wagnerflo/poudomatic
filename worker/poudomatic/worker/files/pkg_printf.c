#include <pkg.h>
#include <sysexits.h>

int main(int argc, char** argv) {
  if (argc != 3) {
    fprintf(stderr, "usage: %s <pkg-file> <format>\n", argv[0]);
    return EX_USAGE;
  }

  struct pkg* pkg = NULL;
  struct pkg_manifest_key* keys = NULL;

  pkg_manifest_keys_new(&keys);

  if (pkg_open(&pkg, argv[1], keys, 0) == EPKG_OK) {
    pkg_printf(argv[2], pkg);
    pkg_free(pkg);
  }

  pkg_manifest_keys_free(keys);

  return 0;
}
