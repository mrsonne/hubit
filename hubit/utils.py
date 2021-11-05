from __future__ import annotations
from functools import reduce
import itertools
from operator import getitem
from typing import List, Dict, Tuple
from collections.abc import Mapping


class ReadOnlyDict(Mapping):
    def __init__(self, data):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def __str__(self):
        return self._data.__str__()


def is_digit(s: str) -> bool:
    """Alternative to s.isdigit() that handles negative integers

    Args:
        s (str): A string

    Returns:
        bool: Flag indicating if the input string is a signed int
    """
    try:
        int(s)
        return True
    except:
        return False


def reshape(paths, valmap):
    """
    paths contains path strings in the correct shape i.e. a nested list.
    Even a simple number is a list of one element due to the expansion.
    If only one element return that element i.e. the value. Else collect the
    values from the value map an store them in a nested list structure like
    paths.
    """
    if len(paths) > 1:
        return [
            valmap[path] if isinstance(path, str) else reshape(path, valmap)
            for path in paths
        ]
    else:
        return valmap[paths[0]]


def traverse(items):
    """
    Iterate nested list. Stop iteration if string elements are encountered
    """
    try:
        for i in iter(items):
            if not isinstance(i, str):
                for j in traverse(i):
                    yield j
            else:
                yield i
    except TypeError:
        yield items


def set_element(data, value, indices):
    """
    Set the "value" on the "data" (nested list with all elements initialized)
    at the "indices" (list of indices)

    For example the input

    data = [[None, None, None], [None, None]]
    indices = 0, 2
    value = 17.0

    Gives the return value

    [[None, None, 17.0], [None, None]]

    """
    _data = data
    # Loop over indices excluding last and point to list
    # at an increasingly deeper level of the
    for idx in indices[:-1]:
        _data = _data[idx]
    # _data is now the innermost list where the values should be set
    _data[indices[-1]] = value
    return data


def set_nested_item(data, keys, val):
    """Set item in nested dictionary"""
    reduce(getitem, keys[:-1], data)[keys[-1]] = val
    return data


def get_nested_item(data, keys):
    return reduce(getitem, keys, data)


def get_from_datadict(datadict, keys):
    """
    Extract value from a nested dictionary using list of keys.
    datadict is a dict. keys is a list of keys (strings).
    """
    # Convert digits strings to int
    _keys = [int(key) if is_digit(key) else key for key in keys]
    return reduce(getitem, _keys, datadict)


def split_items(items: List, sizes: List[int]) -> List:
    """Split the items into a list each with length as specified in
    sizes

    len(split_items) = len(sizes)
    len(split_items[i]) = sizes[i]

    Args:
        items (List): Flat list of items to be split
        sizes (List[int]): Sizes of elements in the split list

    Returns:
        List: Split list
    """
    it = iter(items)
    return [list(itertools.islice(it, 0, size)) for size in sizes]


def count(items: List, key_from: str, increment_fun=(lambda x: 1)):
    """
    Aggregate objects from a list by the attribute `key_from`.
    By default each item increments the counter by 1.
    """
    counts: Dict[str, int] = {}
    for item in items:
        key = getattr(item, key_from)
        increment = increment_fun(item)
        counts[key] = counts.get(key, 0) + increment
    return counts
