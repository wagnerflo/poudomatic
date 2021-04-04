#include <pkg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sysexits.h>

int main(int argc, char** argv) {
  if (argc != 2) {
    fprintf(stderr, "usage: %s <pkg-name>\n", argv[0]);
    return EX_USAGE;
  }

  struct pkg* pkg = NULL;
  struct pkg_manifest_key* keys = NULL;

  char* max_version = strdup("");
  char* max_file = NULL;

  char* line = NULL;
  size_t linecap = 0;

  char* pkgname = NULL;
  char* pkgversion = NULL;

  pkg_manifest_keys_new(&keys);

  while (getdelim(&line, &linecap, '\0', stdin) != -1) {
    if (pkg_open(&pkg, line, keys, 0) != EPKG_OK)
      continue;

    pkg_asprintf(&pkgname, "%n", pkg);

    if (strcmp(pkgname, argv[1]) == 0) {
      pkg_asprintf(&pkgversion, "%v", pkg);

      if (pkg_version_cmp(pkgversion, max_version) > 0) {
        free(max_version);
        free(max_file);
        max_version = strdup(pkgversion);
        max_file = strdup(line);
      }

      free(pkgversion);
      free(pkgname);
      pkg_free(pkg);
    }
  }

  if (max_file != NULL)
    printf("%s", max_file);

  free(line);
  pkg_manifest_keys_free(keys);

  return 0;
}
