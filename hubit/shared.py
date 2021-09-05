from __future__ import annotations
import logging
import copy
import itertools
from typing import Any, List, Dict, Tuple, TYPE_CHECKING
from .errors import HubitIndexError, HubitError, HubitModelQueryError
from .config import ModelIndexSpecifier, _HubitPath, HubitModelPath, HubitQueryPath
from .utils import is_digit, get_from_datadict, split_items, traverse

if TYPE_CHECKING:
    from .config import HubitModelComponent

IDX_WILDCARD = ModelIndexSpecifier.wildcard_chr


class LeafNode:
    """Used for leaves in the LengthTree instead of a LengthNode"""

    def __init__(self, idx: int):
        # Stores index in parent's list of children
        self.index = idx

    def remove_decendants(self):
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
        # Assume bottom level
        self.children = [LeafNode(idx) for idx in range(nchildren)]
        self._set_child_for_idx()

        # Assume top level (children = None)
        self.parent = None
        self.tree = None

        # Stores index in parent's list of children
        self.index = None

        # Is node constrained by pruning
        self.is_constrained = False

    def _set_child_for_idx(self):
        self._child_for_idx = {child.index: child for child in self.children}

    def nchildren(self) -> int:
        return len(self.children)

    def set_children(self, children: List[LengthNode]):
        self.children = list(children)
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

    def get_idx_context(self):
        return "-".join(self.level_names)

    def prune_from_path(self, *args, **kwargs) -> DummyLengthTree:
        return self

    def clip_at_level(self, inplace: bool = True, *args, **kwargs) -> DummyLengthTree:
        return self if inplace else copy.deepcopy(self)

    def fix_idx_at_level(self, *args, **kwargs):
        pass

    def expand_path(
        self, path: HubitModelPath, *args, **kwargs
    ) -> List[HubitModelPath]:
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

    def prune_from_path(self, path: _HubitPath, inplace: bool = True) -> LengthTree:
        """Prune the length tree based on a path where zero
        to all indices are already specified.

        Args:
            path: A Hubit path with zero to all index IDs replaced by indices
            inplace (bool, optional): If True the instance itself will be pruned. If False a pruned copy will be created. Defaults to True.

        Returns:
            LengthTree: Pruned tree. If inplace=True the instance itself is also pruned.
        """
        obj = self if inplace else copy.deepcopy(self)
        _slices = path.get_slices()
        if all([_slice == IDX_WILDCARD for _slice in _slices]):
            return obj

        # Loop over the index ID levels
        assert len(_slices) == len(
            obj.level_names
        ), f"Path {path} does not math tree with levels {obj.level_names}"

        for level_idx, _slice in enumerate(_slices):

            if _slice == IDX_WILDCARD:
                # No pruning required since all elements are in scope
                continue

            if is_digit(_slice):
                obj.fix_idx_at_level(int(_slice), level_idx)

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
        index_specifiers = path.get_index_specifiers()
        index_identifiers = path.get_index_identifiers()
        slices = path.get_slices()

        # Handle no index IDs
        if len(index_specifiers) == 0:
            return DummyLengthTree()

        # Handle all IDs are digits
        if all([is_digit(_slice) for _slice in slices]):
            return DummyLengthTree()

        connecting_paths = path.paths_between_idxids(index_specifiers)
        # Exclude leaf attribute (empty string or path following last index specifier)
        connecting_paths = connecting_paths[:-1]
        nodes, _ = LengthTree._nodes_for_iterpaths(connecting_paths, data)
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

    def normalize_path(self, qpath: str):
        """Handle negative indices
        As stated in "test_normalize_path2" the normalization in general depends
        on the context
        """

        idxids = qpath.get_index_specifiers()
        _path = copy.copy(qpath)

        for idx_level, idxid in enumerate(idxids):
            if is_digit(idxid) and int(idxid) < 0:
                # Get index context i.e. indices prior to current level
                _idx_context = [
                    int(idx) for idx in _path.get_index_specifiers()[:idx_level]
                ]
                node = self._node_for_idxs(_idx_context)
                _path = _path.replace(idxid, str(node.nchildren() + int(idxid)), 1)
        return _path

    def expand_path(
        self,
        path: HubitModelPath,
        flat: bool = False,
    ) -> List[HubitQueryPath]:
        """Expand model path with wildcard based on tree

        Example for a query path:
            list[:].some_attr.numbers ->
            [ list[0].some_attr.numbers, list[1].some_attr.numbers, list[2].some_attr.numbers ]


        Args:
            path (HubitModelPath): Model path with wildcards and index IDs
            flat (bool): Return expansion result as a flat list.

        Returns:
            List: Paths from expansion. Arranged in the shape
            defined by the tree if flat = False. Otherwise a
            flat list.
        """
        # Get the content of the braces
        idxspecs = path.get_index_specifiers()
        slices = path.get_slices()

        paths = [path]
        for idx_level, (idxspec, _slice, level_name) in enumerate(
            zip(idxspecs, slices, self.level_names)
        ):
            nodes = self.nodes_for_level[idx_level]
            paths_current_level = []
            for _path, node in zip(paths, nodes):
                if is_digit(_slice):
                    # slice is digit so replace index specifier with that digit
                    paths_current_level.append(_path.replace(idxspec, _slice))
                elif _slice == IDX_WILDCARD or idxspec == level_name:
                    # slice is wildcard so expand from node children
                    paths_current_level.extend(
                        [
                            _path.replace(
                                idxspec,
                                str(child.index if child is not None else idx),
                                1,
                            )
                            for idx, child in enumerate(node.children)
                        ]
                    )
                else:
                    raise HubitError(
                        f"Unknown slice '{_slice}' for path '{path}' of type '{type(path)}'."
                    )
            paths = copy.deepcopy(paths_current_level)

        paths = [HubitQueryPath(_path) for _path in paths]
        if flat:
            return paths
        else:
            return self.reshape(paths)

    def _all_nodes_constrained(self):
        return all(
            [node.is_constrained for nodes in self.nodes_for_level for node in nodes]
        )

    def number_of_leaves(self):
        """Number of leaves in the tree"""
        return sum([node.nchildren() for node in self.nodes_for_level[-1]])

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

    def __eq__(self, other):
        return self.to_list() == other.to_list()

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

    Args:
        path: A [`HubitQueryPath`][hubit.config.HubitQueryPath] representing the original query.
        decomposed_paths: If a single component can provide results for `path`, `decomposed_paths`
            has one element of type [`HubitQueryPath`][hubit.config.HubitQueryPath]. If multiple
            components match the query individual path contributions are the items in the list.
        expanded_paths_for_decomposed_path: For each element in `decomposed_paths`
            these are the expanded paths i.e. dotted paths with real indices not
            wildcards.
    """

    def __init__(self, path: HubitQueryPath, mpaths: List[HubitModelPath]):
        """
        path: the query path
        mpaths: the model paths that match the query
        """
        self.path = path

        if len(mpaths) > 1 and not path.has_slice_range():
            raise HubitModelQueryError(
                f"More than one component match the query '{path}'. Matching components provide: {mpaths}."
            )

        self.decomposed_paths, index_identifiers = _QueryExpansion.decompose_query(
            path, mpaths
        )
        self.expanded_paths_for_decomposed_path = {}
        # Get the index contexts for doing some tests
        _idx_contexts = {mpath.get_idx_context() for mpath in mpaths}

        if len(_idx_contexts) > 1:
            msg = f"Fatal error. Inconsistent providers for query '{path}': {', '.join(mpaths)}"
            raise HubitModelQueryError(msg)

        if len(_idx_contexts) == 0:
            msg = f"Fatal error. No provider for query path '{path}'."
            raise HubitModelQueryError(msg)

        if index_identifiers is None:
            self.decomposed_idx_identifier = None
        else:
            if len(set(index_identifiers)) > 1:
                msg = f"Fatal error. Inconsistent decomposition for query '{path}': {', '.join(mpaths)}"
                raise HubitModelQueryError(msg)
            self.decomposed_idx_identifier = index_identifiers[0]

        self._idx_context = list(_idx_contexts)[0]

    @property
    def idx_context(self):
        """The (one) index context corresponding to the model paths"""
        return self._idx_context

    def update_expanded_paths(
        self, decomposed_path: HubitQueryPath, expanded_paths: List[HubitQueryPath]
    ):
        self.expanded_paths_for_decomposed_path[decomposed_path] = expanded_paths

    def flat_expanded_paths(self):
        """Returns flat list of expanded paths"""
        return [
            path
            for paths in self.expanded_paths_for_decomposed_path.values()
            for path in paths
        ]

    def is_decomposed(self):
        return len(self.decomposed_paths) > 1

    def is_expanded(self):
        if (
            not self.is_decomposed()
            and self.path == self.decomposed_paths[0]
            and len(self.expanded_paths_for_decomposed_path[self.decomposed_paths[0]])
            == 1
            and self.path
            == self.expanded_paths_for_decomposed_path[self.decomposed_paths[0]][0]
        ):
            return False
        else:
            return True

    @staticmethod
    def decompose_query(
        qpath: HubitQueryPath, mpaths: List[HubitModelPath]
    ) -> Tuple(List[HubitQueryPath], Any):
        """
        If a single component can provide results for `path`, `decomposed_paths`
        has one element of type [`HubitQueryPath`][hubit.config.HubitQueryPath]. If multiple
        components match required their individual path contributions are the items in the list.
        """
        if len(mpaths) > 1:
            # More than one provide requires to match query. Split query into queries
            # each having a unique provider

            decomposed_qpaths = []
            # Index identifiers corresponding to decomposed field
            index_identifiers = []
            for mpath in mpaths:
                q_idx_specs = qpath.get_index_specifiers()
                slices = mpath.get_slices()
                digits = [
                    (idx, slice) for idx, slice in enumerate(slices) if is_digit(slice)
                ]
                if len(digits) == 1:
                    q_idx_specs[digits[0][0]] = digits[0][1]
                    decomposed_qpaths.append(qpath.set_indices(q_idx_specs))
                    index_identifiers.append(
                        mpath.get_index_identifiers()[digits[0][0]]
                    )
                elif len(digits) >= 1:
                    raise HubitModelQueryError(
                        f"Only one index slice may be specified as digit for each model path. For model path '{mpath}', '{slices}' were found."
                    )
                else:
                    logging.warning(
                        f"No digits found for decomposed model path {mpath}"
                    )

        else:
            decomposed_qpaths = [qpath]
            index_identifiers = None

        return decomposed_qpaths, index_identifiers

    def validate_tree(self, tree: LengthTree):
        """Validate that we get the expected number of mpaths in the expansion

        TODO: If the tree was pruned I think the test could be more strict using ==
        instead of >=.
        """
        if isinstance(tree, DummyLengthTree):
            return

        for idx_id in self._idx_context.split("-"):

            # Only validate the relevant index identifier
            if not idx_id == self.decomposed_idx_identifier:
                continue

            try:
                # TODO handle contexts with more than one index identifier
                level_idx = tree.level_names.index(idx_id)
            except ValueError as err:
                raise Exception(
                    f"Index context '{idx_id}' not found in tree '{tree}'"
                ) from err

            n_decomposed_paths = len(self.decomposed_paths)
            n_children = [node.nchildren() for node in tree.nodes_for_level[level_idx]]
            results = [n >= n_decomposed_paths for n in n_children]
            if not all(results):
                print(
                    f"Too few children at level {level_idx} of tree. Expected at least {n_decomposed_paths} children corresponding to the number of decomposed paths.\n"
                )
                print(tree)
                print(self)
                raise HubitError("Query expansion error.")

    def __str__(self):
        lines = [f"\nQuery\n  {self.path}"]
        lines.append("Decomposition & expansion")
        for decomp_path, expanded_paths in itertools.zip_longest(
            self.decomposed_paths,
            self.expanded_paths_for_decomposed_path.values(),
            fillvalue=None,
        ):
            lines.append(f"  {decomp_path} -> {expanded_paths}")
        return "\n".join(lines)


def tree_for_idxcontext(
    components: List[HubitModelComponent], data: Dict
) -> Dict[str, LengthTree]:
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
            idx_context = binding.path.get_idx_context()
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
