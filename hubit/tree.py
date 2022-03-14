from __future__ import annotations
import logging
import copy
import itertools
from typing import (
    Any,
    List,
    Dict,
    Mapping,
    Sequence,
    Tuple,
    Union,
    Optional,
    TYPE_CHECKING,
    cast,
)
from .errors import HubitIndexError, HubitError, HubitModelQueryError
from .config import (
    FlatData,
    HubitModelPath,
    HubitQueryPath,
    PathIndexRange,
    Path,
)
from .utils import is_digit, get_from_datadict, split_items, traverse, set_element

if TYPE_CHECKING:
    from .config import HubitModelComponent

Node = Union["LeafNode", "LengthNode"]


class LeafNode:
    """Used for leaves in the LengthTree instead of a LengthNode"""

    def __init__(self, idx: int):
        # Stores index in parent's list of children
        self.index = idx

        # Not used but mypy likes it
        self.level = 0
        self.parent = None

    @property
    def children(self):
        """A leaf has no children"""
        raise NotImplementedError

    def remove_decendants(self):
        pass

    def __str__(self):
        return f'LeafNode(nchildren=NA, index={self.index}, has parent={"Yes" if self.parent else "No"}, is_constrained=NA)'


class LengthNode:
    def __init__(self, nchildren: int):
        """A node in the length tree i.e. a generalized
        shape for non-rectagular data.

        Args:
            nchildren (int): Number of children. Equivalent to the number of
            indices for the current node.
        """
        self.level = 0
        # Assume bottom level
        self._nchildren_org = nchildren
        self.children: Sequence[Node] = [LeafNode(idx) for idx in range(nchildren)]
        self._set_child_for_idx()

        # Assume top level (parent = None)
        self.parent: Optional[LengthNode] = None
        self.tree: LengthTree

        # Stores index in parent's list of children
        self.index: int

        # Is node constrained by pruning
        self.is_constrained: bool = False

    def _set_child_for_idx(self):
        self._child_for_idx = {child.index: child for child in self.children}

    def child(self, index: int) -> Union[LengthNode, LeafNode]:
        """Get the child corresponding to the specified index"""
        # TODO: should this be improved?
        try:
            return {child.index: child for child in self.children}[
                self.normalize_child_index(index)
            ]
        except KeyError:
            idxs = [str(child.index) for child in self.children]
            raise HubitIndexError(
                f"No child with index {index} ({self.normalize_child_index(index)}) on node."
                f"Available indices are: {', '.join(idxs)}"
            )

    def normalize_child_index(self, index: int):
        # TODO: think about this for a while...
        if index < 0:
            norm_index = self._nchildren_org + index
            if norm_index < 0:
                raise HubitIndexError(
                    f"Index {index} was normalized to {norm_index} for node "
                    f"that had {self._nchildren_org} children (now {self.nchildren()})."
                )
            return norm_index
        else:
            return index

    def nchildren(self) -> int:
        return len(self.children)

    def set_children(self, children: Sequence[Union[LengthNode, LeafNode]]):
        self.children = list(children)
        self._nchildren_org = len(self.children)
        for idx, child in enumerate(self.children):
            child.parent = self
            child.level = self.level + 1
            child.index = idx
        self._set_child_for_idx()

    def remove(self):
        """remove node"""
        if self.parent is None:
            raise HubitIndexError

        self.remove_decendants()
        self.parent.children.remove(self)
        del self.parent._child_for_idx[self.index]
        if self.parent.nchildren() == 0:
            self.parent.remove()
        self.tree.nodes_for_level[self.level].remove(self)
        # for node in self.tree.nodes_for_level[self.level]:
        #     node.is_constrained = False

    def pop_child_for_idx(self, idx):
        child = self._child_for_idx[idx]
        child.remove_decendants()
        if not isinstance(child, LeafNode):
            # Not the bottom-most level so safe to access self.level + 1
            self.tree.nodes_for_level[self.level + 1].remove(child)
        self.children.pop(idx)
        del self._child_for_idx[idx]

    def remove_decendants(self):
        for child in self.children:
            if isinstance(child, LeafNode):
                continue

            # Remove child from tree
            child.tree.nodes_for_level[child.level].remove(child)
            child.remove_decendants()
        self.children = [LeafNode(idx) for idx in range(len(self.children))]
        self._set_child_for_idx()

    def __str__(self):
        return f'LengthNode(nchildren={self.nchildren()}, index={self.index}, has parent={"Yes" if self.parent else "No"}, is_constrained={self.is_constrained})'

    def __repr__(self):
        return str(self)


