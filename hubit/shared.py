from __future__ import print_function
from os import path

import re
import copy
import itertools
import collections
from functools import reduce
from operator import getitem
from typing import Any, List, Dict, Tuple

# Python 2 & 3 compatibility
try:
  basestring
except NameError:
  basestring = str

class HubitError(Exception):
    pass


class Container(object):

    def __init__(self, val):
        self.val = val


    def __str__(self):
        return str(self.val)


def get_from_datadict(datadict, keys):
    """
    Extract value from a nested dictionary using list of keys.
    datadict is a dict. keys is a list of keys (strings).
    """
    # Convert digits strings to int
    _keys = [int(key) if key.isdigit() else key for key in keys]
    return reduce(getitem, _keys, datadict)


def convert_to_internal_path(path: str) -> str:
    """Convert user path using [IDX] to internal path using .IDX.

    Args:
        path (str): Hubit user path string

    Returns:
        str: Hubit internal path string
    """
    return path.replace('[', '.').replace(']', '')


def _length_for_iterpaths(connecting_paths: List[str],
                          input_data: Dict,
                          out=None,
                          paths_previous=None) -> Tuple:
    """Lengths 

    Args:
        connecting_paths (List[str]): Sequence of index identification strings between index IDs
        input_data (Dict): Input data 
        out (List, optional): Lengths found in previous level of recusion. Defaults to None.
        paths_previous (List, optional): Hubit internal paths found in previous level of recusion with explicit indeices. Defaults to None.

    Returns:
        Tuple: Two-tuple out, paths_previous
    """
    sep = '.'
    paths_previous = paths_previous or [connecting_paths[0]]
    out = out or []

    # Get list lengths for paths prepared at the previous recusion level
    out_current_level = [ len( get_from_datadict(input_data, path.split(sep)))
                          for path in paths_previous ]

    out.append(out_current_level)

    paths_next = paths_previous
    if len(connecting_paths) > 1:
        # Prepare paths for next recursive call by appending the 
        # indices (from out_current_level) and the connecting path 
        # to the previosly found paths
        paths_next = ['{}.{}.{}'.format(path_previous, curidx, connecting_paths[1]) 
                        for length, path_previous in zip(out_current_level, paths_previous)
                        for curidx in range(length)]

        # Call again for next index ID
        out, paths_next = _length_for_iterpaths(connecting_paths[1:],
                                                    input_data,
                                                    out=out,
                                                    paths_previous=paths_next)

    elif len(connecting_paths) == 1:
        paths_next = ['{}.{}'.format(path_previous, curidx) 
                        for length, path_previous in zip(out_current_level, paths_previous)
                        for curidx in range(length)]


    return out, paths_next



def lengths_for_path(path: str, input_data: Dict) -> Any:
    """Infer lengths of lists in 'input_data' that correspond 
    to index IDs in the path.

    Args:
        path (str): Hubit user path
        input_data (Dict): Input data

    Returns:
        Any: None if no index IDs found in 'path' else list og lengths
    """
    idxids = idxids_from_path(path)
    
    # Handle no index IDs
    if len(idxids) == 0: 
        return None, None

    # Handle all IDs are digits 
    if all([idxid.isdigit() for idxid in idxids]): 
        return [], [path]

    connecting_paths = _paths_between_idxids(path, idxids)
    return _length_for_iterpaths(connecting_paths, input_data)


def idxids_from_path(path: str) -> List[str]:
    """Get the index identifiers (in square braces) from a Hubit 
    user path string

    Args:
        path (str): Hubit user path string

    Returns:
        List: Sequence of index identification strings
    """
    # return re.findall(r"\[(\w+)\]", path) # Only word charaters i.e. [a-zA-Z0-9_]+
    return re.findall(r"\[(.*?)\]", path) # Any character in square brackets
    

def _paths_between_idxids(path: str, idxids: List[str]) -> List[str]:
    """Find list of path components inbetween index IDs

    Args:
        path (str): Hubit user path string
        idxids (List[str]): Sequence of index identification strings in 'path'

    Returns:
        List[str]: Sequence of index identification strings between index IDs
    """
    # Remove [] and replace with ..
    p2 = convert_to_internal_path(path)
    paths = []
    for idxid in idxids:
        # Split at current index ID
        p1, p2 = p2.split(idxid, 1)
        # Remove leading and trailing
        paths.append(p1.rstrip('.').lstrip('.'))
    return paths


