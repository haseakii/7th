"""
Deep nested dictionary access utilities.

Copied from ALAS framework. Provides fast get/set/exist/iter operations
for deeply nested dict structures used in config management.
"""

from collections import deque

OP_ADD = 'add'
OP_SET = 'set'
OP_DEL = 'del'


def deep_get(d, keys, default=None):
    if type(keys) is str:
        keys = keys.split('.')
    try:
        for k in keys:
            d = d[k]
        return d
    except (KeyError, IndexError, TypeError):
        return default


def deep_get_with_error(d, keys):
    if type(keys) is str:
        keys = keys.split('.')
    try:
        for k in keys:
            d = d[k]
        return d
    except (KeyError, IndexError, TypeError):
        raise KeyError


def deep_exist(d, keys):
    if type(keys) is str:
        keys = keys.split('.')
    try:
        for k in keys:
            d = d[k]
        return True
    except (KeyError, IndexError, TypeError):
        return False


def deep_set(d, keys, value):
    if type(keys) is str:
        keys = keys.split('.')
    first = True
    exist = True
    prev_d = None
    prev_k = None
    prev_k2 = None
    try:
        for k in keys:
            if first:
                prev_d = d
                prev_k = k
                first = False
                continue
            try:
                if exist and prev_k in d:
                    prev_d = d
                    d = d[prev_k]
                else:
                    exist = False
                    new = {}
                    d[prev_k] = new
                    d = new
            except TypeError:
                exist = False
                d = {}
                prev_d[prev_k2] = {prev_k: d}
            prev_k2 = prev_k
            prev_k = k
    except TypeError:
        return
    try:
        d[prev_k] = value
        return
    except TypeError:
        prev_d[prev_k2] = {prev_k: value}
        return


def deep_default(d, keys, value):
    if type(keys) is str:
        keys = keys.split('.')
    first = True
    exist = True
    prev_d = None
    prev_k = None
    prev_k2 = None
    try:
        for k in keys:
            if first:
                prev_d = d
                prev_k = k
                first = False
                continue
            try:
                if exist and prev_k in d:
                    prev_d = d
                    d = d[prev_k]
                else:
                    exist = False
                    new = {}
                    d[prev_k] = new
                    d = new
            except TypeError:
                exist = False
                d = {}
                prev_d[prev_k2] = {prev_k: d}
            prev_k2 = prev_k
            prev_k = k
    except TypeError:
        return
    try:
        d.setdefault(prev_k, value)
        return
    except AttributeError:
        prev_d[prev_k2] = {prev_k: value}
        return


def deep_pop(d, keys, default=None):
    if type(keys) is str:
        keys = keys.split('.')
    try:
        for k in keys[:-1]:
            d = d[k]
        return d.pop(keys[-1])
    except (KeyError, TypeError, IndexError, AttributeError):
        return default


def deep_iter(data, min_depth=None, depth=3):
    if min_depth is None:
        min_depth = depth
    assert 1 <= min_depth <= depth

    try:
        if depth == 1:
            for k, v in data.items():
                yield [k], v
            return
        elif min_depth == 1:
            q = deque()
            for k, v in data.items():
                key = [k]
                if type(v) is dict:
                    q.append((key, v))
                else:
                    yield key, v
        else:
            q = deque()
            for k, v in data.items():
                key = [k]
                if type(v) is dict:
                    q.append((key, v))
    except AttributeError:
        return

    current = 2
    while current <= depth:
        new_q = deque()
        if current == depth:
            for key, data in q:
                for k, v in data.items():
                    yield key + [k], v
        elif min_depth <= current < depth:
            for key, data in q:
                for k, v in data.items():
                    subkey = key + [k]
                    if type(v) is dict:
                        new_q.append((subkey, v))
                    else:
                        yield subkey, v
        else:
            for key, data in q:
                for k, v in data.items():
                    subkey = key + [k]
                    if type(v) is dict:
                        new_q.append((subkey, v))
        q = new_q
        current += 1


def deep_iter_diff(before, after):
    if before == after:
        return
    if type(before) is not dict or type(after) is not dict:
        yield [], before, after
        return
    queue = deque([([], before, after)])
    while True:
        new_queue = deque()
        for path, d1, d2 in queue:
            keys1 = set(d1.keys())
            keys2 = set(d2.keys())
            for key in keys1.union(keys2):
                try:
                    val2 = d2[key]
                except KeyError:
                    yield path + [key], d1[key], None
                    continue
                try:
                    val1 = d1[key]
                except KeyError:
                    yield path + [key], None, val2
                    continue
                if val1 != val2:
                    if type(val1) is dict and type(val2) is dict:
                        new_queue.append((path + [key], val1, val2))
                    else:
                        yield path + [key], val1, val2
        queue = new_queue
        if not queue:
            break


def deep_iter_patch(before, after):
    if before == after:
        return
    if type(before) is not dict or type(after) is not dict:
        yield OP_SET, [], after
        return
    queue = deque([([], before, after)])
    while True:
        new_queue = deque()
        for path, d1, d2 in queue:
            keys1 = set(d1.keys())
            keys2 = set(d2.keys())
            for key in keys1.union(keys2):
                try:
                    val2 = d2[key]
                except KeyError:
                    yield OP_DEL, path + [key], None
                    continue
                try:
                    val1 = d1[key]
                except KeyError:
                    yield OP_ADD, path + [key], val2
                    continue
                if val1 != val2:
                    if type(val1) is dict and type(val2) is dict:
                        new_queue.append((path + [key], val1, val2))
                    else:
                        yield OP_SET, path + [key], val2
        queue = new_queue
        if not queue:
            break
