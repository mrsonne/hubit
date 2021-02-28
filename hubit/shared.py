from __future__ import annotations
import re
import copy
import itertools
import collections
from functools import reduce
from operator import getitem
from typing import Any, List, Dict, Tuple
from dataclasses import dataclass

from .errors import HubitIndexError, HubitWorkerError

IDX_WILDCARD = ":"
REGEX_IDXID = r"\[(.*?)\]"


@dataclass
class HubitModelComponent:
    def _validate(self):
        return True


@dataclass
class HubitModelConfig:
    components: List[HubitWorkerError]

    def _validate(self):
        return True


class HubitModelPath(str):
    def __init__(self, path: str):
        self.path = path

    def _validate(self):
        return True


class HubitPath(str):
    path: str

    def _validate(self):
        return True


class HubitQuery(HubitPath):
    query: List[HubitPath]

    def _validate(self):
        return True


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
        """remove node"""
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
        self.children = [None for _ in range(len(self.children))]

    def __str__(self):
        return f'LengthNode nchildren={self.nchildren()}, has parent={"Yes" if self.parent else "No"}'

    def __repr__(self):
        return str(self)


class DummyLengthTree:
    """Dummy tree for"""

    def __init__(self, *args, **kwargs):
        self.level_names = []

    def get_idx_context(self):
        return "-".join(self.level_names)

    def prune_from_path(self, *args, **kwargs) -> DummyLengthTree:
        return self

    def clip_at_level(self, inplace: bool = True, *args, **kwargs) -> DummyLengthTree:
        return self if inplace else copy.deepcopy(self)

    def fix_idx_at_level(self, *args, **kwargs):
        pass

    def expand_path(self, path: str, *args, **kwargs) -> List[str]:
        return [path]

    def none_like(self):
        return None


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

    def get_idx_context(self):
        return "-".join(self.level_names)

    def clip_at_level(self, level_name: str, inplace: bool = True) -> LengthTree:
        """Remove level below 'level_name'

        Args:
            level_name (str): Name of deepest level to include. Levels below will be remove
            inplace (bool, optional): If True the instance itself will be clipped. If False a clipped copy will be created. Defaults to True.

        Returns:
            LengthTree: Clipped tree
        """
        obj = self if inplace else copy.deepcopy(self)
        level_idx = obj.level_names.index(level_name)
        for node in obj.nodes_for_level[level_idx]:
            node.remove_decendants()
        obj.level_names = obj.level_names[: level_idx + 1]
        obj.nodes_for_level = obj.nodes_for_level[: level_idx + 1]
        return obj

    def prune_from_path(
        self, path: str, template_path: str, inplace: bool = True
    ) -> LengthTree:
        """Prune the length tree based on a path where zero
        to all inices are already specified.

        TODO: id the path used [] the model path is not required

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
                idxstr = get_iloc_indices(path, template_path, [f"{level_name}"])[0]

                if idxstr == IDX_WILDCARD:
                    continue

                idx = int(idxstr)
                # Prune the tree to reflect that the index is fixed
                obj.fix_idx_at_level(idx, level_idx)

        return obj

    def fix_idx_at_level(self, idx_value: int, level_idx: int, inplace: bool = True):
        """Fix the nodes at level_idx to the value idx

        Args:
            idx_value (int): Index value to be set.
            level_idx (int): Level index
            inplace (bool, optional): If True the instance itself will be modified. If False a copy will be created. Defaults to True.

        Raises:
            HubitIndexError: Raise of the specified idx_value cannot be provided

        Returns:
            LengthTree: Fixed tree. If inplace=True the instance itself is also modified.
        """
        obj = self if inplace else copy.deepcopy(self)
        nodes_to_be_deleted = []
        for node in obj.nodes_for_level[level_idx]:
            # Keep child corresponding to idx remove the rest
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
                raise HubitIndexError(
                    f"Cannot find index {idx_value} "
                    f"for index ID {obj.level_names[level_idx]}"
                )
        return obj

    def to_list(self):
        """Convert length tree to nested lists for testing puposes

        Returns:
            List: Nested lists representing the length tree
        """
        idx_vals = [
            [node.nchildren() for node in nodes] for nodes in self.nodes_for_level
        ]

        size_for_level = []
        size_for_level = [idx_vals[0][0]]
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
    def _nodes_for_iterpaths(
        connecting_paths: List[str],
        data: Dict,
        nodes=None,
        paths_previous=None,
        parent: LengthNode = None,
    ) -> Tuple:
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
        sep = "."
        paths_previous = paths_previous or [connecting_paths[0]]
        nodes = nodes or []

        # Get node list for paths prepared at the previous recusion level
        child_nodes = [
            LengthNode(len(get_from_datadict(data, path.split(sep))))
            for path in paths_previous
        ]

        if parent is not None:
            parent.set_children(child_nodes)

        nodes.extend(child_nodes)

        paths_next = paths_previous
        if len(connecting_paths) > 1:
            # Prepare paths for next recursive call by appending the
            # indices (from out_current_level) and the connecting path
            # to the previosly found paths
            for node, path_previous in zip(child_nodes, paths_previous):
                paths_next = [
                    "{}.{}.{}".format(path_previous, curidx, connecting_paths[1])
                    for curidx in range(node.nchildren())
                ]

                # Call again for next index ID
                nodes, paths_next = LengthTree._nodes_for_iterpaths(
                    connecting_paths[1:],
                    data,
                    nodes=nodes,
                    parent=node,
                    paths_previous=paths_next,
                )

        elif len(connecting_paths) == 1:
            for node, path_previous in zip(child_nodes, paths_previous):
                paths_next = [
                    "{}.{}".format(path_previous, curidx)
                    for curidx in range(node.nchildren())
                ]

        return nodes, paths_next

    @classmethod
    def from_data(cls, path: str, data: dict) -> Any:
        """Infer lengths of lists in 'input_data' that correspond
        to index IDs in the path.

        Args:
            path (str): Hubit model path
            input_data (Dict): Input data

        Returns:
            LengthTree: Element 0 is DummyLengthTree if no index IDs found in 'path'
            otherwise a LengthTree.
        """
        level_names = idxids_from_path(path)
        clean_level_names = [
            idxid.split("@")[1] if "@" in idxid else idxid for idxid in level_names
        ]
        # Handle no index IDs
        if len(level_names) == 0:
            return DummyLengthTree()

        # Handle all IDs are digits
        if all([is_digit(level_name) for level_name in level_names]):
            return DummyLengthTree()

        connecting_paths = _paths_between_idxids(path, level_names)
        nodes, paths = LengthTree._nodes_for_iterpaths(connecting_paths[:-1], data)
        if not connecting_paths[-1] == "":
            paths = ["{}.{}".format(path, connecting_paths[-1]) for path in paths]

        tree = cls(nodes, clean_level_names)

        # Some path indices may have specific locations some prune the tree
        new_idxitems = []
        for idxitem in idxids_from_path(path):
            iloc = idxitem.split("@")[0]
            if is_digit(iloc):
                new_idxitems.append(iloc)
            else:
                new_idxitems.append(idxitem)

        new_model_path = set_ilocs_on_path(path, new_idxitems)
        new_internal_path = convert_to_internal_path(new_model_path)
        tree.prune_from_path(new_internal_path, convert_to_internal_path(path))
        return tree

    def reshape(self, items: List, inplace: bool = True) -> List:
        """Reshape items according to the shape defined by the tree

        Args:
            items (List): Flat list of to be reshaped
            inplace (bool): If True the specified list will be reshaped.
            If False a copy will be created and reshaped.

        Returns:
            List: [description]
        """
        _items = items if inplace else copy.deepcopy(items)
        # TODO: rewrite as no not use the list version of the tree object
        as_list = self.to_list()
        for sizes in reversed(as_list):
            try:
                if len(sizes) < 1:
                    continue
            except TypeError:
                # not a list so not need to split
                continue

            # Don't add a level if all have only one child
            if all([size == 1 for size in sizes]):
                continue

            _items = split_items(_items, list(traverse(sizes)))
        return _items

    def preprocess_query_path(path, *args, **kwargs):
        """
        Dummy preprocessor for query paths
        """
        return path, IDX_WILDCARD

    def preprocess_model_path(path, level_name):
        """
        # Replace string between braces ([*level_name]) with [level_name].
        # # * could be 2@, :@ or nothing

        TODO: remove this old doc
        Replace string between dots (.*level_name.) with .level_name.
        # * could be 2@, :@ or nothing
        """
        # For dot-path
        # pcmps = path.split('.')
        # idxs = [idx for idx, pcmp in enumerate(pcmps) if level_name in pcmp]
        # if len(idxs):
        #     pcmps[idxs[0]] = level_name
        # _path = '.'.join(pcmps)
        # return re.sub("\.([^\.]+){}".format(level_name),
        #                 '.{}'.format(level_name),
        #                 path), level_name
        # For epath
        return (
            re.sub("\[([^\.]+){}]".format(level_name), f"[{level_name}]", path),
            level_name,
        )

    precessor_for_pathtype = {
        "model": preprocess_model_path,
        "query": preprocess_query_path,
    }

    def _node_for_idxs(self, idxs: List[int]):
        """
        Get the node corresponding to a list of indices
        """
        if len(idxs) == 0:
            node = self.nodes_for_level[0][0]
        else:
            node = self.nodes_for_level[0][0].children[idxs[0]]
            for node_idx in idxs[1:]:
                node = node.children[node_idx]
        return node

    def normalize_path(self, qpath: str):
        """Handle negative indices
        As stated in "test_normalize_path2" the normalization in general depends
        on the context
        """

        idxids = idxids_from_path(qpath)
        _path = copy.copy(qpath)

        for idx_level, idxid in enumerate(idxids):
            if is_digit(idxid) and int(idxid) < 0:
                # Get index context i.e. indices prior to current level
                _idx_context = [int(idx) for idx in idxids_from_path(_path)[:idx_level]]
                node = self._node_for_idxs(_idx_context)
                _path = _path.replace(idxid, str(node.nchildren() + int(idxid)), 1)
        return _path

    def expand_path(
        self,
        path: str,
        flat: bool = False,
        path_type: str = "model",
        as_internal_path: bool = False,
    ) -> List[str]:
        """Expand external path with wildcard based on tree

        Example for a query path:
            list[:].some_attr.numbers ->
            [ list[0].some_attr.numbers, list[1].some_attr.numbers, list[2].some_attr.numbers ]


        Args:
            path (str): Hubit internal model path with wildcards and index IDs
            flat (bool): Return expansion result as a flat list.
            path_type (str): The path type. Valid path types are 'model' and 'query'. Not checked.
            as_internal_path (bool): Return expansion result as internal paths

        Returns:
            [List]: Paths from expansion. Arranged in the shape
            defined by the tree if flat = False. Otherwise a
            flat list.
        """
        # Get the appropriate path preprocessor
        path_preprocessor = LengthTree.precessor_for_pathtype[path_type]

        # Get the content of the braces
        idxids = idxids_from_path(path)

        # Expand the path (and do some pruning)
        paths = [path]
        for idx_level, (level_name, idxid) in enumerate(zip(self.level_names, idxids)):
            nodes = self.nodes_for_level[idx_level]
            paths_current_level = []

            if path_type == "query" and not IDX_WILDCARD in idxid:
                # for query paths we only look for IDX_WILDCARD (tgtstr)
                # and therefor cannot handle fixed ilocs. For list[0].some_attr.numbers[:]
                # the first level in the tree will have one child which would erroneously
                # be inserted at the numbers wildcard
                continue

            for _path, node in zip(paths, nodes):

                _path, tgtstr = path_preprocessor(_path, level_name)

                # Replace tgtstr with indices of children. Only replace first occurence
                # from left since query strings may have multiple index wildcards (:)
                paths_current_level.extend(
                    [
                        _path.replace(
                            tgtstr, str(child.index if child is not None else idx), 1
                        )
                        for idx, child in enumerate(node.children)
                    ]
                )

            paths = paths_current_level

        if as_internal_path:
            paths = [convert_to_internal_path(path) for path in paths]

        if flat:
            return paths
        else:
            return self.reshape(paths)

    def none_like(self):
        """Create nested lists in the shape of the tree
        filled with None

        Returns:
            List: Nested list with None
        """
        nitems = sum([node.nchildren() for node in self.nodes_for_level[-1]])
        return self.reshape([None for _ in range(nitems)])

    def __eq__(self, other):
        return self.to_list() == other.to_list()

    def __str__(self):
        lines = ["--------------------", "Tree"]
        for idx, (name, nodes) in enumerate(
            zip(self.level_names, self.nodes_for_level)
        ):
            nparents = len({node.parent for node in nodes if node.parent is not None})
            nchildren = sum([node.nchildren() for node in nodes])
            children_is_none = [
                all([child is None for child in node.children]) for node in nodes
            ]
            lines.append(
                f"level={idx} ({name}), "
                f"nodes={len(nodes)}, "
                f"parents={nparents}, "
                f"children={nchildren}, "
                f"children_is_none={children_is_none}"
            )

        lines.append("--------------------")
        lines.append("Lengths")

        size_for_level = self.to_list()

        for idx, (name, size) in enumerate(zip(self.level_names, size_for_level)):
            lines.append(f"level={idx} ({name}), {size}")

        return "\n".join(lines)


class Container:
    def __init__(self, val):
        self.val = val

    def __str__(self):
        return str(self.val)


def tree_for_idxcontext(components: List, data: Dict) -> Dict[str, LengthTree]:
    """Compute LengthTree for relevant index contexts.

    Args:
        components (List[Componet]): List of Hubit components
        data (Dict): Input data

    Returns:
        Dict: LengthTree for relevant index contexts
    """
    out = {"": DummyLengthTree()}
    for component in components:
        for binding in component["consumes"]["input"]:
            tree = LengthTree.from_data(binding["path"], data)
            idx_context = get_idx_context(binding["path"])
            if idx_context in out.keys():
                continue
            out[idx_context] = tree

    # Clip trees to generate trees for (all) shallower index contexts
    for tree in copy.deepcopy(list(out.values())):
        for level_name in tree.level_names[:-1]:
            new_tree = tree.clip_at_level(level_name, inplace=False)
            idx_context = new_tree.get_idx_context()
            if idx_context in out.keys():
                continue
            out[idx_context] = new_tree

    return out


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
        return False


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
    return path.replace("[", ".").replace("]", "")


def _length_for_iterpaths(
    connecting_paths: List[str], input_data: Dict, out=None, paths_previous=None
) -> Tuple:
    """Lengths

    Args:
        connecting_paths (List[str]): Sequence of index identification strings between index IDs
        input_data (Dict): Input data
        out (List, optional): Lengths found in previous level of recusion. Defaults to None.
        paths_previous (List, optional): Hubit internal paths found in previous level of recusion with explicit indeices. Defaults to None.

    Returns:
        Tuple: Two-tuple out, paths_previous
    """
    sep = "."
    paths_previous = paths_previous or [connecting_paths[0]]
    out = out or []

    # Get list lengths for paths prepared at the previous recusion level
    out_current_level = [
        len(get_from_datadict(input_data, path.split(sep))) for path in paths_previous
    ]

    out.append(out_current_level)

    paths_next = paths_previous
    if len(connecting_paths) > 1:
        # print(paths_previous)
        # Prepare paths for next recursive call by appending the
        # indices (from out_current_level) and the connecting path
        # to the previosly found paths
        paths_next = [
            "{}.{}.{}".format(path_previous, curidx, connecting_paths[1])
            for length, path_previous in zip(out_current_level, paths_previous)
            for curidx in range(length)
        ]
        # print(paths_next)
        # Call again for next index ID
        out, paths_next = _length_for_iterpaths(
            connecting_paths[1:], input_data, out=out, paths_previous=paths_next
        )

    elif len(connecting_paths) == 1:
        paths_next = [
            "{}.{}".format(path_previous, curidx)
            for length, path_previous in zip(out_current_level, paths_previous)
            for curidx in range(length)
        ]

    return out, paths_next


def idxids_from_path(path: str) -> List[str]:
    """Get the index identifiers (in square braces) from a Hubit
    model path string

    Args:
        path (str): Hubit user path string

    Returns:
        List: Sequence of index identification strings
    """
    # return re.findall(r"\[(\w+)\]", path) # Only word charaters i.e. [a-zA-Z0-9_]+
    return re.findall(REGEX_IDXID, path)  # Any character in square brackets


def clean_idxids_from_path(path):
    """TODO add documentation

    Args:
        path ([type]): [description]

    Returns:
        [type]: [description]
    """
    return [
        idxid.split("@")[1] if "@" in idxid else idxid
        for idxid in idxids_from_path(path)
    ]


def remove_braces_from_path(path: str) -> str:
    """Removes braces and their content from the path

    Args:
        path (str): Hubit external path (with square braces)

    Returns:
        str: Hubit path with braces and content removed
    """
    return re.sub("\[([^\.]+)]", "", path)


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
        paths.append(p1.rstrip(".").lstrip("."))
    paths.append(p2.rstrip(".").lstrip("."))
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


# def get_nested_list(maxilocs):
#     """
#     Create nested list with all values set to None.
#     Dimensions given in "maxilocs" which are the max element number ie zero-based
#     """
#     empty_list = None
#     for n in maxilocs[::-1]:
#         empty_list = [copy.deepcopy(empty_list) for _ in range(n + 1)]
#     return empty_list


