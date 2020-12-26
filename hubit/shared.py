from __future__ import annotations
import re
import copy
import itertools
import collections
from functools import reduce
from operator import getitem
from typing import Any, List, Dict, Tuple


IDX_WILDCARD = ":"


class HubitError(Exception):
    pass


class HubitIndexError(HubitError):
    pass


class LengthNode:
    def __init__(self, nchildren: int):
        """A node in the length tree i.e. a generalized 
        shape for non-rectagular data.

        Args:
            nchildren (int): Number of children. Equivalent to the number of 
            indices for the current node.
        """
        self.level = 0
        # Assume bottom level (children = None)
        self.children = [None for _ in range(nchildren)]

        # Assume top level (children = None)
        self.parent = None
        self.tree = None
        
        # Stores index in parent's list of children
        self.index = None 

    def nchildren(self) -> int:
        return len(self.children)


    def set_children(self, children: List[LengthNode]):
        self.children = list(children)
        for idx, child in enumerate(self.children):
            child.parent = self
            child.level = self.level + 1
            child.index = idx


    def remove(self):
        """remove node 
        """
        if self.parent is None:
            raise HubitIndexError

        self.remove_decendants()
        self.parent.children.remove(self)
        if self.parent.nchildren() == 0:
            self.parent.remove()
        self.tree.nodes_for_level[self.level].remove(self)


    def pop_child_for_idx(self, idx):
        child = self.children[idx]
        if child is not None:
            # Not the bottom-most level
            child.remove_decendants()
            self.tree.nodes_for_level[self.level + 1].remove(child)
        self.children.pop(idx)


    def remove_decendants(self):
        for child in self.children:
            if child is not None:
                # Remove child from tree
                child.tree.nodes_for_level[child.level].remove(child)
                child.remove_decendants()

    
    def __str__(self):
        return f'LengthNode nchildren={self.nchildren()}, has parent={"Yes" if self.parent else "No"}'


    def __repr__(self):
        return str(self)


