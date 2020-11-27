#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <pkg.h>

static PyObject* py_password_cb = NULL;

static int password_cb(char* buf, int size, int rwflag, void* key) {
  if (py_password_cb == NULL)
    return 0;

  PyObject* arglist = Py_BuildValue("(s)", key);
  PyObject* result = PyObject_CallObject(py_password_cb, arglist);
  Py_DECREF(arglist);

  if (result == NULL)
    return 0;

  if (!PyUnicode_CheckExact(result)) {
    PyErr_Format(PyExc_TypeError, "'%s' object is not a str",
                 Py_TYPE(result)->tp_name);
    Py_DECREF(result);
    return 0;
  }

  PyObject* ascii = PyUnicode_AsASCIIString(result);
  if (ascii == NULL) {
    Py_DECREF(result);
    return 0;
  }

  char* pass = PyBytes_AsString(ascii);
  int len = strlen(pass);

  if (len <= 0) {
    Py_DECREF(ascii);
    Py_DECREF(result);
    return 0;
  }

  if (len > size)
    len = size;

  memset(buf, '\0', size);
  memcpy(buf, pass, len);

  Py_DECREF(ascii);
  Py_DECREF(result);
  return len;
}

static PyObject* libpkg_create_repo(PyObject* self, PyObject* args, PyObject* kws) {
  static char* keywords[] = {
    "path", "output_dir", "filelist", "meta_file", "hash",
    "hash_symlink", "rsa_key", "password_cb",
    NULL
  };

  int ret;

  PyObject* py_path = NULL;
  PyObject* py_output_dir = NULL;
  PyObject* py_meta_file = NULL;
  PyObject* py_rsa_key = NULL;
  PyObject* py_password_cb_temp = NULL;

  const char* path = NULL;
  const char* output_dir = NULL;
  const int filelist = 0;
  const char* meta_file = NULL;
  const int hash = 0;
  const int hash_symlink = 0;
  const char* rsa_key = NULL;

  if (!PyArg_ParseTupleAndKeywords(
          args, kws, "O&|O&pO&ppO&O", keywords,
          PyUnicode_FSConverter, &py_path,
          PyUnicode_FSConverter, &py_output_dir,
          &filelist,
          PyUnicode_FSConverter, &py_meta_file,
          &hash, &hash_symlink,
          PyUnicode_FSConverter, &py_rsa_key,
          &py_password_cb_temp))
    return NULL;

  path = PyBytes_AS_STRING(py_path);

  if (py_output_dir != NULL)
    output_dir = PyBytes_AS_STRING(py_output_dir);
  else
    output_dir = path;

  if (py_meta_file != NULL)
    meta_file = PyBytes_AS_STRING(py_meta_file);

  if (py_rsa_key != NULL)
    rsa_key = PyBytes_AS_STRING(py_rsa_key);

  if (py_password_cb_temp != NULL) {
    if (!PyCallable_Check(py_password_cb_temp)) {
      PyErr_SetString(PyExc_TypeError, "password_cb must be callable");
      return NULL;
    }

    Py_XINCREF(py_password_cb_temp);
  }

  ret = pkg_create_repo(
      (char*) path, output_dir, filelist, meta_file
#ifdef HAVE_PKGREPO_HASH
      , hash, hash_symlink
#endif
  );

  if (ret != EPKG_OK) {
    if (py_password_cb_temp != NULL)
      Py_XDECREF(py_password_cb_temp);

    PyErr_SetString(PyExc_RuntimeError,
                    "Cannot create repository catalogue");
    return NULL;
  }

  if (py_password_cb_temp)
    py_password_cb = py_password_cb_temp;

  ret = pkg_finish_repo(
      output_dir, password_cb,
      (char**) &rsa_key, rsa_key == NULL ? 0 : 1,
      filelist
  );

  if (py_password_cb_temp) {
    py_password_cb = NULL;
    Py_XDECREF(py_password_cb_temp);
  }

  if (ret != EPKG_OK) {
    PyErr_SetString(PyExc_RuntimeError,
                    "Cannot finish repository catalogue");
    return NULL;
  }

  Py_RETURN_NONE;
}

static PyObject* libpkg_version_cmp(PyObject* self, PyObject* args) {
  const char* pkg1 = NULL;
  const char* pkg2 = NULL;

  if (!PyArg_ParseTuple(args, "ss", &pkg1, &pkg2))
    return NULL;

  int res = pkg_version_cmp(pkg1, pkg2);

  return PyLong_FromLong(res);
}

static PyMethodDef libpkg_methods[] = {
  { "pkg_version_cmp", libpkg_version_cmp,
    METH_VARARGS,
    NULL },
  { "pkg_create_repo", (PyCFunction) libpkg_create_repo,
    METH_VARARGS | METH_KEYWORDS,
    NULL },
  { NULL, NULL, 0, NULL }
};

static struct PyModuleDef libpkg_module = {
  PyModuleDef_HEAD_INIT,
  "poudomatic.libpkg",
  NULL,
  -1,
  libpkg_methods
};

PyMODINIT_FUNC PyInit_libpkg(void) {
  return PyModule_Create(&libpkg_module);
}
