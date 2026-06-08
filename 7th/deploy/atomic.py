import os
import random
import string
import time
from typing import Iterable, Union

IS_WINDOWS = os.name == 'nt'
WINDOWS_MAX_ATTEMPT = 5
WINDOWS_RETRY_DELAY = 0.05


def random_id():
    return ''.join(random.sample(string.ascii_letters + string.digits, 6))


def is_tmp_file(file: str) -> bool:
    if not file.endswith('.tmp'):
        return False
    dot = file[-11:-10]
    if not dot:
        return False
    rid = file[-10:-4]
    return rid.isalnum()


def to_tmp_file(file: str) -> str:
    suffix = random_id()
    return f'{file}.{suffix}.tmp'


def to_nontmp_file(file: str) -> str:
    if is_tmp_file(file):
        return file[:-11]
    else:
        return file


def windows_attempt_delay(attempt: int) -> float:
    return 2 ** attempt * WINDOWS_RETRY_DELAY


def replace_tmp(tmp: str, file: str):
    if IS_WINDOWS:
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                os.replace(tmp, file)
                return
            except PermissionError as e:
                last_error = e
                time.sleep(windows_attempt_delay(attempt))
                continue
            except FileNotFoundError:
                raise
            except Exception as e:
                last_error = e
                break
    else:
        try:
            os.replace(tmp, file)
            return
        except FileNotFoundError:
            raise
        except Exception as e:
            last_error = e

    try:
        os.unlink(tmp)
    except (FileNotFoundError, PermissionError):
        pass
    except Exception:
        pass
    if last_error is not None:
        raise last_error from None


def atomic_replace(replace_from: str, replace_to: str):
    if IS_WINDOWS:
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                os.replace(replace_from, replace_to)
                return
            except PermissionError as e:
                last_error = e
                time.sleep(windows_attempt_delay(attempt))
                continue
            except FileNotFoundError:
                raise
            except Exception as e:
                last_error = e
                break
        if last_error is not None:
            raise last_error from None
    else:
        os.replace(replace_from, replace_to)


def file_write(file: str, data: Union[str, bytes]):
    if isinstance(data, str):
        mode = 'w'
        encoding = 'utf-8'
        newline = ''
    elif isinstance(data, bytes):
        mode = 'wb'
        encoding = None
        newline = None
        data = memoryview(data)
    else:
        typename = str(type(data))
        if typename == "<class 'numpy.ndarray'>":
            mode = 'wb'
            encoding = None
            newline = None
        else:
            mode = 'w'
            encoding = 'utf-8'
            newline = ''

    try:
        with open(file, mode=mode, encoding=encoding, newline=newline) as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except FileNotFoundError:
        directory = os.path.dirname(file)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(file, mode=mode, encoding=encoding, newline=newline) as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())


def file_write_stream(file: str, data_generator):
    data_iter = iter(data_generator)
    try:
        first_chunk = next(data_iter)
    except StopIteration:
        return

    if isinstance(first_chunk, str):
        mode = 'w'
        encoding = 'utf-8'
        newline = ''
    elif isinstance(first_chunk, bytes):
        mode = 'wb'
        encoding = None
        newline = None
    else:
        mode = 'w'
        encoding = 'utf-8'
        newline = ''

    try:
        with open(file, mode=mode, encoding=encoding, newline=newline) as f:
            f.write(first_chunk)
            for chunk in data_iter:
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
    except FileNotFoundError:
        directory = os.path.dirname(file)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(file, mode=mode, encoding=encoding, newline=newline) as f:
            f.write(first_chunk)
            for chunk in data_iter:
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())


def atomic_write(file: str, data: Union[str, bytes]):
    temp = to_tmp_file(file)
    file_write(temp, data)
    replace_tmp(temp, file)


def atomic_write_stream(file: str, data_generator):
    temp = to_tmp_file(file)
    file_write_stream(temp, data_generator)
    replace_tmp(temp, file)


def file_read_text(file: str, encoding: str = 'utf-8', errors: str = 'strict') -> str:
    try:
        with open(file, mode='r', encoding=encoding, errors=errors) as f:
            return f.read()
    except FileNotFoundError:
        return ''


def file_read_bytes(file: str) -> bytes:
    try:
        with open(file, mode='rb', buffering=0) as f:
            return f.read()
    except FileNotFoundError:
        return b''


def atomic_read_text(file: str, encoding: str = 'utf-8', errors: str = 'strict') -> str:
    if IS_WINDOWS:
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                return file_read_text(file, encoding=encoding, errors=errors)
            except PermissionError as e:
                last_error = e
                time.sleep(windows_attempt_delay(attempt))
                continue
        if last_error is not None:
            raise last_error from None
    else:
        return file_read_text(file, encoding=encoding, errors=errors)


def atomic_read_bytes(file: str) -> bytes:
    if IS_WINDOWS:
        last_error = None
        for attempt in range(WINDOWS_MAX_ATTEMPT):
            try:
                return file_read_bytes(file)
            except PermissionError as e:
                last_error = e
                time.sleep(windows_attempt_delay(attempt))
                continue
        if last_error is not None:
            raise last_error from None
    else:
        return file_read_bytes(file)


def file_remove(file: str):
    try:
        os.unlink(file)
    except FileNotFoundError:
        pass


def folder_rmtree(folder, may_symlinks=True):
    try:
        if may_symlinks and os.path.islink(folder):
            file_remove(folder)
            return True
        with os.scandir(folder) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    folder_rmtree(entry.path, may_symlinks=False)
                else:
                    try:
                        file_remove(entry.path)
                    except PermissionError:
                        pass
    except FileNotFoundError:
        return True
    except NotADirectoryError:
        file_remove(folder)
        return True
    try:
        os.rmdir(folder)
        return True
    except FileNotFoundError:
        return True
    except NotADirectoryError:
        file_remove(folder)
        return True
    except OSError:
        return False


def atomic_rmtree(folder: str):
    temp = to_tmp_file(folder)
    try:
        atomic_replace(folder, temp)
    except FileNotFoundError:
        return
    folder_rmtree(temp)


def atomic_failure_cleanup(folder: str, recursive: bool = False):
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                if is_tmp_file(entry.name):
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            folder_rmtree(entry.path, may_symlinks=False)
                        else:
                            file_remove(entry.path)
                    except PermissionError:
                        pass
                    except Exception:
                        pass
                else:
                    if recursive:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                atomic_failure_cleanup(entry.path, recursive=True)
                        except Exception:
                            pass
    except FileNotFoundError:
        pass
    except NotADirectoryError:
        file_remove(folder)
    except Exception:
        pass