class DummyLengthTree:
    """Dummy tree for"""

    def __init__(self, *args, **kwargs):
        self.level_names = []

    @property
    def index_context(self):
        return "-".join(self.level_names)

    def prune_from_path(
        self,
        _path: Path,
        inplace: bool = True,
    ) -> DummyLengthTree:
        return self if inplace else copy.deepcopy(self)

    def clip_at_level(
        self,
        _level_name: str = "",
        inplace: bool = True,
    ) -> DummyLengthTree:
        return self if inplace else copy.deepcopy(self)

    def fix_idx_at_level(
        self,
        _idx_value: int = 0,
        _level_idx: int = 0,
        inplace: bool = True,
    ):
        """Don't change the tree"""
        return self if inplace else copy.deepcopy(self)

    def expand_path(self, path: Path, *args, **kwargs) -> List[HubitQueryPath]:
        return [HubitQueryPath(path)]

    def none_like(self):
        return None

    def is_path_described(self, path: Path) -> bool:
        return True


class LengthTree:
    """Stores length information for multi-dimensional and non-rectangular
    data.
    """

    def __init__(self, nodes: List[LengthNode], level_names: Sequence[str]):
        """A data structure that allows manipulations of connected
        LengthNodes

        Args:
            nodes (List[LengthNode]): Connected length nodes
            level_names (List[str]): Name of the levels specified on the nodes
        """
        self.level_names: Sequence[str] = level_names

        # Set to pruning path when pruned else None
        self._prune_path: Union[None, Path] = None

        self.nodes_for_level: Sequence[List[LengthNode]] = [[] for _ in level_names]
        for node in nodes:
            node.tree = self
            self.nodes_for_level[node.level].append(node)

    @property
    def nlevels(self):
        return len(self.nodes_for_level)

    @property
    def index_context(self):
        return "-".join(self.level_names)

    def clip_at_level(self, level_name: str, inplace: bool = True) -> LengthTree:
        """Remove levels below 'level_name'

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

    def prune_from_path(self, path: Path, inplace: bool = True) -> LengthTree:
        """Prune the length tree based on a path where zero
        to all indices are already specified.

        Args:
            path: A Hubit path with zero to all index IDs replaced by indices
            inplace (bool, optional): If True the instance itself will be pruned. If False a pruned copy will be created. Defaults to True.

        Returns:
            LengthTree: Pruned tree. If inplace=True the instance itself is also pruned.
        """
        obj = self if inplace else copy.deepcopy(self)
        obj._prune_path = path
        ranges = path.ranges()
        if all([range.is_full_range for range in ranges]):
            return obj

        # Loop over the index ID levels
        assert len(ranges) == len(
            obj.level_names
        ), f"Path {path} does not math tree with levels {obj.level_names}"

        for level_idx, range in enumerate(ranges):

            if range.is_full_range:
                # No pruning required since all elements are in scope
                continue

            if range.is_digit:
                obj.fix_idx_at_level(int(range), level_idx)

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
            idx_others = [child.index for child in node.children]
            node.is_constrained = True
            idx_value_norm = node.normalize_child_index(idx_value)
            if idx_value_norm in idx_others:
                # idx can be provided
                idx_others.remove(idx_value_norm)
                for idx_other in reversed(idx_others):
                    node.pop_child_for_idx(idx_other)

            else:
                nodes_to_be_deleted.append(node)

        for node in nodes_to_be_deleted:
            try:
                node.remove()
            except HubitIndexError:
                raise HubitIndexError(
                    f"Cannot find index {idx_value} ({idx_value_norm}) "
                    f"for index ID {obj.level_names[level_idx]} "
                    f"in tree "
                    f"{self}"
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
                if is_digit(sizes):
                    vals = split_items(vals, traverse([sizes]))
                elif len(sizes) == 1:
                    vals = split_items(vals, traverse(sizes))[0]
                else:
                    vals = split_items(vals, traverse(sizes))

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
            nodes (List[LengthNode], optional): Cumulative list of nodes. Defaults to None.
            paths_previous (List, optional): Hubit internal paths found in
            previous level of recursion with explicit indices. Defaults to None.
            parent (LengthNode, optional): Parent node

        Returns:
            Tuple: Two-tuple list of nodes, paths_previous
        """
        sep = "."
        paths_previous = paths_previous or [connecting_paths[0]]
        nodes = nodes or []

        # Get node list for paths prepared at the previous recursion level
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
            # to the previously found paths
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
    def from_data(cls, path: HubitModelPath, data: dict, prune: bool = False) -> Any:
        """Infer lengths of lists in 'input_data' that correspond
        to index IDs in the path.

        Args:
            path (str): Hubit model path
            input_data (Dict): Input data
            prune (bool): Tree is pruned if True

        Returns:
            LengthTree: Element 0 is DummyLengthTree if no index IDs found in 'path'
            otherwise a LengthTree.
        """
        # Handle no index IDs
        if len(path.get_index_specifiers()) == 0:
            return DummyLengthTree()

        # Handle all IDs are digits
        if all([range.is_digit for range in path.ranges()]):
            return DummyLengthTree()

        connecting_paths = path.paths_between_specifiers()
        # Exclude leaf attribute (empty string or path following last index specifier)
        connecting_paths = connecting_paths[:-1]
        nodes, _ = LengthTree._nodes_for_iterpaths(connecting_paths, data)

        index_identifiers = path.get_index_identifiers()
        tree = cls(nodes, index_identifiers)

        # Some path indices may have specific locations so prune the tree
        # This does not work when different indices can be provided by
        # different components since the tress are only stored according to their
        # index context. When different indices are be provided by
        # different components the index context are the same but the trees are
        # different
        if prune:
            tree.prune_from_path(path)

        return tree

    def reshape(self, items: List, inplace: bool = True) -> Any:
        """Reshape items according to the shape defined by the tree

        Args:
            items (List): Flat list of to be reshaped
            inplace (bool): If True the specified list will be reshaped.
            If False a copy will be created and reshaped.

        Returns:
            None objects arraged like the tree.
        """
        _items = items if inplace else copy.deepcopy(items)

        # Always one node at the top of the tree
        top_node = self.nodes_for_level[0][0]

        # Used to check if items are ever split.
        # Use top node since it is not part of the loop
        as_list = not top_node.is_constrained

        for nodes in reversed(self.nodes_for_level[1:]):

            # If 1 node and contrained by pruning do not split
            # Assures that "segments[0].layers[0].thickness[:]" would result
            # in a 1D list while "segments[0].layers[:].thickness[:]" would
            # result in a 2D list even if there were only 1 layer
            # print("is_constrained", nodes[0].is_constrained)
            # if len(nodes) == 1 and nodes[0].is_constrained:
            #     continue

            if all([node.is_constrained for node in nodes]):
                continue

            as_list = True
            nchildren = [node.nchildren() for node in nodes]
            _items = split_items(_items, nchildren)

        if as_list:
            # Reduce dimensionality by 1
            if top_node.is_constrained:
                _items = _items[0]

            return _items
        else:
            # TODO: could check len(items) = 1 at the top
            assert (
                len(items) == 1
            ), f"Expected list of length 1, but found {len(items)}."
            return _items

    def _node_for_idxs(self, idxs: List[int]):
        """
        Get the node corresponding to a list of indices
        """
        if len(idxs) == 0:
            node = self.nodes_for_level[0][0]
        else:
            node = self.nodes_for_level[0][0]._child_for_idx[idxs[0]]
            for node_idx in idxs[1:]:
                node = node._child_for_idx[node_idx]
        return node

    def _is_pruned_from(self, path: Path):
        return self._prune_path == path

    def expand_path(
        self,
        path: Path,
        flat: bool = False,
    ) -> List[HubitQueryPath]:
        """Expand model path with wildcard based on tree. If path is fixed at some index the
        tree must be pruned according to the specified path if flat = False. This is not
        checked.

        Example for a query path:
            list[:].some_attr.numbers ->
            [ list[0].some_attr.numbers, list[1].some_attr.numbers, list[2].some_attr.numbers ]


        Args:
            path (Path): Any path with wildcards and index IDs
            flat (bool): Return expansion result as a flat list.

        Returns:
            List: Paths from expansion. Arranged in the shape
            defined by the tree if flat = False. Otherwise a
            flat list.
        """
        if not self._is_pruned_from(path):
            raise HubitError(
                f"Tree should be pruned using path '{path}'. Tree pruned with: '{self._prune_path}'"
            )

        # Get the content of the braces
        idxspecs = path.get_index_specifiers()

        # Top level always has one node
        paths = [path]

        # Loop over levels in sequence stating from the top (left)
        for idx_level, idxspec in enumerate(idxspecs):
            nodes = self.nodes_for_level[idx_level]
            # After processing the number of paths (on the current level) there will
            # always be an equal number of paths and children. Therefore, before the
            # processing (here), the number of nodes and paths are
            # equal (in a LengthTree #nodes next level = #children current level).
            paths_current_level: List[Path] = []
            for _path, node in zip(paths, nodes):
                # Assumes pruned tree
                paths_current_level.extend(
                    [
                        _path.new_with_index(idxspec, str(child.index))
                        for child in node.children
                    ]
                )
            paths = copy.deepcopy(paths_current_level)

        # Cast strings as paths
        _paths = [HubitQueryPath(_path) for _path in paths]
        if flat:
            return _paths
        else:
            return self.reshape(_paths)

    def _all_nodes_constrained(self):
        return all(
            [node.is_constrained for nodes in self.nodes_for_level for node in nodes]
        )

    def number_of_leaves(self):
        """Number of leaves in the tree"""
        return sum(self.number_of_children(-1))

    def children_at_level(self, idx_level: int) -> List[Node]:
        """Number of children for each node at the specified level"""
        return [
            child for node in self.nodes_for_level[idx_level] for child in node.children
        ]

    def number_of_children(self, idx_level: int) -> List[int]:
        """Number of children for each node at the specified level"""
        return [node.nchildren() for node in self.nodes_for_level[idx_level]]

    def none_like(self) -> Any:
        """Create data structure in the shape of the tree
        filled with None

        Returns:
            Data structure with None
        """
        # If all node are constrained the result is None. No list to reshape
        if self._all_nodes_constrained():
            return None

        # Reshape a flat list with all elements set to None. The list has length
        # like all leaves in the tree
        return self.reshape([None for _ in range(self.number_of_leaves())])

    def is_path_described(self, path: Path) -> bool:
        """Check if the specified model path is described by the tree

        On each level the path index range must contain at least one child index. Example:
        For the tree
          level=0 (IDX_SITE), nodes=1 parents=0, children=1, children are leaves=[False], child idxs=[[0]]
          level=1 (IDX_LINE), nodes=1 parents=1, children=1, children are leaves=[False], child idxs=[[0]]
          level=2 (IDX_TANK), nodes=1 parents=1, children=3, children are leaves=[True], child idxs=[[0, 1, 2]]
        The following path match
          prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_yield -> OK
          prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[1@IDX_TANK].Q_yield -> OK
          prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[2@IDX_TANK].Q_yield -> OK
        while the path below does not
          prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[3@IDX_TANK].Q_yield -> Not OK
        since the index range '3' coming from [3@IDX_TANK] is not a part of the tree
        """

        # Index contexts must match
        try:
            if not self.index_context == path.index_context:
                return False
        except NotImplementedError:
            # query paths have no index context
            pass

        ranges = path.ranges()

        # The path must have ranges corresponding to the number of levels in the tree
        if not (len(ranges) == self.nlevels):
            return False

        def filter_nodes(range_: PathIndexRange, nodes: List[Node]) -> List[Node]:
            """Only consider children that are described by the index"""
            return [node for node in nodes if range_.contains_index(node.index)]

        def nodes_next(nodes: List[Node]) -> List[Node]:
            """Get children for the LengthNode"""
            return [child for node in nodes for child in node.children]

        nodes = self.children_at_level(0)

        # Loop over levels excluding the last which has LeafNode (with no children)
        for range_ in ranges[:-1]:
            # Build list of children matching the "description"
            nodes = filter_nodes(range_, nodes)
            if len(nodes) == 0:
                return False

            nodes = nodes_next(nodes)

        # Handle LeafNodes
        nodes = filter_nodes(ranges[-1], nodes)
        if len(nodes) == 0:
            return False

        # If we get to the leaves the path is described
        return True

    def __str__(self):
        lines = ["--------------------", "Tree"]
        for idx, (name, nodes) in enumerate(
            zip(
                self.level_names,
                self.nodes_for_level,
            )
        ):
            nparents = len({node.parent for node in nodes if node.parent is not None})
            nchildren = sum([node.nchildren() for node in nodes])
            children_are_leaves = [
                all([isinstance(child, LeafNode) for child in node.children])
                for node in nodes
            ]
            idx_node = [[child.index for child in node.children] for node in nodes]
            is_constrained = [node.is_constrained for node in nodes]

            lines.append(
                f"level={idx} ({name}), "
                f"nodes={len(nodes)} (constrained: {is_constrained}), "
                f"parents={nparents}, "
                f"children={nchildren}, "
                f"children are leaves={children_are_leaves}, "
                f"child idxs={idx_node}"
            )

        lines.append("--------------------")
        lines.append("Lengths")

        size_for_level = self.to_list()

        for idx, (name, size) in enumerate(zip(self.level_names, size_for_level)):
            lines.append(f"level={idx} ({name}), {size}")

        return "\n".join(lines)


