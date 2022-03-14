import random
import string
import unittest
from unittest.mock import Mock
import yaml
import pytest
import pprint

from hubit.tree import (
    LengthTree,
    LengthNode,
    DummyLengthTree,
    _QueryExpansion,
    LeafNode,
)
from hubit.config import FlatData, HubitModelPath, HubitQueryPath, PathIndexRange
from hubit.errors import HubitError, HubitIndexError, HubitModelQueryError


def get_mock_components(mpaths):
    cmp = Mock()
    cmp.index_scope = {}
    return [cmp for _ in mpaths]


def _get_data():
    # Make the tree
    site_nodes = LengthNode(2)
    line_nodes = [LengthNode(1), LengthNode(1)]
    tank_nodes_site0 = [LengthNode(3)]
    tank_nodes_site1 = [LengthNode(4)]

    site_nodes.set_children(line_nodes)
    line_nodes[0].set_children(tank_nodes_site0)
    line_nodes[1].set_children(tank_nodes_site1)

    nodes = [site_nodes]
    nodes.extend(line_nodes)
    nodes.extend(tank_nodes_site0)
    nodes.extend(tank_nodes_site1)
    level_names = "IDX_SITE", "IDX_LINE", "IDX_TANK"

    flat_results = FlatData(
        {
            "sites[0].lines[0].tanks[0].Q_yield": 10.0,
            "sites[0].lines[0].tanks[1].Q_yield": 6.0,
            "sites[0].lines[0].tanks[2].Q_yield": 4.0,
            "sites[1].lines[0].tanks[0].Q_yield": 20.0,
            "sites[1].lines[0].tanks[1].Q_yield": 8.0,
            "sites[1].lines[0].tanks[2].Q_yield": 3.0,
            "sites[1].lines[0].tanks[3].Q_yield": 1.0,
        }
    )
    tree = LengthTree(nodes, level_names)
    print("tree", tree)

    return tree, flat_results


class TestDummyTree(unittest.TestCase):
    def setUp(self):
        self.tree = LengthTree.from_data(
            HubitModelPath("segments.layers.positions"), {}
        )
        assert isinstance(self.tree, DummyLengthTree)

    def test_get_idx_context(self):
        """Index context for dummy tree must be the empty string"""
        result = self.tree.index_context
        assert result == ""

    def test_prune_from_path(self):
        """Inplace pruning gives the dummy tree itself"""
        result = self.tree.prune_from_path(HubitModelPath(), inplace=True)
        assert result == self.tree

    def test_clip_at_level(self):
        """Inplace clipping gives the dummy tree itself"""
        result = self.tree.clip_at_level(inplace=True)
        assert result == self.tree

    def test_fix_idx_at_level(self):
        """Inplace fix gives the dummy tree itself"""
        result = self.tree.fix_idx_at_level()
        assert result == self.tree

    def test_is_path_described(self):
        """Any path is describe"""
        assert DummyLengthTree().is_path_described(
            HubitModelPath(
                "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
            )
        )


