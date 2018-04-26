import ctypes
from enum import IntEnum

from sawtooth_validator.ffi import LIBRARY


class NativeLmdbDatabase(object):
    def __init__(self, path, _size=1024**4):
        self._db_ptr = ctypes.c_void_p()

        c_path = ctypes.c_char_p(path.encode())
        c_size = ctypes.c_size_t(_size)
        res = LIBRARY.call(
            'lmdb_database_new', c_path, c_size, ctypes.byref(self._db_ptr))
        if res == ErrorCode.Success:
            return
        elif res == ErrorCode.NullPointerProvided:
            raise TypeError("Path cannot be null")
        elif res == ErrorCode.InvalidFilePath:
            raise TypeError("Invalid file path {}".format(path))
        elif res == ErrorCode.InitializeContextError:
            raise TypeError("Unable to initialize LMDB Context")
        elif res == ErrorCode.InitializeDatabaseError:
            raise TypeError("Unable to initialize LMDB Database")
        else:
            raise TypeError("Unknown error occurred: {}".format(res.error))

    def __del__(self):
        if self._db_ptr:
            LIBRARY.call('lmdb_database_drop', self._db_ptr)
            self._db_ptr = None

    @property
    def pointer(self):
        return self._db_ptr


class ErrorCode(IntEnum):
    Success = 0
    NullPointerProvided = 0x01
    InvalidFilePath = 0x02

    InitializeContextError = 0x11
    InitializeDatabaseError = 0x12