class _QueryExpansion:
    """A Hubit query expansion. A query can be split into multiple queries

    path: A [`HubitQueryPath`][hubit.config.HubitQueryPath] representing the original query.
    decomposed_paths: If a single component can provide results for `path`, `decomposed_paths`
        has one element of type [`HubitQueryPath`][hubit.config.HubitQueryPath]. If multiple
        components match the query individual path contributions are the items in the list.
    exp_paths_for_decomp_path: For each element in `decomposed_paths`
        these are the expanded paths i.e. dotted paths with real indices not
        wildcards.
    """

    def __init__(
        self,
        path: HubitQueryPath,
        mpaths: List[HubitModelPath],
        tree: LengthTree,
        cmps: List[HubitModelComponent],
    ):
        """
        path: the query path
        mpaths: the model paths that match the query
        cmps: the component for each of the mpaths. If None no mpath filtering is performed

        We don't normalize on initialization  to reduce coupling to model and tree objects
        """
        self.path = path
        self.tree = tree
        self.paths_norm = _QueryExpansion._normalize_path(self.path, tree)

        # Filter models paths using index specifiers for normalized query path

        # Store in dict with normalized path so decomposition can be carried out in
        # pairs (qpath_norm, mpaths)
        index_scopes = [cmp.index_scope for cmp in cmps]
        mpaths_for_qpath_norm = {
            qpath_norm: _QueryExpansion._filter_mpaths_for_qpath_index_ranges(
                qpath_norm,
                mpaths,
                index_scopes,
                self.tree.prune_from_path(qpath_norm, inplace=False),
            )
            for qpath_norm in self.paths_norm
        }

        # Store the flattened version
        self.mpaths = list(
            itertools.chain.from_iterable(mpaths_for_qpath_norm.values())
        )

        if len(self.mpaths) > 1 and not self.path.has_slice_range():
            # Should not be possible to have multiple providers if the query
            # points to a specific path i.e. has no ranges.
            # TODO: This check could be more strict e.g. the wildcard is located where
            # the mpaths vary
            raise HubitModelQueryError(
                f"More than one component match the query '{self.path}'. Matching components provide: {self.mpaths}."
            )

        # Get the index contexts for doing some validation
        self._idx_context = _QueryExpansion.get_index_context(self.path, self.mpaths)

        self.decomposed_paths: List[List[HubitQueryPath]] = []
        for path_norm in self.paths_norm:
            _decomposed_paths, index_identifiers = _QueryExpansion.decompose_query(
                path_norm, mpaths_for_qpath_norm[path_norm]
            )
            self.decomposed_paths.append(list(set(_decomposed_paths)))

        # TODO: Cannot see that I actually use the keys any longer
        self.exp_paths_for_decomp_path: Dict[HubitQueryPath, List[HubitQueryPath]] = {}

        # Used to validate tree against expansion
        self.decomposed_idx_identifiers: List[Union[None, str]] = []
        if index_identifiers is None:
            self.decomposed_idx_identifiers.append(None)
        else:
            # Cannot occur since len(_idx_contexts) is 1
            # if len(set(index_identifiers)) > 1:
            #     msg = f"Fatal error. Inconsistent decomposition for query '{path}': {', '.join(mpaths)}"
            #     raise HubitModelQueryError(msg)
            self.decomposed_idx_identifiers.append(index_identifiers[0])

        # Validate that tree and expantion are consistent
        self._validate_tree()
        self._set_expanded_paths()

    @staticmethod
    def _filter_mpaths_for_qpath_index_ranges(
        qpath: HubitQueryPath,
        mpaths: List[HubitModelPath],
        index_scopes: Sequence[Dict[str, PathIndexRange]],
        pruned_tree: LengthTree,
    ) -> List[HubitModelPath]:
        """
        each path represents a path provided for the corresponding component.
        mpaths, index_scopes have same length
        """
        # Indexes for models paths that match the query path (index considering intersections)
        # Set the index scope
        _mpaths = [
            mpath.set_range_for_idxid(index_scope)
            for mpath, index_scope in zip(mpaths, index_scopes)
        ]

        # TODO negative-indices. split out field check
        idxs = qpath.idxs_for_matches(_mpaths, check_intersection=True)

        # Check that math exists in pruned tree
        _mpaths = [
            _mpaths[idx] for idx in idxs if pruned_tree.is_path_described(_mpaths[idx])
        ]
        return _mpaths

    @staticmethod
    def _normalize_path(
        qpath: HubitQueryPath, tree: LengthTree
    ) -> List[HubitQueryPath]:
        """
        If the query path has negative indices we must normalize the path
        i.e expand it to get rid of this abstraction.
        """
        if qpath.has_negative_indices:
            # Get index context to find tree and normalizethe  path. The tree
            # is required since field[:].filed2[-1] may, for non-rectangular data,
            # for example correspond to
            # [ field[0].field2[2],
            #   field[1].field2[4],
            #   field[2].filed2[1]
            # ]

            # Even though the model paths have not yet been filtered based on
            # index ranges the index context should still be unique
            return tree.prune_from_path(qpath, inplace=False).expand_path(
                qpath, flat=True
            )
        else:
            return [qpath]

    @staticmethod
    def get_index_context(qpath: HubitQueryPath, mpaths: List[HubitModelPath]):
        """
        Get the index context and do some validation
        """
        # Get the index contexts for doing some tests
        _idx_contexts = {mpath.index_context for mpath in mpaths}
        if len(_idx_contexts) > 1:
            msg = f"Fatal error. Inconsistent providers for query '{qpath}': {', '.join(mpaths)}"
            raise HubitModelQueryError(msg)

        if len(_idx_contexts) == 0:
            msg = f"Fatal error. No provider for query path '{qpath}'."
            raise HubitModelQueryError(msg)

        return list(_idx_contexts)[0]

    @property
    def idx_context(self):
        """The (one) index context corresponding to the model paths"""
        return self._idx_context

    def _set_expanded_paths(self):
        """Set the expanded paths using the tree"""
        for decomposed_qpaths in self.decomposed_paths:
            for decomposed_qpath, _mpath in zip(decomposed_qpaths, self.mpaths):
                pruned_tree = self.tree.prune_from_path(
                    decomposed_qpath,
                    inplace=False,
                )

                # Expand the path
                expanded_paths = pruned_tree.expand_path(decomposed_qpath, flat=True)

                self._update_expanded_paths(decomposed_qpath, expanded_paths)

    def _update_expanded_paths(
        self, decomposed_path: HubitQueryPath, expanded_paths: List[HubitQueryPath]
    ):
        self.exp_paths_for_decomp_path[decomposed_path] = expanded_paths

    def flat_expanded_paths(self):
        """Returns flat list of expanded paths"""
        return [
            path for paths in self.exp_paths_for_decomp_path.values() for path in paths
        ]

    def normalization_is_simple(self):
        return len(self.paths_norm) == 1

    def _path_is_normalized(self):
        return len(self.paths_norm) > 1 or self.path != self.paths_norm[0]

    def is_decomposed(self):
        return any(len(paths) > 1 for paths in self.decomposed_paths)

    def is_expanded(self):
        if self.path.has_slice_range():
            return True

        return False

    def collect_results(self, flat_results: FlatData):
        """
        Collect result from the flat data that belong to the query (expansion)
        """
        if not self.is_expanded():
            # Path not expanded so no need to compress
            # Simple map from single normalized path to the path
            # e.g cars[-1].price ['cars[2].price'] or cars[2].price ['cars[2].price']
            return flat_results[self.paths_norm[0]]

        # Get the index IDs from the original query
        idxids = self.path.get_index_specifiers()

        # TODO: Can we prune earlier on?
        # inplace = False to leave the tree state unchanged.
        values = self.tree.prune_from_path(self.path, inplace=False).none_like()
        # Extract iloc indices for each query in the expanded query
        for expanded_paths in self.exp_paths_for_decomp_path.values():
            for path in expanded_paths:
                ranges = path.ranges()
                # Only keep ilocs that come from an expansion... otherwise
                # the dimensions of "values" do no match
                ranges = [
                    range
                    for range, idxid in zip(ranges, idxids)
                    if idxid == PathIndexRange.wildcard_chr
                ]
                values = set_element(
                    values,
                    flat_results[path],
                    [int(range) for range in ranges],
                )

        return values

    @staticmethod
    def decompose_query(
        qpath: HubitQueryPath, mpaths: List[HubitModelPath]
    ) -> Tuple[List[HubitQueryPath], Union[List[str], None]]:
        """
        Handles the case where more than one provider required to match query.
        In that case the query is into (decomposed) queries each having a single
        provider.

        If a single component can provide results for `path`, `decomposed_paths`
        has one element of type [`HubitQueryPath`][hubit.config.HubitQueryPath].
        If multiple components are required to provide the query their individual
        path contributions are the items in the list. index_identifiers are the
        index identifiers corresponding to the decomposed index
        """
        index_identifiers: Union[List, None]
        if len(mpaths) > 1:
            # More than one provider required to match query. Split query into queries
            # each having a unique provider

            decomposed_qpaths = []
            # Index identifiers corresponding to decomposed field
            index_identifiers = []
            for mpath in mpaths:
                q_idx_specs = qpath.get_index_specifiers()
                idxs, ranges = zip(
                    *[
                        (idx, range)
                        for idx, range in enumerate(mpath.ranges())
                        if not range.is_empty
                    ]
                )
                if len(ranges) == 1:
                    # Replace the index specifier from the query path with
                    # the range from the model path
                    q_idx_specs[idxs[0]] = ranges[0]

                    # Set the ranges (one comes from model path) on the query path
                    decomposed_qpaths.append(qpath.set_indices(q_idx_specs))

                    # Save the index identifier corresponding to the replacement
                    index_identifiers.append(mpath.get_index_identifiers()[idxs[0]])
                elif len(ranges) >= 1:
                    raise HubitModelQueryError(
                        (
                            f"Only one index range may be specified as digit for each",
                            f"model path. For model path '{mpath}', '{mpath.ranges()}'",
                            f"were found.",
                        )
                    )
                else:
                    logging.warning(
                        f"No digits found for decomposed model path {mpath}"
                    )

        else:
            decomposed_qpaths = [qpath]
            index_identifiers = None

        return decomposed_qpaths, index_identifiers

    def _validate_tree(self):
        """Validate that we get the expected number of mpaths in the expansion

        Raises if tree is invalid.

        TODO: If the tree was pruned I think the test could be more strict using ==
        instead of >=.
        """
        # Don't validate if DummyLengthTree since they can never be decomposed
        if isinstance(self.tree, DummyLengthTree):
            return

        # Don't validate tree against expansion if path was not decomposed
        if not self.is_decomposed():
            return

        for decomposed_paths, tree_level_name in zip(
            self.decomposed_paths, self.decomposed_idx_identifiers
        ):

            # Find out which level (index) we are at
            try:
                self.tree.level_names.index(tree_level_name)
            except ValueError as err:
                print(f"ERROR. Level name '{tree_level_name}' not found in tree")
                print(self.tree)
                print(self)
                raise HubitError("Query expansion error.")

            for path in decomposed_paths:
                if not self.tree.is_path_described(path):
                    print(self.tree)
                    raise HubitError(
                        f"Query expansion error. Path '{path}' not described by tree."
                    )

    def __str__(self):
        lines = [f"\nQuery\n  {self.path}"]
        lines.append("Decomposition & expansion")
        for decomp_path, expanded_paths in itertools.zip_longest(
            self.decomposed_paths,
            self.exp_paths_for_decomp_path.values(),
            fillvalue=None,
        ):
            lines.append(f"  {decomp_path} -> {expanded_paths}")
        return "\n".join(lines)


def tree_for_idxcontext(
    components: List[HubitModelComponent], data: Dict
) -> Mapping[str, Union[LengthTree, DummyLengthTree]]:
    """Compute LengthTree for relevant index contexts.

    Args:
        components (List[Componet]): List of Hubit components
        data (Dict): Input data

    Returns:
        Dict: LengthTree for relevant index contexts
    """
    out = {"": DummyLengthTree()}
    for component in components:
        for binding in component.consumes_input:
            tree = LengthTree.from_data(binding.path, data)
            idx_context = binding.path.index_context
            if idx_context in out.keys():
                continue
            out[idx_context] = tree

    # Clip trees to generate trees for (all) shallower index contexts
    for tree in copy.deepcopy(list(out.values())):
        for level_name in tree.level_names[:-1]:
            new_tree = tree.clip_at_level(level_name, inplace=False)
            idx_context = new_tree.index_context
            if idx_context in out.keys():
                continue
            out[idx_context] = new_tree

    return out