def reshape(pstrs, valmap):
    """
    pstrs contains path strings in the correct shape i.e. a nested list. 
    Even a simple number is a list of one element due to the expansion. 
    If only one element return that element i.e. the value. Else collect the 
    values from the value map an store them in a nested list structure like
    pstrs.
    """
    if len(pstrs) > 1:
        return [valmap[pstr] 
               if isinstance(pstr, basestring) 
               else reshape(pstr, valmap) 
               for pstr in pstrs]
    else:
        return valmap[pstrs[0]]
        

def traverse(items):
    """
    Iterate nested list. Stop iteration if string elements are encountered 
    """
    try:
        for i in iter(items):
            if not isinstance(i, basestring):
                for j in traverse(i):
                    yield j
            else:
                yield i
    except TypeError:
        yield items


def set_element(data, value, indices):
    """
    Set the "value" on the "data" (nested list) at the 
    "indices" (list of indices)
    """
    _data = data
    # Loop over indices excluding last and point to list
    # at an increasingly deeper level of the 
    for idx in indices[:-1]:
        _data = _data[idx]
    # _data is now the innermost list where the values should be set
    _data[indices[-1]] = value
    return data


def get_nested_list(maxilocs):
    """
    Create nested list with all values set to None.
    Dimensions given in "maxilocs" which are the max element number ie zero-based
    """
    empty_list = None
    for n in maxilocs[::-1]:
        empty_list = [copy.deepcopy(empty_list) for _ in range(n + 1)]
    return empty_list


def list_from_shape(shape):
    """
    Create nested list with all values set to None.
    Dimensions given in "shape". shape = 1 results in a number 
    """
    empty_list = None
    for n in shape[::-1]:
        if n > 1:
            empty_list = [copy.deepcopy(empty_list) for _ in range(n)]
        else:
            empty_list = copy.deepcopy(empty_list)
    return empty_list


def inflate(d, sep="."):
    """
    https://gist.github.com/fmder/494aaa2dd6f8c428cede
    TODO: expands lists as dict... No functional importance but would be nice to fix
    """
    items = dict()
    for k, v in d.items():
        keys = k.split(sep)
        sub_items = items
        for ki in keys[:-1]:
            _ki = int(ki) if ki.isdigit() else ki
            try:
                sub_items = sub_items[_ki]
            except KeyError:
                sub_items[_ki] = dict()
                sub_items = sub_items[_ki]
        
        k_last = keys[-1]
        k_last = int(k_last) if k_last.isdigit() else k_last
        sub_items[keys[-1]] = v

    return items


def flatten(d, parent_key='', sep='.'):
    """
    Flattens dict and concatenates keys 
    Modified from: https://stackoverflow.com/questions/6027558/flatten-nested-python-dictionaries-compressing-keys
    """
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.abc.MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        elif isinstance(v, collections.abc.Iterable) and not isinstance(v, basestring):
            try:
                # Elements are dicts
                for idx, item in enumerate(v):
                    _new_key = new_key + '.' + str(idx)
                    items.extend(flatten(item, _new_key, sep=sep).items())
            except AttributeError:
                # Elements are not dicts
                items.append((new_key, v))
        else:
            items.append((new_key, v))
    return dict(items)


def set_ilocs_on_pathstr(pathstr, ilocs, ilocstr):
    """
    Replace the ilocstr on the path string with location indices 
    in ilocs
    """
    _pathstr = copy.copy(pathstr)
    for iloc in ilocs:
        _pathstr = _pathstr.replace(ilocstr, iloc, 1)
    return _pathstr


def check_path_match(query_path, symbolic_path, ilocstr):
    query_path_cmps = query_path.split('.')
    symbolic_path_cmps = symbolic_path.split('.')
    # Should have same number of path components
    if not len(query_path_cmps) == len(symbolic_path_cmps): return False
    for qcmp, scmp in zip(query_path_cmps, symbolic_path_cmps):

        if qcmp.isdigit():
            # When a digit is found in the query either an ilocstr, 
            # a wildcard or a digit should be found in the symbolic path
            if not (scmp == ilocstr or scmp == ':' or scmp.isdigit()):
                return False    
        else:
            # If not a digit the path components should be identical
            if not qcmp == scmp:
                return False
    return True


