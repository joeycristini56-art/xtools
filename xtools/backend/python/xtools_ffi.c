/*
 * XTools FFI - C Extension
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyObject* call_tool(const char* func_name, PyObject* args) {
    PyObject* sys_path = PySys_GetObject("path");
    PyObject* path = PyUnicode_FromString("/workspace/project/xtools/backend/python");
    PyList_Append(sys_path, path);
    Py_DECREF(path);
    
    PyObject* pModule = PyImport_ImportModule("xtools_ffi_module");
    if (!pModule) {
        PyErr_Print();
        return PyUnicode_FromString("{\"success\":false,\"error\":\"Module not found\"}");
    }
    
    PyObject* pFunc = PyObject_GetAttrString(pModule, func_name);
    Py_DECREF(pModule);
    
    if (!pFunc || !PyCallable_Check(pFunc)) {
        Py_XDECREF(pFunc);
        return PyUnicode_FromString("{\"success\":false,\"error\":\"Function not found\"}");
    }
    
    PyObject* pResult = PyObject_CallObject(pFunc, args);
    Py_DECREF(pFunc);
    
    if (!pResult) {
        PyErr_Print();
        return PyUnicode_FromString("{\"success\":false,\"error\":\"Call failed\"}");
    }
    
    return pResult;
}

static PyObject* ffi_gofile_upload(PyObject* self, PyObject* args) {
    const char* file_path;
    if (!PyArg_ParseTuple(args, "s", &file_path)) return NULL;
    PyObject* py_args = PyTuple_Pack(1, PyUnicode_FromString(file_path));
    PyObject* result = call_tool("gofile_upload_func", py_args);
    Py_DECREF(py_args);
    return result;
}

static PyObject* ffi_run_sort(PyObject* self, PyObject* args) {
    const char* file_path;
    if (!PyArg_ParseTuple(args, "s", &file_path)) return NULL;
    PyObject* py_args = PyTuple_Pack(1, PyUnicode_FromString(file_path));
    PyObject* result = call_tool("run_sort", py_args);
    Py_DECREF(py_args);
    return result;
}

static PyObject* ffi_run_filter(PyObject* self, PyObject* args) {
    const char* file_path;
    if (!PyArg_ParseTuple(args, "s", &file_path)) return NULL;
    PyObject* py_args = PyTuple_Pack(1, PyUnicode_FromString(file_path));
    PyObject* result = call_tool("run_filter", py_args);
    Py_DECREF(py_args);
    return result;
}

static PyObject* ffi_run_dedup(PyObject* self, PyObject* args) {
    const char* file_path;
    if (!PyArg_ParseTuple(args, "s", &file_path)) return NULL;
    PyObject* py_args = PyTuple_Pack(1, PyUnicode_FromString(file_path));
    PyObject* result = call_tool("run_dedup", py_args);
    Py_DECREF(py_args);
    return result;
}

static PyObject* ffi_run_split(PyObject* self, PyObject* args) {
    const char* file_path;
    if (!PyArg_ParseTuple(args, "s", &file_path)) return NULL;
    PyObject* py_args = PyTuple_Pack(1, PyUnicode_FromString(file_path));
    PyObject* result = call_tool("run_split", py_args);
    Py_DECREF(py_args);
    return result;
}

static PyObject* ffi_run_remove(PyObject* self, PyObject* args) {
    const char* file_path;
    const char* pattern;
    if (!PyArg_ParseTuple(args, "ss", &file_path, &pattern)) return NULL;
    PyObject* py_args = PyTuple_Pack(2, PyUnicode_FromString(file_path), PyUnicode_FromString(pattern));
    PyObject* result = call_tool("run_remove", py_args);
    Py_DECREF(py_args);
    return result;
}

static PyObject* ffi_discord_bot(PyObject* self, PyObject* args) {
    const char* token;
    const char* imap_host;
    const char* imap_user;
    const char* imap_pass;
    const char* channel_id;
    if (!PyArg_ParseTuple(args, "sssss", &token, &imap_host, &imap_user, &imap_pass, &channel_id)) return NULL;
    PyObject* py_args = PyTuple_Pack(5, 
        PyUnicode_FromString(token), 
        PyUnicode_FromString(imap_host),
        PyUnicode_FromString(imap_user),
        PyUnicode_FromString(imap_pass),
        PyUnicode_FromString(channel_id)
    );
    PyObject* result = call_tool("discord_bot", py_args);
    Py_DECREF(py_args);
    return result;
}

static PyObject* ffi_telegram_bot(PyObject* self, PyObject* args) {
    const char* api_id;
    const char* api_hash;
    const char* phone;
    if (!PyArg_ParseTuple(args, "sss", &api_id, &api_hash, &phone)) return NULL;
    PyObject* py_args = PyTuple_Pack(3, 
        PyUnicode_FromString(api_id), 
        PyUnicode_FromString(api_hash),
        PyUnicode_FromString(phone)
    );
    PyObject* result = call_tool("telegram_bot", py_args);
    Py_DECREF(py_args);
    return result;
}

static PyObject* ffi_run_scraper(PyObject* self, PyObject* args) {
    const char* url;
    if (!PyArg_ParseTuple(args, "s", &url)) return NULL;
    PyObject* py_args = PyTuple_Pack(1, PyUnicode_FromString(url));
    PyObject* result = call_tool("run_scraper", py_args);
    Py_DECREF(py_args);
    return result;
}

static PyObject* ffi_run_combo(PyObject* self, PyObject* args) {
    const char* file_path;
    if (!PyArg_ParseTuple(args, "s", &file_path)) return NULL;
    PyObject* py_args = PyTuple_Pack(1, PyUnicode_FromString(file_path));
    PyObject* result = call_tool("run_combo", py_args);
    Py_DECREF(py_args);
    return result;
}

static PyObject* ffi_run_captcha(PyObject* self, PyObject* args) {
    const char* image_path;
    if (!PyArg_ParseTuple(args, "s", &image_path)) return NULL;
    PyObject* py_args = PyTuple_Pack(1, PyUnicode_FromString(image_path));
    PyObject* result = call_tool("run_captcha", py_args);
    Py_DECREF(py_args);
    return result;
}

static PyMethodDef XToolsMethods[] = {
    {"gofile_upload", ffi_gofile_upload, METH_VARARGS, "Upload to GoFile"},
    {"run_sort", ffi_run_sort, METH_VARARGS, "Sort tool"},
    {"run_filter", ffi_run_filter, METH_VARARGS, "Filter tool"},
    {"run_dedup", ffi_run_dedup, METH_VARARGS, "Dedup tool"},
    {"run_split", ffi_run_split, METH_VARARGS, "Split tool"},
    {"run_remove", ffi_run_remove, METH_VARARGS, "Remove tool"},
    {"discord_bot", ffi_discord_bot, METH_VARARGS, "Discord bot"},
    {"telegram_bot", ffi_telegram_bot, METH_VARARGS, "Telegram bot"},
    {"run_scraper", ffi_run_scraper, METH_VARARGS, "Scraper"},
    {"run_combo", ffi_run_combo, METH_VARARGS, "Combo tool"},
    {"run_captcha", ffi_run_captcha, METH_VARARGS, "Captcha tool"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef xtools_module = {
    PyModuleDef_HEAD_INIT,
    "xtools_ffi",
    "XTools FFI - Direct Python Integration",
    -1,
    XToolsMethods
};

PyMODINIT_FUNC PyInit_xtools_ffi(void) {
    return PyModule_Create(&xtools_module);
}