# def list_from_shape(shape):
#     """
#     Create nested list with all values set to None.
#     Dimensions given in "shape". shape = 1 results in a number
#     """
#     empty_list = None
#     for n in shape[::-1]:
#         if n > 1:
#             empty_list = [copy.deepcopy(empty_list) for _ in range(n)]
#         else:
#             empty_list = copy.deepcopy(empty_list)
#     return empty_list


def inflate(d, sep="."):
    """
    https://gist.github.com/fmder/494aaa2dd6f8c428cede
    Expands lists as dict to handle queries that do include
    all elements i.e. to return the result for item at index X
    at index X and not zero
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


def flatten(d, parent_key="", sep="."):
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
                    _new_key = new_key + "." + str(idx)
                    items.extend(flatten(item, _new_key, sep=sep).items())
            except AttributeError:
                # Elements are not dicts
                items.append((new_key, v))
        else:
            items.append((new_key, v))
    return dict(items)


def set_ilocs_on_path(path: str, ilocs: List) -> str:
    """Replace the index IDs on the path with location indices
    in ilocs

    Args:
        path (str): Hubit model path
        ilocs (List): Sequence of index locations to be inserted into the path.
        The sequence should match the index IDs in the path

    Returns:
        str: Path with index IDs replaced by integers
    """
    _path = copy.copy(path)
    for iloc, idxid in zip(ilocs, idxids_from_path(path)):

        # Don't replace if there is an index wildcard
        if IDX_WILDCARD in idxid:
            continue

        _path = _path.replace(idxid, iloc, 1)
    return _path


def check_path_match(
    query_path: str, model_path: str, accept_idx_wildcard: bool = True
) -> bool:
    """Check if the query mathches the model path from the
    model bindings

    Args:
        query_path (str): The query path (external)
        symbolic_path (str): The model path (external)
        accept_idx_wildcard (bool): Should idx wildcard in the query path be accepted. Default True.

    Returns:
        bool: True if the query matches the model path
    """
    idxids = idxids_from_path(model_path)
    query_path_cmps = convert_to_internal_path(query_path).split(".")
    model_path_cmps = convert_to_internal_path(model_path).split(".")
    # Should have same number of path components
    if not len(query_path_cmps) == len(model_path_cmps):
        return False
    for qcmp, mcmp in zip(query_path_cmps, model_path_cmps):
        if is_digit(qcmp):
            # When a digit is found in the query either an ilocstr,
            # a wildcard or a digit should be found in the symbolic path
            if not (mcmp in idxids or IDX_WILDCARD in mcmp or is_digit(mcmp)):
                return False
        elif accept_idx_wildcard and qcmp == IDX_WILDCARD:
            # When a wildcard is found in the query an index ID must be in the model
            if not mcmp in idxids:
                return False
        else:
            # If not a digit the path components should be identical
            if not qcmp == mcmp:
                return False
    return True


def idxs_for_matches(
    qpath: str, mpaths: List[str], accept_idx_wildcard: bool = True
) -> List[int]:
    """
    Returns indices in the sequence of provider strings that match the
    strucure of the query string
    """
    return [
        idx
        for idx, mpath in enumerate(mpaths)
        if check_path_match(qpath, mpath, accept_idx_wildcard)
    ]


def get_iloc_indices(query_path: str, model_path: str, idxids: List[str]) -> Tuple:
    """
    List indices extracted from query based on location of
    ilocstr in providerstring

    BOTH SHOULD BE INTERNAL PATHS
    """
    # If no index IDS specified we cant find any index locations
    if len(idxids) == 0:
        return []

    idxs = []
    for qcmp, scmp in zip(query_path.split("."), model_path.split(".")):
        if idxids[len(idxs)] in scmp:
            idxs.append(qcmp.split("@")[0])
            if len(idxs) == len(idxids):
                break
    return tuple(idxs)


# def query_all(providerstrings, flat_input, ilocstr):
#     """
#     Assumes complete input
#     """
#     return [qry
#             for path in providerstrings
#             for qry in expand_query(path.replace(ilocstr, ":"), flat_input)]


def set_nested_item(data, keys, val):
    """Set item in nested dictionary"""
    reduce(getitem, keys[:-1], data)[keys[-1]] = val
    return data


def get_nested_item(data, keys):
    return reduce(getitem, keys, data)


def get_idx_context(path):
    return "-".join(clean_idxids_from_path(path))


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