def idxs_for_matches(query_path, symbolic_paths, ilocstr):
    """
    Returns indices in the sequence of provider strings that match the 
    strucure of the query string
    """
    return [idx 
            for idx, symbolic_path in enumerate(symbolic_paths) 
            if check_path_match(query_path, symbolic_path, ilocstr)]


def get_iloc_indices(query_path, symbolic_path, ilocstr):
    """
    List indices extracted from query based on location of 
    ilocstr in providerstring
    """
    return [qcmp for qcmp, scmp in zip(query_path.split('.'),
                                       symbolic_path.split('.'))          
            if scmp == ilocstr]

# def expand_query(querystr, flat_input):
# NEW VERSION using [] instead of ..
#     #TODO: change so we dont need to inflate again
#     input_data = inflate(flat_input)
#     lengths, paths = lengths_for_path(querystr, input_data)

#     # Assume rectangular data and convert from length to max index
#     maxilocs = [items[0] - 1 for items in lengths]

#     return paths, maxilocs


def expand_query(querystr, flat_input):
    """
    querystr = "segs.:.walls.temps"
    all_input = {"segs.0.walls.temps" : 1, "segs.1.walls.temps" : 2, "segs.2.walls.temps" : None}
    result = "segs.0.walls.temps", "segs.1.walls.temps", "segs.2.walls.temps"
    """
    sepstr = "."
    wcstr = ":"
    querycmps = querystr.split(sepstr)
    # print 'querycmps', querycmps
    # At which indices are the wildcard encountered
    wcidxs = [idx for idx, qcmp in enumerate(querycmps) if qcmp == wcstr]
    # print 'wcidxs', wcidxs
    # Find maximal iloc for the indices with wildcards
    maxilocs = []
    for icount, cmpidx in enumerate(wcidxs):
        for pathstr in flat_input.keys():
            pathcmps = pathstr.split(sepstr)
            # print 'pathcmps', pathcmps
            try:
                pathcmp = int(pathcmps[cmpidx])
            except IndexError: # too few components in path
                continue
            except ValueError: # cannot cast component to int
                continue
                
            try:
                maxilocs[icount] = max(pathcmp, maxilocs[icount])
            except IndexError:
                maxilocs.append(pathcmp)

    # Make all query combinations
    queries = []
    for ilocs in itertools.product(*[range(maxval + 1) for maxval in maxilocs]):
        queries.append(set_ilocs_on_pathstr(querystr, [str(iloc) for iloc in ilocs], wcstr))

    return queries, maxilocs

def query_all(providerstrings, flat_input, ilocstr):
    """
    Assumes complete input
    """
    return [qry 
            for pstr in providerstrings
            for qry in expand_query(pstr.replace(ilocstr, ":"), flat_input)]
    


def pstr_shape(pstr, inputdata, sepstr, ilocwcchar):
    """
    From the input data infer the shape corresponding to the iloc 
    wildcard character (ilocwcchar) in the pstr.
    Rectagular data assumed.
    """
    nwc = pstr.count(ilocwcchar)
    shape = []
    pcmps = pstr.split(sepstr)
    cidx = 0
    for _ in range(nwc):
        idx = pcmps[cidx:].index(ilocwcchar) 
        cidx += idx
        shape.append(len(get_from_datadict(inputdata, pcmps[:cidx])))
        pcmps[cidx] = '0'

    return shape


def pstr_expand(pstr, shape, ilocwcchar):
    """
    Expand a path string according to the shape. 
    The result is a nested list of path strings
    """
    # pstrs = []
    pstrs = get_nested_list([s-1 for s in shape])
    for ilocs in itertools.product(*[range(nitm) for nitm in shape]):
        #pstrs.append(set_ilocs_on_pathstrpstr, [str(iloc) for iloc in ilocs], ilocwcchar))
        set_element(pstrs, set_ilocs_on_pathstr(pstr, [str(iloc) for iloc in ilocs], ilocwcchar), ilocs)
    return pstrs