class LengthTree:
    """Stores length information for multi-dimensional and non-rectangular 
    data. 
    """

    def __init__(self, nodes: List[LengthNode], level_names: List[str]):
        """A data structure that allows manipulations of connected 
        LengthNodes 

        Args:
            nodes (List[LengthNode]): Connected length nodes
            level_names (List[str]): Name of the levels specified on the nodes
        """
        self.nlevels = len(level_names)
        self.level_names = level_names

        self.nodes_for_level = [[] for idx in range(self.nlevels)]
        for node in nodes:
            node.tree = self
            self.nodes_for_level[node.level].append(node)
    

    def prune_from_path(self, path: str,
                        template_path: str,
                        inplace: bool=True) -> LengthTree:
        """Prune the length tree based on a path where zero
        to all inices are already specified.

        Args:
            path (str): A Hubit internal path with zero to all index IDs replaced by indices
            template_path (str): A Hubit internal path with all relevant index IDs defined
            inplace (bool, optional): If True the instance itself will be pruned. If False a pruned copy will be created. Defaults to True.

        Returns:
            LengthTree: Pruned tree. If inplace=True the instance itself is also pruned.
        """

        obj = self if inplace else copy.deepcopy(self)

        # Loop over the index ID levels
        for level_idx, level_name in enumerate(obj.level_names):
            # Check in the index is fixed i.e. if the index ID is missing
            if not level_name in path:
                # Get fixed index from path
                idx = int(get_iloc_indices(path,
                                           template_path,
                                           f':@{level_name}')[0])

                # Prune the tree to reflex that the index is fixed
                obj.fix_idx_at_level(idx, level_idx)

        return obj


    def fix_idx_at_level(self, idx_value: int, level_idx: int):
        """Fix the nodes at level_idx to the value idx

        Args:
            idx_value (int): Index value to be set.  
            level_idx (int): Level index

        Raises:
            HubitIndexError: Raise of the specified idx_value cannot be provided 
        """
        nodes_to_be_deleted = []
        for node in self.nodes_for_level[level_idx]:
            # Keep child corresponding to idx  remove the rest
            idx_others = list(range(node.nchildren()))
            if idx_value in idx_others:
                # idx can be provided
                idx_others.remove(idx_value)
                for idx_other in reversed(idx_others):
                    node.pop_child_for_idx(idx_other)
            else:
                nodes_to_be_deleted.append(node)

        for node in nodes_to_be_deleted:
            try:
                node.remove()
            except HubitIndexError:
                raise HubitIndexError(f'Cannot find index {idx_value} for index ID {self.level_names[level_idx]}')


    def to_list(self):
        """Convert length tree to nested lists for testing puposes

        Returns:
            List: Nested lists representing the length tree
        """
        idx_vals = [[node.nchildren() for node in nodes] 
                    for nodes in self.nodes_for_level]

        size_for_level = []
        size_for_level = [ idx_vals[0][0] ]
        for idx, vals in enumerate(idx_vals[1:], 1):

            # Loop over levels above (excluding level 0) and incrementally 
            # divide list into sub-lists
            for sizes in idx_vals[1:idx][::-1]:
                # Cast to list in case of an integer
                vals = split_items(vals, traverse([sizes]))

            if len(vals) == 1:
                vals = vals[0]

            size_for_level.append(vals)

        return size_for_level

    @staticmethod
    def _nodes_for_iterpaths(connecting_paths: List[str],
                             data: Dict,
                             nodes=None,
                             paths_previous=None,
                             parent: LengthNode=None) -> Tuple:
        """Lengths 

        Args:
            connecting_paths (List[str]): Sequence of index identification strings between index IDs
            data (Dict): Input data 
            nodes (List[LengthNode], optional): Cummulative list of nodes. Defaults to None.
            paths_previous (List, optional): Hubit internal paths found in 
            previous level of recusion with explicit indeices. Defaults to None.
            parent (LengthNode, optional): Parent node

        Returns:
            Tuple: Two-tuple list of nodes, paths_previous
        """
        sep = '.'
        paths_previous = paths_previous or [connecting_paths[0]]
        nodes = nodes or []

        # Get node list for paths prepared at the previous recusion level
        child_nodes = [ LengthNode(len( get_from_datadict(data, path.split(sep))))
                               for path in paths_previous ]

        if parent is not None:
            parent.set_children(child_nodes)

        nodes.extend(child_nodes)

        paths_next = paths_previous
        if len(connecting_paths) > 1:
            # Prepare paths for next recursive call by appending the 
            # indices (from out_current_level) and the connecting path 
            # to the previosly found paths
            for node, path_previous in zip(child_nodes, paths_previous):
                paths_next = ['{}.{}.{}'.format(path_previous, curidx, connecting_paths[1]) 
                              for curidx in range(node.nchildren())]

                # Call again for next index ID
                nodes, paths_next = LengthTree._nodes_for_iterpaths(connecting_paths[1:],
                                                                    data,
                                                                    nodes=nodes,
                                                                    parent=node,
                                                                    paths_previous=paths_next)

        elif len(connecting_paths) == 1:
            for node, path_previous in zip(child_nodes, paths_previous):
                paths_next = ['{}.{}'.format(path_previous, curidx) 
                               for curidx in range(node.nchildren())]

        return nodes, paths_next


    @classmethod
    def from_data(cls, path:str, data: dict) -> Any:
        """Infer lengths of lists in 'input_data' that correspond 
        to index IDs in the path.

        Args:
            path (str): Hubit user path
            input_data (Dict): Input data

        Returns:
            Tuple: Element 0 is None if no index IDs found in 'path' 
            else a LengthTree. Element 1 is a list of all paths from 
            the 'expansion'.
        """
        level_names = idxids_from_path(path)
        clean_level_names = [idxid.split('@')[1] if '@' in idxid 
                             else idxid
                             for idxid in level_names]
        
        # Handle no index IDs
        if len(level_names) == 0: 
            return None, None

        # Handle all IDs are digits 
        if all([is_digit(level_name) for level_name in level_names]): 
            return None, [path]

        connecting_paths = _paths_between_idxids(path, level_names)
        nodes, paths = LengthTree._nodes_for_iterpaths(connecting_paths[:-1], data)
        if not connecting_paths[-1] == '':
            paths = ['{}.{}'.format(path, connecting_paths[-1]) for path in paths]

        tree = cls(nodes, clean_level_names)

        return tree, paths


    def expand_path(self, path: str):
        """Expand path with wildcard based on tree

        Args:
            path (str): Hubit internal path with wildcards

        Returns:
            [List]: Paths arranged in the shape defined by the tree 
        """
        # Expand the path (and do some pruning)
        paths = [path]

        for idx_level, level_name in enumerate(self.level_names):
            nodes = self.nodes_for_level[idx_level]
            paths_current_level = []
            for path, node in zip(paths, nodes):
                paths_current_level.extend([path.replace(f':@{level_name}', str(child.index if child is not None else idx)) 
                                            for idx, child in enumerate(node.children)])

            paths = paths_current_level

        # TODO: rewrite as no not use the list version of the tree object
        as_list = self.to_list()
        for sizes in reversed(as_list):
            try:
                if len(sizes) < 1: continue
            except TypeError:
                # not a list so not need to split
                continue 

            # Don't add a level if all have only one child 
            if all([size == 1 for size in sizes]): continue

            paths = split_items(paths, list(traverse(sizes)))

        return paths


    def __eq__(self, other):
        return self.to_list() == other.to_list()


    def __str__(self):
        lines = ['--------------------',
                 'Tree']
        for idx, (name, nodes) in enumerate(zip(self.level_names, self.nodes_for_level)):
            nparents = len({node.parent for node in nodes if node.parent is not None})
            nchildren = sum( [node.nchildren() for node in nodes] )
            lines.append(f'level={idx} ({name}), nodes={len(nodes)}, parents={nparents}, children={nchildren}')

        lines.append('--------------------')
        lines.append('Lengths')

        size_for_level = self.to_list()

        for idx, (name, size) in enumerate(zip(self.level_names,
                                               size_for_level)):
            lines.append(f'level={idx} ({name}), {size}')

        return '\n'.join(lines)