class TestTree(unittest.TestCase):
    def setUp(self):
        # lengths = [['IDX_SEG', 2],
        #            ['IDX_LAY', [3, 4]],
        #            ['IDX_POS', [[1, 3, 2], [5, 1, 2, 4]]]]

        seg_nodes = LengthNode(2)
        lay_nodes = LengthNode(3), LengthNode(4)
        pos_lay0_nodes = (
            LengthNode(1),
            LengthNode(3),
            LengthNode(2),
        )
        pos_lay1_nodes = (
            LengthNode(5),
            LengthNode(1),
            LengthNode(2),
            LengthNode(4),
        )

        seg_nodes.set_children(lay_nodes)
        lay_nodes[0].set_children(pos_lay0_nodes)
        lay_nodes[1].set_children(pos_lay1_nodes)

        nodes = [seg_nodes]
        nodes.extend(lay_nodes)
        nodes.extend(pos_lay0_nodes)
        nodes.extend(pos_lay1_nodes)
        level_names = "IDX_SEG", "IDX_LAY", "IDX_POS"
        self.tree = LengthTree(nodes, level_names)
        self.template_path = HubitModelPath(
            "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        )

    def test_from_data1(self):
        """Extract lengths from input for path"""
        yml_input = """
                        segments:
                            - layers:
                                - thickness: 0.1 # [m]
                                  material: brick
                                  test:
                                    positions: [1, ]
                                - thickness: 0.02
                                  material: air
                                  test:
                                    positions: [1, 2, 3]
                                - thickness: 0.1
                                  material: brick
                                  test:
                                    positions: [1, 3]
                              inside:
                                temperature: 320. 
                              outside:
                                temperature: 273.
                            - layers:
                                - thickness: 0.15
                                  material: concrete
                                  test:
                                    positions: [1, 2, 3, 4, 5]
                                - thickness: 0.025
                                  material: EPS
                                  test:
                                    positions: [1,]
                                - thickness: 0.1
                                  material: concrete
                                  test:
                                    positions: [1, 2,]
                                - thickness: 0.001
                                  material: paint
                                  test:
                                    positions: [1, 2, 3, 4]
                              inside:
                                temperature: 300.
                              outside:
                                temperature: 273.
                    """
        input_data = yaml.load(yml_input, Loader=yaml.FullLoader)
        # path = "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        path = HubitModelPath(
            "segments[IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        )

        tree = LengthTree.from_data(path, input_data)
        tree_as_list = tree.to_list()
        # print(tree_as_list)
        # TODO test paths in this case
        # path = "segments[:@IDX_SEG].layers[:@IDX_LAY].test"
        expected_lengths = [2, [3, 4], [[1, 3, 2], [5, 1, 2, 4]]]
        self.assertSequenceEqual(expected_lengths, tree_as_list)

    def test_from_data2(self):
        """No lengths since there are no index IDs in path"""
        path = HubitModelPath("segments.layers.positions")
        calculated_tree = LengthTree.from_data(path, {})
        self.assertIsInstance(calculated_tree, DummyLengthTree)

    def test_0(self):
        """path is identical to template_path so the tree remains unchanged"""
        path = self.template_path
        pruned_tree = self.tree.prune_from_path(path, inplace=False)
        self.assertTrue(self.tree.to_list() == pruned_tree.to_list())

    def test_1(self):
        """Top level index fixed to 0
        [['IDX_SEG', 2],
        ['IDX_LAY', [3, 4]],
        ['IDX_POS', [[1, 3, 2], [5, 1, 2, 4]]]]
        """
        expected_lengths = [1, 3, [1, 3, 2]]
        path = HubitModelPath(
            "segments[0@IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        )
        pruned_tree = self.tree.prune_from_path(path, inplace=False)
        self.assertListEqual(pruned_tree.to_list(), expected_lengths)

        path = HubitQueryPath("segments[0].layers[:].test.positions[:]")
        pruned_tree = self.tree.prune_from_path(path, inplace=False)
        self.assertListEqual(pruned_tree.to_list(), expected_lengths)

    def test_2(self):
        """Top level index fixed to 1"""
        expected_lengths = [1, 4, [5, 1, 2, 4]]

        path = HubitModelPath(
            "segments[1@IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        )
        pruned_tree = self.tree.prune_from_path(path, inplace=False)
        self.assertListEqual(pruned_tree.to_list(), expected_lengths)

        path = HubitQueryPath("segments[1].layers[:].test.positions[:]")
        pruned_tree = self.tree.prune_from_path(path, inplace=False)
        self.assertListEqual(pruned_tree.to_list(), expected_lengths)

    def test_2a(self):
        """Outside bounds top level index"""
        path = HubitModelPath(
            "segments[2@IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        )
        with self.assertRaises(HubitIndexError) as context:
            self.tree.prune_from_path(path)

        path = HubitQueryPath("segments[2].layers[:].test.positions[:]")
        with self.assertRaises(HubitIndexError) as context:
            self.tree.prune_from_path(path)

    def test_3(self):
        """Middle index fixed"""
        expected_lengths = [2, [1, 1], [[3], [1]]]

        path = HubitModelPath(
            "segments[:@IDX_SEG].layers[1@IDX_LAY].test.positions[:@IDX_POS]"
        )
        pruned_tree = self.tree.prune_from_path(path, inplace=False)
        self.assertListEqual(pruned_tree.to_list(), expected_lengths)

        path = HubitQueryPath("segments[:].layers[1].test.positions[:]")
        pruned_tree = self.tree.prune_from_path(path)
        self.assertListEqual(pruned_tree.to_list(), expected_lengths)

    def test_4(self):
        """In bounds for all bottom-most paths."""
        expected_lengths = [2, [3, 4], [[1, 1, 1], [1, 1, 1, 1]]]

        path = HubitModelPath(
            "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions[0@IDX_POS]"
        )
        pruned_tree = self.tree.prune_from_path(path, inplace=False)
        self.assertListEqual(pruned_tree.to_list(), expected_lengths)

        path = HubitQueryPath("segments[:].layers[:].test.positions[0]")
        pruned_tree = self.tree.prune_from_path(path, inplace=False)
        self.assertListEqual(pruned_tree.to_list(), expected_lengths)

    def test_5(self):
        """Two indices fixed"""
        expected_lengths = [1, 4, [1, 1, 1, 1]]

        path = HubitModelPath(
            "segments[1@IDX_SEG].layers[:@IDX_LAY].test.positions[0@IDX_POS]"
        )
        pruned_tree = self.tree.prune_from_path(path, inplace=False)
        self.assertListEqual(pruned_tree.to_list(), expected_lengths)

        path = HubitQueryPath("segments[1].layers[:].test.positions[0]")
        pruned_tree = self.tree.prune_from_path(path, inplace=False)
        self.assertListEqual(pruned_tree.to_list(), expected_lengths)

    def test_5a(self):
        """Out of bounds for all but two paths

        [['IDX_SEG', 2*], -> 1
        ['IDX_LAY', [3, 4*]], -> 2
        ['IDX_POS', [[1, 3, 2], [5*, 1, 2, 4*]]]] -> [1, 1]
        """
        expected_lengths = [1, 2, [1, 1]]

        path = HubitModelPath(
            "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions[3@IDX_POS]"
        )
        pruned_tree = self.tree.prune_from_path(path, inplace=False)
        self.assertListEqual(pruned_tree.to_list(), expected_lengths)

        path = HubitQueryPath("segments[:].layers[:].test.positions[3]")
        pruned_tree = self.tree.prune_from_path(path, inplace=False)
        self.assertListEqual(pruned_tree.to_list(), expected_lengths)

    def test_6(self):
        """Out of bounds for all paths

        The tree is modified even when an error is raised if inplace=True
        Thats is OK since Hubit will raise an error and stop execution
        """
        path = HubitModelPath(
            "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions1[7@IDX_POS]"
        )
        with self.assertRaises(HubitIndexError) as context:
            self.tree.prune_from_path(path, inplace=False)

        path = HubitQueryPath("segments[:].layers[:].test.positions1[7]")
        with self.assertRaises(HubitIndexError) as context:
            self.tree.prune_from_path(path, inplace=False)

    def test_prune(self):
        def print_test(tree):
            nodes = tree.nodes_for_level[0]
            for node in nodes:
                print("node", node)
                for child in node.children:
                    print("child", child)

        idx_car_node = LengthNode(2)
        idx_parts_nodes = LengthNode(5), LengthNode(4)
        idx_car_node.set_children(idx_parts_nodes)
        nodes = [idx_car_node]
        nodes.extend(idx_parts_nodes)
        level_names = "IDX_CAR", "IDX_CAR"
        tree = LengthTree(nodes, level_names)
        clipped_tree = tree.clip_at_level("IDX_CAR", inplace=False)

        # nodes or bottom level
        nodes = clipped_tree.nodes_for_level[-1]

        # all children should be None at bottom level
        children_are_leaves = [
            all([isinstance(child, LeafNode) for child in node.children])
            for node in nodes
        ]

        with self.subTest():
            self.assertTrue(all(children_are_leaves))

        with self.subTest():
            self.assertTrue(len(clipped_tree.level_names) == 1)

        with self.subTest():
            self.assertTrue(len(clipped_tree.nodes_for_level) == 1)

    def test_7(self):
        """4-level tree"""
        x1_nodes = LengthNode(2)
        x2_nodes = LengthNode(1), LengthNode(3)
        x3_0_nodes = [LengthNode(2)]
        x3_1_nodes = LengthNode(1), LengthNode(2), LengthNode(4)
        x4_0_0_nodes = LengthNode(1), LengthNode(3)
        x4_1_0_nodes = [LengthNode(1)]
        x4_1_1_nodes = LengthNode(2), LengthNode(2)
        x4_1_2_nodes = (
            LengthNode(1),
            LengthNode(1),
            LengthNode(1),
            LengthNode(2),
        )

        x1_nodes.set_children(x2_nodes)
        x2_nodes[0].set_children(x3_0_nodes)
        x2_nodes[1].set_children(x3_1_nodes)
        x3_0_nodes[0].set_children(x4_0_0_nodes)
        x3_1_nodes[0].set_children(x4_1_0_nodes)
        x3_1_nodes[1].set_children(x4_1_1_nodes)
        x3_1_nodes[2].set_children(x4_1_2_nodes)

        nodes = [x1_nodes]
        nodes.extend(x2_nodes)
        nodes.extend(x3_0_nodes)
        nodes.extend(x3_1_nodes)
        nodes.extend(x4_0_0_nodes)
        nodes.extend(x4_1_0_nodes)
        nodes.extend(x4_1_1_nodes)
        nodes.extend(x4_1_2_nodes)
        level_names = (
            "IDX_X1",
            "IDX_X2",
            "IDX_X3",
            "IDX_X4",
        )
        tree = LengthTree(nodes, level_names)
        expected_lengths = [
            2,
            [1, 3],
            [[2], [1, 2, 4]],
            [[[1, 3]], [[1], [2, 2], [1, 1, 1, 2]]],
        ]
        self.assertListEqual(tree.to_list(), expected_lengths)

    def test_expand_mpath1(self):
        """Expand to full template path"""
        path = HubitModelPath(
            "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        )

        # 1 + 3 + 2 values for segment 0 and 5 + 1 + 2 + 4 values for segment 1
        # All all 18 elements
        expected_paths = [
            [  # IDX_SEG element 0 has 3 IDX_LAY elements
                [  # IDX_LAY element 0 has 1 IDX_POS elements
                    "segments[0].layers[0].test.positions[0]"
                ],
                [  # IDX_LAY element 1 has 3 IDX_POS elements
                    "segments[0].layers[1].test.positions[0]",
                    "segments[0].layers[1].test.positions[1]",
                    "segments[0].layers[1].test.positions[2]",
                ],
                [  # IDX_LAY element 2 has 2 IDX_POS elements
                    "segments[0].layers[2].test.positions[0]",
                    "segments[0].layers[2].test.positions[1]",
                ],
            ],
            [  # IDX_SEG element 1 has 4 IDX_LAY elements
                [  # IDX_LAY element 0 has 5 IDX_POS elements
                    "segments[1].layers[0].test.positions[0]",
                    "segments[1].layers[0].test.positions[1]",
                    "segments[1].layers[0].test.positions[2]",
                    "segments[1].layers[0].test.positions[3]",
                    "segments[1].layers[0].test.positions[4]",
                ],
                [  # IDX_LAY element 0 has 1 IDX_POS elements
                    "segments[1].layers[1].test.positions[0]",
                ],
                [  # IDX_LAY element 0 has 2 IDX_POS elements
                    "segments[1].layers[2].test.positions[0]",
                    "segments[1].layers[2].test.positions[1]",
                ],
                [  # IDX_LAY element 0 has 4 IDX_POS elements
                    "segments[1].layers[3].test.positions[0]",
                    "segments[1].layers[3].test.positions[1]",
                    "segments[1].layers[3].test.positions[2]",
                    "segments[1].layers[3].test.positions[3]",
                ],
            ],
        ]

        paths = self.tree.prune_from_path(path, inplace=False).expand_path(path)
        self.assertSequenceEqual(paths, expected_paths)

        # Cannot expand without pruning
        with self.assertRaises(HubitError) as context:
            paths = self.tree.expand_path(path)

    def test_expand_path2(self):
        """Expand path"""
        paths = (
            HubitModelPath("segments[:@IDX_SEG].layers[:@IDX_LAY].test"),
            HubitQueryPath("segments[:].layers[:].test"),
        )

        # path = "segments.:@IDX_SEG.layers.:@IDX_LAY.test"
        seg_node = LengthNode(2)
        lay_nodes = LengthNode(2), LengthNode(2)
        seg_node.set_children(lay_nodes)

        nodes = [seg_node]
        nodes.extend(lay_nodes)
        level_names = "IDX_SEG", "IDX_LAY"
        tree = LengthTree(nodes, level_names)
        # 2  values for segment 0 and 2 values for segment 1
        expected_paths = [
            [
                "segments[0].layers[0].test",
                "segments[0].layers[1].test",
            ],
            [
                "segments[1].layers[0].test",
                "segments[1].layers[1].test",
            ],
        ]

        for path in paths:
            with self.subTest(path=path):
                expanded_paths = tree.prune_from_path(path).expand_path(path)
                self.assertSequenceEqual(expanded_paths, expected_paths)

    def test_expand_path_count_from_back(self):
        """Expand path with fixed index set to negative number"""
        path = HubitQueryPath("segments[:].layers[-2].test")

        seg_node = LengthNode(3)
        lay_nodes = LengthNode(2), LengthNode(4), LengthNode(3)
        seg_node.set_children(lay_nodes)

        nodes = [seg_node]
        nodes.extend(lay_nodes)
        level_names = "IDX_SEG", "IDX_LAY"
        tree = LengthTree(nodes, level_names)

        expected_paths = [
            "segments[0].layers[0].test",
            "segments[1].layers[2].test",
            "segments[2].layers[1].test",
        ]

        # Since the tree is not pruned we must use flat=True
        expanded_paths = tree.prune_from_path(path, inplace=False).expand_path(
            path, flat=True
        )
        self.assertSequenceEqual(expanded_paths, expected_paths)

        # Index error. There are 2 layers on segment at index 0.
        path = HubitQueryPath("segments[:].layers[-3].test")
        with self.assertRaises(HubitIndexError) as context:
            expanded_paths = tree.prune_from_path(path, inplace=False).expand_path(
                path, flat=True
            )

        tree, _ = _get_data()
        qpath = HubitQueryPath("sites[1].lines[0].tanks[-1].Q_yield")
        expanded_paths = tree.prune_from_path(qpath, inplace=False).expand_path(
            qpath, flat=True
        )
        assert expanded_paths == ["sites[1].lines[0].tanks[3].Q_yield"]

        qpath = HubitQueryPath("sites[0].lines[-1].tanks[-1].Q_yield")
        expanded_paths = tree.prune_from_path(qpath, inplace=False).expand_path(
            qpath, flat=True
        )
        assert expanded_paths == ["sites[0].lines[0].tanks[2].Q_yield"]

        qpath = HubitQueryPath("sites[:].lines[-1].tanks[-1].Q_yield")
        expanded_paths = tree.prune_from_path(qpath, inplace=False).expand_path(
            qpath, flat=True
        )
        assert expanded_paths == [
            "sites[0].lines[0].tanks[2].Q_yield",
            "sites[1].lines[0].tanks[3].Q_yield",
        ]

        qpath = HubitQueryPath("sites[:].lines[:].tanks[:].Q_yield")
        expanded_paths = tree.prune_from_path(qpath, inplace=False).expand_path(
            qpath, flat=True
        )

    def test_expand_mpath3(self):
        """Prune tree before expanding. Two indices vary so
        expanded paths is 2D
        """
        # 1 + 3 + 2 values for segment 0
        expected_paths = [
            [
                "segments[0].layers[0].test.positions[0]",
            ],
            [
                "segments[0].layers[1].test.positions[0]",
                "segments[0].layers[1].test.positions[1]",
                "segments[0].layers[1].test.positions[2]",
            ],
            [
                "segments[0].layers[2].test.positions[0]",
                "segments[0].layers[2].test.positions[1]",
            ],
        ]

        mpath = HubitModelPath(
            "segments[0@IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        )
        pruned_tree = self.tree.prune_from_path(mpath, inplace=False)
        paths = pruned_tree.expand_path(mpath)
        self.assertSequenceEqual(paths, expected_paths)

    def test_expand_mpath4(self):
        """Prune tree before expanding. One index varies so
        expanded paths is 1D
        """
        print(self.tree)
        path = HubitModelPath(
            "segments[0@IDX_SEG].layers[:@IDX_LAY].test.positions[1@IDX_POS]"
        )
        # path = HubitModelPath("segments[0].layers[:@IDX_LAY].test.positions[1]")
        template_path = HubitModelPath(
            "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        )
        self.tree.prune_from_path(path)
        # 1 + 3 + 2 values for segment 0
        expected_paths = [
            "segments[0].layers[1].test.positions[1]",
            "segments[0].layers[2].test.positions[1]",
        ]
        paths = self.tree.expand_path(path)
        self.assertSequenceEqual(paths, expected_paths)

    def test_expand_mpath5(self):
        """Expand subscription path with two wildcards gives a nested list"""
        input_data = {
            "items": [
                {"attr": {"items": [{"path": 2}, {"path": 1}]}},
                {"attr": {"items": [{"path": 3}, {"path": 4}]}},
            ],
            "some_number": 33,
        }
        path_consumed_for_name = {
            "attrs": HubitModelPath("items[:@IDX1].attr.items[:@IDX2].path"),
            "number": HubitModelPath("some_number"),
        }
        expected_result = {
            "attrs": [
                ["items[0].attr.items[0].path", "items[0].attr.items[1].path"],
                ["items[1].attr.items[0].path", "items[1].attr.items[1].path"],
            ],
            "number": ["some_number"],
        }
        tree_for_name = {
            name: LengthTree.from_data(path, input_data)
            for name, path in path_consumed_for_name.items()
        }

        result = {
            name: tree.prune_from_path(path_consumed_for_name[name]).expand_path(
                path_consumed_for_name[name]
            )
            for name, tree in tree_for_name.items()
        }

        self.assertDictEqual(expected_result, result)

    def test_expand_mpath6(self):
        """As test 8 but the consumed path only subscribes to element 1
        of the (leftmost) items. Thus, the expansion leads to a flat list
        corresponding to the (rightmost) items
        """
        input_data = {
            "items_a": [
                {"attr": {"items": [{"path": 2}, {"path": 1}]}},
                {"attr": {"items": [{"path": 3}, {"path": 4}]}},
            ],
            "some_number": 33,
        }

        path_consumed_for_name = {
            "attrs": HubitModelPath("items_a[1@IDX1].attr.items[:@IDX2].path"),
            "number": HubitModelPath("some_number"),
        }

        expected_result = {
            "attrs": ["items_a[1].attr.items[0].path", "items_a[1].attr.items[1].path"],
            "number": ["some_number"],
        }

        tree_for_name = {
            name: LengthTree.from_data(path, input_data, prune=True)
            for name, path in path_consumed_for_name.items()
        }

        tree_for_name["attrs"].prune_from_path(path_consumed_for_name["attrs"])

        result = {
            name: tree.expand_path(path_consumed_for_name[name])
            for name, tree in tree_for_name.items()
        }
        self.assertDictEqual(expected_result, result)

    def test_none_like_1(self):
        """
        Get a nested list corresponding to the tree
        """
        print(self.tree)
        result = self.tree.none_like()
        expected_result = [
            [[None], [None, None, None], [None, None]],
            [
                [None, None, None, None, None],
                [None],
                [None, None],
                [None, None, None, None],
            ],
        ]
        print(expected_result)
        self.assertListEqual(result, expected_result)

    def test_none_like_2(self):
        """
        Get a nested list corresponding to a tree with
        only node element per nested list
        """
        #
        yml_input = """
                        segments:
                            - layers:
                                - dummy1: 0.1 
                                  dummy2: dummy_value
                                  test:
                                    positions: 
                                        - 1
                    """
        input_data = yaml.load(yml_input, Loader=yaml.FullLoader)

        # Point to all elements
        path = HubitModelPath(
            "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        )
        tree = LengthTree.from_data(path, input_data)
        # print(tree)
        # print(tree.to_list())
        result = tree.none_like()
        print(result)
        # expected_result = [None]
        # self.assertListEqual(result, expected_result)

        path = HubitModelPath(
            "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions[IDX_POS]"
        )
        tree = LengthTree.from_data(path, input_data)
        # print(tree)
        # print(tree.to_list())
        result = tree.none_like()
        print(result)
        # self.assertListEqual(result, expected_result)

    def test_none_like_2(self):
        """
        Get a nested list corresponding to a tree with
        only node element per nested list
        """
        #
        yml_input = """
                        segments:
                            - layers:
                                - dummy1: 0.1 
                                  dummy2: dummy_value
                                  test:
                                    positions: 
                                        - 1
                                        - 2
                    """
        input_data = yaml.load(yml_input, Loader=yaml.FullLoader)

        # Point to all elements
        path = HubitModelPath(
            "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        )
        tree = LengthTree.from_data(path, input_data)
        # print(tree)
        # print(tree.to_list())
        result = tree.none_like()
        print(result)
        # expected_result = [None]
        # self.assertListEqual(result, expected_result)

        path = HubitModelPath(
            "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions[IDX_POS]"
        )
        tree = LengthTree.from_data(path, input_data)
        # print(tree)
        # print(tree.to_list())
        result = tree.none_like()
        print(result)
        # self.assertListEqual(result, expected_result)

    def test_none_like_3(self):
        """
        Get a nested list corresponding to a tree with
        only node element per nested list
        """
        #
        yml_input = """
                    layers:
                      - dummy1: 0.1 
                        dummy2: dummy_value
                        test:
                          positions: 
                            - 1
                            - 2
                      - dummy1: 0.1 
                        dummy2: dummy_value
                        test:
                          positions: 
                            - 1
                    """
        input_data = yaml.load(yml_input, Loader=yaml.FullLoader)

        # Point to all elements
        path = HubitModelPath("layers[:@IDX_LAY].test.positions[:@IDX_POS]")
        tree = LengthTree.from_data(path, input_data)
        # print(tree)
        # print(tree.to_list())
        result = tree.none_like()
        print(result)
        # expected_result = [None]
        # self.assertListEqual(result, expected_result)

        path = HubitModelPath("layers[:@IDX_LAY].test.positions[IDX_POS]")
        tree = LengthTree.from_data(path, input_data)
        # print(tree)
        # print(tree.to_list())
        result = tree.none_like()
        print(result)
        # self.assertListEqual(result, expected_result)

    def test_none_like_4(self):
        """
        Get a nested list corresponding to a tree with
        only node element per nested list
        """
        # Two nested lists of length 1
        yml_inputs = {
            "1d": """
                    layers:
                      - dummy1: 0.1 
                        dummy2: dummy_value
                        test:
                          positions: 
                            - 1
                    """,
            "2d": """
                    layers:
                      - dummy1: 0.1 
                        dummy2: dummy_value
                        test:
                          positions: 
                            - 1
                            - 2
                      - dummy1: 0.1 
                        dummy2: dummy_value
                        test:
                          positions: 
                            - 3
                            - 4
                    """,
        }

        test_items = [
            (
                HubitModelPath("layers[:@IDX_LAY].test.positions[:@IDX_POS]"),
                None,
                {"1d": [[None]], "2d": [[None, None], [None, None]]},
            ),
            (
                HubitModelPath("layers[0@IDX_LAY].test.positions[0@IDX_POS]"),
                None,
                {"1d": None, "2d": None},
            ),
            (
                HubitModelPath("layers[0@IDX_LAY].test.positions[:@IDX_POS]"),
                None,
                {"1d": [None], "2d": [None, None]},
            ),
            (
                HubitModelPath("layers[:@IDX_LAY].test.positions[0@IDX_POS]"),
                None,
                {"1d": [None], "2d": [None, None]},
            ),
            (
                HubitModelPath("layers[:@IDX_LAY].test.positions[:@IDX_POS]"),
                HubitQueryPath("layers[:].test.positions[:]"),
                {"1d": [[None]], "2d": [[None, None], [None, None]]},
            ),
            (
                HubitModelPath("layers[:@IDX_LAY].test.positions[:@IDX_POS]"),
                HubitQueryPath("layers[0].test.positions[0]"),
                {"1d": None, "2d": None},
            ),
            (
                HubitModelPath("layers[:@IDX_LAY].test.positions[:@IDX_POS]"),
                HubitQueryPath("layers[:].test.positions[0]"),
                {"1d": [None], "2d": [None, None]},
            ),
            (
                HubitModelPath("layers[:@IDX_LAY].test.positions[:@IDX_POS]"),
                HubitQueryPath("layers[0].test.positions[:]"),
                {"1d": [None], "2d": [None, None]},
            ),
        ]

        for input_id, yml_input in yml_inputs.items():
            input_data = yaml.load(yml_input, Loader=yaml.FullLoader)

            for test_item in test_items:
                mpath, qpath, expected_result = test_item
                expected_result = expected_result[input_id]
                tree = LengthTree.from_data(mpath, input_data, prune=True)
                if qpath is not None:
                    tree.prune_from_path(qpath)
                print("Test:", input_id, mpath, qpath)
                result = tree.none_like()
                with self.subTest(
                    result=result,
                    expected_result=expected_result,
                    mapth=mpath,
                    qpath=qpath,
                    input_id=input_id,
                ):
                    if expected_result is None:
                        self.assertEqual(result, expected_result)
                    else:
                        self.assertListEqual(result, expected_result)

    def test_is_path_described_query_paths(self):
        print(self.tree)

        # Path with no ranges is not described by a LengthTree
        assert not self.tree.is_path_described(HubitQueryPath("i.dont.exist"))

        assert self.tree.is_path_described(
            HubitQueryPath("segments[0].layers[0].test.positions[0]")
        )

        assert not self.tree.is_path_described(
            HubitQueryPath("segments[0].layers[0].test.positions[1]")
        )

        assert not self.tree.is_path_described(
            HubitQueryPath("segments[7].layers[0].test.positions[1]")
        )

        assert self.tree.is_path_described(
            HubitQueryPath("segments[1].layers[0].test.positions[4]")
        )

        assert not self.tree.is_path_described(
            HubitQueryPath("segments[1].layers[0].test.positions[5]")
        )

        # At least one segment has 4 positions on layer 0
        assert self.tree.is_path_described(
            HubitQueryPath("segments[:].layers[0].test.positions[4]")
        )

        # No segment has 5 positions on layer 0
        assert not self.tree.is_path_described(
            HubitQueryPath("segments[:].layers[0].test.positions[5]")
        )

    def test_is_path_described_model_paths(self):
        print(self.tree)

        # Path with no ranges is not described by a LengthTree
        assert not self.tree.is_path_described(HubitModelPath("i.dont.exist"))

        assert self.tree.is_path_described(
            HubitModelPath(
                "segments[0@IDX_SEG].layers[0@IDX_LAY].test.positions[0@IDX_POS]"
            )
        )

        assert not self.tree.is_path_described(
            HubitModelPath(
                "segments[0@IDX_SEG].layers[0@IDX_LAY].test.positions[1@IDX_POS]"
            )
        )

        # Wrong index context
        assert not self.tree.is_path_described(
            HubitModelPath(
                "segments[0@IDX_WRONG].layers[0@IDX_LAY].test.positions[0@IDX_POS]"
            )
        )


# TODO: test if len(mpaths) > 1 and not path.has_slice_range():
class TestQueryExpansion(unittest.TestCase):
    def test_decompose_query(self):

        qpath = HubitQueryPath("lines[:].tanks[:].vol_outlet_flow")
        mpaths = [
            "lines[IDX_LINE].tanks[0@IDX_TANK].vol_outlet_flow",
            "lines[IDX_LINE].tanks[1@IDX_TANK].vol_outlet_flow",
            "lines[IDX_LINE].tanks[2@IDX_TANK].vol_outlet_flow",
        ]
        mpaths = [HubitModelPath(mpath) for mpath in mpaths]
        result, index_identifiers = _QueryExpansion.decompose_query(qpath, mpaths)
        index_identifiers = set(index_identifiers)
        self.assertTrue(len(index_identifiers) == 1)
        self.assertIn("IDX_TANK", index_identifiers)
        self.assertTrue(len(result) == len(mpaths))
        expected_result = [
            "lines[:].tanks[0].vol_outlet_flow",
            "lines[:].tanks[1].vol_outlet_flow",
            "lines[:].tanks[2].vol_outlet_flow",
        ]
        self.assertListEqual(result, expected_result)

    def test_init(self):
        # Success
        qpath = HubitQueryPath("lines[:].tanks[:].vol_outlet_flow")
        mpaths = [
            "lines[IDX_LINE].tanks[0@IDX_TANK].vol_outlet_flow",
            "lines[IDX_LINE].tanks[1@IDX_TANK].vol_outlet_flow",
            "lines[IDX_LINE].tanks[2@IDX_TANK].vol_outlet_flow",
        ]
        mpaths = [HubitModelPath(mpath) for mpath in mpaths]
        # Use a dummy tree. It will not be used since the path normalization is bypassed
        tree = DummyLengthTree()
        cmps = get_mock_components(mpaths)
        _QueryExpansion(qpath, mpaths, tree, cmps)

        # mpaths cannot have different index contexts
        qpath = HubitQueryPath("lines[:].tanks[:].vol_outlet_flow")
        mpaths = [
            "lines[IDX_LINE].tanks[0@IDX_TANK].vol_outlet_flow",
            "lines[IDX_LINE].tanks[1@IDX_OTHER].vol_outlet_flow",
        ]
        mpaths = [HubitModelPath(mpath) for mpath in mpaths]
        cmps = get_mock_components(mpaths)
        with pytest.raises(HubitModelQueryError):
            _QueryExpansion(qpath, mpaths, tree, cmps)

        # No mpaths i.e. no provider
        qpath = HubitQueryPath("lines[:].tanks[:].vol_outlet_flow")
        mpaths = []
        cmps = get_mock_components(mpaths)
        with pytest.raises(HubitModelQueryError):
            _QueryExpansion(qpath, mpaths, tree, cmps)

    def _get_qexp():

        path = HubitModelPath("lines[IDX_LINE].tanks[0@IDX_TANK].vol_outlet_flow")
        yml_input = """
        lines:
            - tanks:
                - tank1: 1
                - tank2: 2
                - tank3: 3
            - tanks:
                - tank1: 1
                - tank2: 2
                - tank3: 3
                - tank4: 4
        """
        input_data = yaml.load(yml_input, Loader=yaml.FullLoader)

        tree = LengthTree.from_data(path, input_data)

        qpath = HubitQueryPath("lines[:].tanks[:].vol_outlet_flow")
        mpaths = [
            "lines[IDX_LINE].tanks[0@IDX_TANK].vol_outlet_flow",
            "lines[IDX_LINE].tanks[1@IDX_TANK].vol_outlet_flow",
            "lines[IDX_LINE].tanks[2@IDX_TANK].vol_outlet_flow",
        ]
        mpaths = [HubitModelPath(mpath) for mpath in mpaths]
        cmps = get_mock_components(mpaths)

        qexp = _QueryExpansion(qpath, mpaths, tree, cmps)

        return qexp

    def test_validate_tree(self):
        qexp = TestQueryExpansion._get_qexp()
        qexp._validate_tree()

        # DummyTree passes validation
        path = HubitModelPath("segments.layers.positions")
        qexp.tree = LengthTree.from_data(path, {})
        qexp._validate_tree()

    def test_validate_tree_fail(self):

        qexp = TestQueryExpansion._get_qexp()

        # Tree corresponds to something 'segments[IDX_SEG].layers[IDX_LAY]'
        # while qexp was decomposed for the identifier 'IDX_TANK'
        path = HubitModelPath("segments[IDX_SEG].layers[:@IDX_LAY]")
        yml_input = """
        segments:
            - layers:
                - thickness: 0.1 # [m]
                  material: brick
                - thickness: 0.1
                  material: brick
            - layers:
                - thickness: 0.15
                  material: concrete
                - thickness: 0.1
                  material: concrete
        """
        input_data = yaml.load(yml_input, Loader=yaml.FullLoader)

        qexp.tree = LengthTree.from_data(path, input_data)
        with pytest.raises(HubitError):
            qexp._validate_tree()

    @staticmethod
    def _get_tests():

        # Test1
        mpaths = [
            "sites[IDX_SITE].lines[IDX_LINE].tanks[IDX_TANK].Q_yield",
        ]
        cmps = get_mock_components(mpaths)
        tests = [(mpaths, cmps)]
        # Test 2
        mpaths = [
            "sites[IDX_SITE].lines[IDX_LINE].tanks[0@IDX_TANK].Q_yield",
            "sites[IDX_SITE].lines[IDX_LINE].tanks[1@IDX_TANK].Q_yield",
            "sites[IDX_SITE].lines[IDX_LINE].tanks[2:@IDX_TANK].Q_yield",
        ]
        # Explicitly defining tank three doesn't work since it doesn't exits for the first site
        # "sites[IDX_SITE].lines[IDX_LINE].tanks[2@IDX_TANK].Q_yield",
        # "sites[IDX_SITE].lines[IDX_LINE].tanks[3@IDX_TANK].Q_yield",
        cmps = get_mock_components(mpaths)

        tests.append((mpaths, cmps))
        return tests

    def test_collect_results(self):
        """
        Test that the flat results are collected correctly when forming the response

        - 1 provider -> 1 mpath
        - 1 production site
        """
        tree, flat_results = _get_data()
        test_items = TestQueryExpansion._get_tests()

        for mpaths, cmps in test_items:
            mpaths = [HubitModelPath(mpath) for mpath in mpaths]
            with self.subTest(mpaths=mpaths, cmps=cmps):
                # Positive indices
                qpath = HubitQueryPath("sites[0].lines[0].tanks[0].Q_yield")
                _tree = tree.prune_from_path(qpath, inplace=False)
                qexp = _QueryExpansion(qpath, mpaths, _tree, cmps)
                result = qexp.collect_results(flat_results)
                # Query has two index wildcards hence nested list
                assert result == 10.0

                # Positive indices
                qpath = HubitQueryPath("sites[1].lines[0].tanks[3].Q_yield")
                _tree = tree.prune_from_path(qpath, inplace=False)
                qexp = _QueryExpansion(qpath, mpaths, _tree, cmps)
                result = qexp.collect_results(flat_results)
                # Query has two index wildcards hence nested list
                assert result == 1.0

                # Negative indices
                qpath = HubitQueryPath("sites[-1].lines[-1].tanks[-1].Q_yield")
                qpath = HubitQueryPath("sites[1].lines[0].tanks[-1].Q_yield")
                _tree = tree.prune_from_path(qpath, inplace=False)
                qexp = _QueryExpansion(qpath, mpaths, _tree, cmps)
                result = qexp.collect_results(flat_results)
                # Query has two index wildcards hence nested list
                assert result == 1.0

                # Negative index
                qpath = HubitQueryPath("sites[:].lines[:].tanks[-1].Q_yield")
                _tree = tree.prune_from_path(qpath, inplace=False)
                qexp = _QueryExpansion(qpath, mpaths, _tree, cmps)
                result = qexp.collect_results(flat_results)
                # Query has two index wildcards hence nested list
                assert result == [[4.0], [1.0]]

                # Positive index
                qpath = HubitQueryPath("sites[:].lines[:].tanks[2].Q_yield")
                _tree = tree.prune_from_path(qpath, inplace=False)
                qexp = _QueryExpansion(qpath, mpaths, _tree, cmps)
                result = qexp.collect_results(flat_results)
                # Query has two index wildcards hence nested list
                assert result == [[4.0], [3.0]]

                # All tanks on all lines
                qpath = HubitQueryPath("sites[0].lines[:].tanks[:].Q_yield")
                _tree = tree.prune_from_path(qpath, inplace=False)
                qexp = _QueryExpansion(qpath, mpaths, _tree, cmps)
                result = qexp.collect_results(flat_results)
                # Query has two index wildcards hence nested list
                assert result == [[10.0, 6.0, 4.0]]

                # All tanks on all lines in all sites
                qpath = HubitQueryPath("sites[:].lines[:].tanks[:].Q_yield")
                _tree = tree.prune_from_path(qpath, inplace=False)
                qexp = _QueryExpansion(qpath, mpaths, _tree, cmps)
                result = qexp.collect_results(flat_results)
                # Query has two index wildcards hence nested list
                assert result == [[[10.0, 6.0, 4.0]], [[20.0, 8.0, 3.0, 1.0]]]

    def test_filter_mpaths_for_qpath_index_ranges(self):
        qpath = HubitQueryPath("sites[0].lines[0].tanks[:].Q_yield")
        mpaths = [
            HubitModelPath(
                "sites[0@IDX_SITE].lines[0@IDX_LINE].tanks[IDX_TANK].Q_yield"
            ),
            HubitModelPath(
                "sites[0@IDX_SITE].lines[0@IDX_LINE].tanks[IDX_TANK].Q_yield"
            ),
            HubitModelPath(
                "sites[0@IDX_SITE].lines[1@IDX_LINE].tanks[IDX_TANK].Q_yield"
            ),
        ]

        # Index scpoe for each mpath
        index_scopes = [
            {"IDX_TANK": PathIndexRange("0")},
            {"IDX_TANK": PathIndexRange("1:")},
            {"IDX_TANK": PathIndexRange(":")},
        ]
        tree, _ = _get_data()
        pruned_tree = tree.prune_from_path(qpath, inplace=False)

        result = _QueryExpansion._filter_mpaths_for_qpath_index_ranges(
            qpath,
            mpaths,
            index_scopes,
            pruned_tree,
        )

        expected_result = [
            mpath.set_range_for_idxid(index_scope)
            for mpath, index_scope in zip(mpaths[:2], index_scopes[:2])
        ]
        assert result == expected_result


if __name__ == "__main__":
    unittest.main()
