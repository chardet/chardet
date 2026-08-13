# Build-time-only type declarations for _kernel.py.  Cython reads this file;
# CPython and PyPy never do, and it ships no code — the .py is the only
# implementation.  Cython's default bounds and wraparound checks are left on.
cimport cython

@cython.locals(dot=cython.ulonglong, n=cython.Py_ssize_t, i=cython.Py_ssize_t)
cpdef unsigned long long dot_packed(int[::1] idx, int[::1] vals, bytes model)

# ``vals`` is deliberately left untyped.  Declaring it ``int[::1]`` would make
# the compiled build return a memoryview where the interpreted build returns
# an ``array.array``, and this function's result is stored on the profile and
# handed back out — a type that differs between builds is not worth the few
# microseconds, since pack_profile runs once per profile (~4k calls) rather
# than on the 289k-call scoring path.
@cython.locals(n=cython.Py_ssize_t, i=cython.Py_ssize_t)
cpdef pack_profile(list nonzero, list freq)