class Container:

    def __init__(self, val):
        self.val = val


    def __str__(self):
        return str(self.val)


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
    except ValueError:
        return  False


def get_from_datadict(datadict, keys):
    """
    Extract value from a nested dictionary using list of keys.
    datadict is a dict. keys is a list of keys (strings).
    """
    # Convert digits strings to int
    _keys = [int(key) if is_digit(key) else key for key in keys]
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
        print(paths_previous)
        # Prepare paths for next recursive call by appending the 
        # indices (from out_current_level) and the connecting path 
        # to the previosly found paths
        paths_next = ['{}.{}.{}'.format(path_previous, curidx, connecting_paths[1]) 
                        for length, path_previous in zip(out_current_level, paths_previous)
                        for curidx in range(length)]
        # print(paths_next)
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
    clean_idxids = [idxid.split('@')[1] if '@' in idxid 
                    else idxid
                    for idxid in idxids]
    
    # Handle no index IDs
    if len(idxids) == 0: 
        return None, None

    # Handle all IDs are digits 
    if all([is_digit(idxid) for idxid in idxids]): 
        return [], [path]

    connecting_paths = _paths_between_idxids(path, idxids)
    lengths, paths = _length_for_iterpaths(connecting_paths[:-1], input_data)
    if not connecting_paths[-1] == '':
        paths = ['{}.{}'.format(path, connecting_paths[-1]) for path in paths]
    return tuple(zip(clean_idxids, lengths)), paths


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
        List[str]: Sequence of index identification strings between index IDs. Includes path after last index ID
    """
    # Remove [] and replace with ..
    p2 = convert_to_internal_path(path)
    paths = []
    for idxid in idxids:
        # Split at current index ID
        p1, p2 = p2.split(idxid, 1)
        # Remove leading and trailing
        paths.append(p1.rstrip('.').lstrip('.'))
    paths.append(p2.rstrip('.').lstrip('.'))
    return paths


def reshape(paths, valmap):
    """
    paths contains path strings in the correct shape i.e. a nested list. 
    Even a simple number is a list of one element due to the expansion. 
    If only one element return that element i.e. the value. Else collect the 
    values from the value map an store them in a nested list structure like
    paths.
    """
    if len(paths) > 1:
        return [valmap[path] 
               if isinstance(path, str) 
               else reshape(path, valmap) 
               for path in paths]
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
            _ki = int(ki) if is_digit(ki) else ki
            try:
                sub_items = sub_items[_ki]
            except KeyError:
                sub_items[_ki] = dict()
                sub_items = sub_items[_ki]
        
        k_last = keys[-1]
        k_last = int(k_last) if is_digit(k_last) else k_last
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
        elif isinstance(v, collections.abc.Iterable) and not isinstance(v, str):
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


def set_ilocs_on_path(path, ilocs, ilocstr):
    """
    Replace the ilocstr on the path with location indices 
    in ilocs
    """
    _path = copy.copy(path)
    for iloc in ilocs:
        _path = _path.replace(ilocstr, iloc, 1)
    return _path


def check_path_match(query_path, symbolic_path, ilocstr):
    query_path_cmps = query_path.split('.')
    symbolic_path_cmps = symbolic_path.split('.')
    # Should have same number of path components
    if not len(query_path_cmps) == len(symbolic_path_cmps): return False
    for qcmp, scmp in zip(query_path_cmps, symbolic_path_cmps):

        if is_digit(qcmp):
            # When a digit is found in the query either an ilocstr, 
            # a wildcard or a digit should be found in the symbolic path
            if not (scmp == ilocstr or scmp == ':' or is_digit(scmp)):
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
    return tuple([qcmp for qcmp, scmp in zip(query_path.split('.'),
                                             symbolic_path.split('.'))          
            if scmp == ilocstr or scmp == IDX_WILDCARD])

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
    # At which indices are the wildcard encountered
    wcidxs = [idx for idx, qcmp in enumerate(querycmps) if qcmp == wcstr]
    # Find maximal iloc for the indices with wildcards
    maxilocs = []
    for icount, cmpidx in enumerate(wcidxs):
        for path in flat_input.keys():
            pathcmps = path.split(sepstr)
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
        queries.append(set_ilocs_on_path(querystr, [str(iloc) for iloc in ilocs], wcstr))

    return queries, maxilocs


def query_all(providerstrings, flat_input, ilocstr):
    """
    Assumes complete input
    """
    return [qry 
            for path in providerstrings
            for qry in expand_query(path.replace(ilocstr, ":"), flat_input)]
    


def path_shape(path, inputdata, sepstr, ilocwcchar):
    """
    From the input data infer the shape corresponding to the iloc 
    wildcard character (ilocwcchar) in the path.
    Rectagular data assumed.
    """
    nwc = path.count(ilocwcchar)
    shape = []
    pcmps = path.split(sepstr)
    cidx = 0
    for _ in range(nwc):
        idx = pcmps[cidx:].index(ilocwcchar) 
        cidx += idx
        shape.append(len(get_from_datadict(inputdata, pcmps[:cidx])))
        pcmps[cidx] = '0'

    return shape


def path_expand(path, shape, ilocwcchar):
    """
    Expand a path string according to the shape. 
    The result is a nested list of path strings
    """
    paths = get_nested_list([s-1 for s in shape])
    for ilocs in itertools.product(*[range(nitm) for nitm in shape]):
        #pstrs.append(set_ilocs_on_pathstrpstr, [str(iloc) for iloc in ilocs], ilocwcchar))
        set_element(paths, set_ilocs_on_path(path, [str(iloc) for iloc in ilocs], ilocwcchar), ilocs)
    return paths


def set_nested_item(data, keys, val):
    """Set item in nested dictionary"""
    reduce(getitem, keys[:-1], data)[keys[-1]] = val
    return data


def get_nested_item(data, keys):
    return reduce(getitem, keys, data)


def expand_new(path: str, template_path: str, all_lengths: List):
    """Expand path with wildcard based on lengths in "all_lengths"

    Args:
        path (str): Hubit internal path with wildcards
        template_path (str): Hubit internal path corresponding to paths with all wildcards present
        all_lengths (List): Lengths object from "lengths_for_path"

    Returns:
        [List]: Paths arranged in the correct shape according to all_lengths
    """
    nlevels = len(all_lengths)
    _all_lengths = copy.copy(all_lengths)
    print(_all_lengths)
    print(path)
    # Prune length tree if some levels are fixed in path
    fixed_idx_for_level = {}
    for level in range(nlevels):
        idxid_current, _ = _all_lengths[level]
        print(_all_lengths)
        if not idxid_current in path:
            # Get fixed index from path
            idx = int(get_iloc_indices(path,
                                       template_path,
                                       f':@{idxid_current}')[0])
            fixed_idx_for_level[level] = idx

            # The current level is fixed so level above
            _all_lengths[level-1][1] = [1]
            # At all levels from below the current level keep only data 
            # corrensponding to the fixed index
            print('XXXX', _all_lengths)
            for idx_level, (_, sizes) in enumerate(_all_lengths[level+1:], start=level+1):
                print(sizes)
                _all_lengths[idx_level][1] = sizes[idx]

    print('final', _all_lengths)
    # Expand the path (and do some pruning)
    paths = [path]
    for level in range(nlevels):
        idxid_current, lengths = _all_lengths[level]
        paths_current_level = []
        # did_break = False
        for path, length in zip(paths, list(traverse(lengths))):

            if not level in fixed_idx_for_level:
                paths_current_level.extend([path.replace(f':@{idxid_current}', str(idx)) 
                                           for idx in range(length)])
            else:
                idx = fixed_idx_for_level[level]
                # print(_all_lengths)
                paths_current_level = paths

                if idx >= length:
                    # The fixed index is not legal in the context of indices above
                    paths_current_level.remove(path)

                    # Get all indices above the illegal path 
                    idxs = [int(get_iloc_indices(path,
                                                 template_path,
                                                 f':@{_all_lengths[lev][0]}')[0]) 
                            for lev in range(level+1)] 

                    # We need to subtract one element in the size tree node above the illegal path
                    # Indices to level above illegal path
                    idxs = idxs[:-1]
                    sizes_at_level = _all_lengths[level][1]
                    if isinstance(sizes_at_level, int):
                        val = sizes_at_level 
                    else:
                        val = get_nested_item(sizes_at_level, idxs)
    
                    if val > 1:
                        set_nested_item(sizes_at_level, idxs, val - 1)
                    else:
                        if isinstance(sizes_at_level, int):
                            _all_lengths[level-1][1] -= 1
                        else:
                            items = get_nested_item(sizes_at_level, idxs[:-1])
                            print(items)
                            items.pop(idxs[-1])
                            print(items)
                            set_nested_item(sizes_at_level, idxs[:-1], items)
                            print(_all_lengths)

                    break

        paths = paths_current_level

    print('_all_lengths', _all_lengths)
    for _, sizes in reversed(_all_lengths):
        print('sizes 1', sizes)
        try:
            if len(sizes) < 1: continue
        except TypeError:
            # not a list so not need to split
            continue 

        print('sizes', sizes)
        paths = split_items(paths, list(traverse(sizes)))

    return paths


def split_items(items, sizes):
    """Split the items into a list each with 

    Args:
        items ([type]): [description]
        sizes ([type]): [description]

    Returns:
        [type]: [description]
    """
    it = iter(items)
    return [list(itertools.islice(it, 0, size)) for size in sizes]

