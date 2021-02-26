import unittest
import yaml

from hubit import shared


def get_data():
    cfg = {
        "provides": [
            {"name": "attrs1", "path": "items.:.attr.items.:.path1"},
            {"name": "attr2", "path": "attr2.path"},
        ],
        "consumes": {
            "input": [{"name": "attr", "path": "items.:.attr.path"}],
            "results": {},
        },
    }

    inputdata = {
        "items": [
            {"attr": {"items": [{"path": 2}, {"path": 1}]}},
            {"attr": {"items": [{"path": 3}, {"path": 4}]}},
        ]
    }
    return cfg, inputdata


class TestShared(unittest.TestCase):
    def setUp(self):
        self.flat_input = {
            "segs.0.walls.0.kval": 1,
            "segs.0.walls.1.kval": 2,
            "segs.0.walls.2.kval": None,
            "segs.1.walls.0.kval": 3,
            "segs.1.walls.1.kval": 7,
            "segs.1.walls.2.kval": 5,
            "segs.0.length": 13,
            "segs.1.length": 14,
            "weight": 567,
        }

        self.providerstring = "segs[IDXSEG].walls[IDXWALL].temps"
        self.querystring = "segs[42].walls[3].temps"
        self.idxids = shared.idxids_from_path(self.providerstring)

    def test_get_indices(self):
        """Test that indices from query string are extracted correctly"""
        mpath = shared.convert_to_internal_path(self.providerstring)
        qpath = shared.convert_to_internal_path(self.querystring)
        idxs = shared.get_iloc_indices(qpath, mpath, self.idxids)
        idxs_expected = ("42", "3")
        self.assertSequenceEqual(idxs, idxs_expected)

    def test_get_matches(self):
        """Test that we can find the provider strings
        that match the query
        """
        providerstrings = (
            "price",
            self.providerstring,
            "segs[IDXSEG].walls.thicknesses",
            self.querystring,
            "segs[IDXSEG].walls[IDXWALL].thicknesses",
            "segs[IDXSEG].walls[IDXWALL]",
        )

        idxs_match_expected = (1, 3)
        idxs_match = shared.idxs_for_matches(self.querystring, providerstrings)
        self.assertSequenceEqual(idxs_match, idxs_match_expected)

    def test_set_ilocs(self):
        """Insert real numbers where the ILOC placeholder is found"""
        expected_pathstr = "segs[34].walls[3].temps"
        path = shared.set_ilocs_on_path(
            "segs[IDXSEG].walls[IDXWALL].temps", ("34", "3")
        )
        self.assertEqual(path, expected_pathstr)

    def test_set_ilocs_with_wildcard(self):
        """Insert real numbers where the ILOC placeholder is found"""
        expected_pathstr = "segs[34].walls[:@IDXWALL].temps"
        path = shared.set_ilocs_on_path(
            "segs[IDXSEG].walls[:@IDXWALL].temps", ("34", "3")
        )
        self.assertEqual(path, expected_pathstr)

    @staticmethod
    def get_tree():
        seg_node = shared.LengthNode(2)
        wall_nodes = shared.LengthNode(3), shared.LengthNode(3)
        seg_node.set_children(wall_nodes)
        nodes = [seg_node]
        nodes.extend(wall_nodes)
        tree = shared.LengthTree(nodes, level_names=["IDXSEG", "IDXWALL"])
        return tree

    # def test_expand_mpath(self):
    #     """Expand a query that uses : to its constituents

    #     TODO: move to Tree Test or delete if not longer neede.
    #     """
    #     tree = TestShared.get_tree()
    #     query= "segs.:@IDXSEG.walls.:@IDXWALL.temps"
    #     paths = tree.expand_path(query, flat=True)
    #     expected_length = sum( [node.nchildren()
    #                             for node in tree.nodes_for_level[-1]]
    #                          )
    #     length = len(paths)
    #     self.assertTrue( length == expected_length )

    # def test_expand_mpath2(self):
    #     """Expand a query that does not use : to its constituents
    #     i.e. itself

    #     TODO: move to Tree Test or delete if not longer neede.
    #     """
    #     tree = TestShared.get_tree()
    #     model_path= "segs.:@IDXSEG.walls.:@IDXWALL.temps"
    #     query = "segs.0.walls.0.kval"
    #     paths = tree.prune_from_path(query, model_path).expand_path(query, flat=True)
    #     expected_length = 1
    #     length = len(paths)
    #     self.assertTrue( length == expected_length )

    def test_query_all(self):
        """"""
        self.skipTest("Feature not used yet")
        providerstrings = (
            "price",
            "segs._ILOC.walls.values",
            "segs._ILOC.walls._ILOC.heat_flow",
            "segs._ILOC.walls._ILOC.temp_in",
        )

        qall = shared.query_all(providerstrings, self.flat_input, self.ilocstr)
        # Make general query
        print(qall)

    def test_get_from_datadict(self):
        """Extract value from nested dict using a list of keys."""
        datadict = {"a": {"b": [4, 5]}}
        # Should all be of type string
        keys = ["a", "b", "0"]
        value = shared.get_from_datadict(datadict, keys)
        self.assertTrue(value == 4)

    def test_traverse(self):
        """ Thest iterator that traverses nested list """
        l0 = "as", "fv", "dsd", ["fr", "hj", ["gb", 0]]
        self.assertTrue(len(list(shared.traverse(l0))) == 7)

    def test_x(self):
        self.skipTest("Feature not used yet... and not sure what it is")
        cfg, inputdata = get_data()
        path = cfg["provides"]["attrs1"]

        # iterate over all indices
        import itertools

        shape = (2, 3)
        for ilocs in itertools.product(*[range(s) for s in shape]):
            print(ilocs)

        paths = [["attr1", "attr2"], ["attr3", "attr4"]]
        valuemap = {"attr1": 1, "attr2": 2, "attr3": 3, "attr4": 4}

        print("XXX", shared.setelemtents(paths, valuemap))


class TestPath(unittest.TestCase):
    def test_1(self):
        """Extract idxids from path"""
        path = "segs[IDX_SEG].walls[IDX_WALL].heat_flow"
        expected_idxids = ["IDX_SEG", "IDX_WALL"]
        idxids = shared.idxids_from_path(path)
        self.assertSequenceEqual(expected_idxids, idxids)

    def test_2(self):
        """Convert from Hubit user path to internal Hubit path"""
        path = "segs[IDX_SEG].walls[IDX_WALL].heat_flow"
        expected_internal_path = "segs.IDX_SEG.walls.IDX_WALL.heat_flow"
        internal_path = shared.convert_to_internal_path(path)
        self.assertSequenceEqual(expected_internal_path, internal_path)

    def test_2a(self):
        """Convert from Hubit user path to internal Hubit path"""
        path = "segs[:@IDX_SEG].walls[:@IDX_WALL].heat_flow"
        expected_internal_path = "segs.:@IDX_SEG.walls.:@IDX_WALL.heat_flow"
        internal_path = shared.convert_to_internal_path(path)
        self.assertSequenceEqual(expected_internal_path, internal_path)

    def test_3(self):
        path = "segments[IDX_SEG].layers[IDX_LAY].test.positions[IDX_POS]"
        idxids = shared.idxids_from_path(path)
        internal_paths = shared._paths_between_idxids(path, idxids)
        # Last element is empty since there are no attribute after IDX_POS
        expected_internal_paths = ["segments", "layers", "test.positions", ""]
        self.assertSequenceEqual(expected_internal_paths, internal_paths)


class TestTree(unittest.TestCase):
    def setUp(self):
        # lengths = [['IDX_SEG', 2],
        #            ['IDX_LAY', [3, 4]],
        #            ['IDX_POS', [[1, 3, 2], [5, 1, 2, 4]]]]

        seg_nodes = shared.LengthNode(2)
        lay_nodes = shared.LengthNode(3), shared.LengthNode(4)
        pos_lay0_nodes = (
            shared.LengthNode(1),
            shared.LengthNode(3),
            shared.LengthNode(2),
        )
        pos_lay1_nodes = (
            shared.LengthNode(5),
            shared.LengthNode(1),
            shared.LengthNode(2),
            shared.LengthNode(4),
        )

        seg_nodes.set_children(lay_nodes)
        lay_nodes[0].set_children(pos_lay0_nodes)
        lay_nodes[1].set_children(pos_lay1_nodes)

        nodes = [seg_nodes]
        nodes.extend(lay_nodes)
        nodes.extend(pos_lay0_nodes)
        nodes.extend(pos_lay1_nodes)
        level_names = "IDX_SEG", "IDX_LAY", "IDX_POS"
        self.tree = shared.LengthTree(nodes, level_names)
        self.template_path = (
            "segments.:@IDX_SEG.layers.:@IDX_LAY.test.positions.:@IDX_POS"
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
        path = "segments[IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"

        tree = shared.LengthTree.from_data(path, input_data)
        tree_as_list = tree.to_list()
        # print(tree_as_list)
        # TODO test paths in this case
        # path = "segments[:@IDX_SEG].layers[:@IDX_LAY].test"
        expected_lengths = [2, [3, 4], [[1, 3, 2], [5, 1, 2, 4]]]
        self.assertSequenceEqual(expected_lengths, tree_as_list)

    def test_from_data2(self):
        """No lengths since there are no index IDs in path"""
        path = "segments.layers.positions"
        calculated_tree = shared.LengthTree.from_data(path, {})
        self.assertIsInstance(calculated_tree, shared.DummyLengthTree)

    def test_0(self):
        """path is identical to template_path so the tree remains unchanged"""
        path = self.template_path
        pruned_tree = self.tree.prune_from_path(path, self.template_path, inplace=False)
        self.assertEqual(self.tree, pruned_tree)

    def test_1(self):
        """Top level index fixed to 0"""
        path = "segments.0.layers.:@IDX_LAY.test.positions.:@IDX_POS"
        self.tree.prune_from_path(path, self.template_path)
        expected_lengths = [1, 3, [1, 3, 2]]
        self.assertListEqual(self.tree.to_list(), expected_lengths)

    def test_2(self):
        """Top level index fixed to 1"""
        path = "segments.1.layers.:@IDX_LAY.test.positions.:@IDX_POS"
        self.tree.prune_from_path(path, self.template_path)
        expected_lengths = [1, 4, [5, 1, 2, 4]]
        self.assertListEqual(self.tree.to_list(), expected_lengths)

    def test_2a(self):
        """Outside bounds top level index"""
        path = "segments.2.layers.:@IDX_LAY.test.positions.:@IDX_POS"
        with self.assertRaises(shared.HubitIndexError) as context:
            self.tree.prune_from_path(path, self.template_path)

    def test_3(self):
        """Middle index fixed"""
        path = "segments.:@IDX_SEG.layers.1.test.positions.:@IDX_POS"
        expected_lengths = [
            2,
            [1, 1],
            [
                [
                    3,
                ],
                [
                    1,
                ],
            ],
        ]
        self.tree.prune_from_path(path, self.template_path)
        self.assertListEqual(self.tree.to_list(), expected_lengths)

    def test_4(self):
        """In bounds for all bottom-most paths."""
        path = "segments.:@IDX_SEG.layers.:@IDX_LAY.test.positions.0"
        expected_lengths = [2, [3, 4], [[1, 1, 1], [1, 1, 1, 1]]]
        self.tree.prune_from_path(path, self.template_path)
        self.assertListEqual(self.tree.to_list(), expected_lengths)

    def test_5(self):
        """Two indices fixed"""
        path = "segments.1.layers.:@IDX_LAY.test.positions.0"
        expected_lengths = [1, 4, [1, 1, 1, 1]]
        self.tree.prune_from_path(path, self.template_path)
        # print(self.tree)
        self.assertListEqual(self.tree.to_list(), expected_lengths)

    def test_5a(self):
        """Out of bounds for all but two paths

        [['IDX_SEG', 2*], -> 1
        ['IDX_LAY', [3, 4*]], -> 2
        ['IDX_POS', [[1, 3, 2], [5*, 1, 2, 4*]]]] -> [1, 1]
        """
        path = "segments.:@IDX_SEG.layers.:@IDX_LAY.test.positions.3"
        expected_lengths = [1, 2, [1, 1]]
        self.tree.prune_from_path(path, self.template_path)
        self.assertListEqual(self.tree.to_list(), expected_lengths)

    def test_6(self):
        """Out of bounds for all paths"""
        path = "segments.:@IDX_SEG.layers.:@IDX_LAY.test.positions.17"
        with self.assertRaises(shared.HubitIndexError) as context:
            self.tree.prune_from_path(path, self.template_path)

    def test_prune(self):
        def print_test(tree):
            nodes = tree.nodes_for_level[0]
            for node in nodes:
                print("node", node)
                for child in node.children:
                    print("child", child)

        idx_car_node = shared.LengthNode(2)
        idx_parts_nodes = shared.LengthNode(5), shared.LengthNode(4)
        idx_car_node.set_children(idx_parts_nodes)
        nodes = [idx_car_node]
        nodes.extend(idx_parts_nodes)
        level_names = "IDX_CAR", "IDX_CAR"
        tree = shared.LengthTree(nodes, level_names)
        clipped_tree = tree.clip_at_level("IDX_CAR", inplace=False)

        # nodes or bottom level
        nodes = clipped_tree.nodes_for_level[-1]

        # all children should be None at bottom level
        children_is_none = [
            all([child is None for child in node.children]) for node in nodes
        ]

        with self.subTest():
            self.assertTrue(all(children_is_none))

        with self.subTest():
            self.assertTrue(len(clipped_tree.level_names) == 1)

        with self.subTest():
            self.assertTrue(len(clipped_tree.nodes_for_level) == 1)

    def test_7(self):
        """4-level tree"""
        x1_nodes = shared.LengthNode(2)
        x2_nodes = shared.LengthNode(1), shared.LengthNode(3)
        x3_0_nodes = [shared.LengthNode(2)]
        x3_1_nodes = shared.LengthNode(1), shared.LengthNode(2), shared.LengthNode(4)
        x4_0_0_nodes = shared.LengthNode(1), shared.LengthNode(3)
        x4_1_0_nodes = [shared.LengthNode(1)]
        x4_1_1_nodes = shared.LengthNode(2), shared.LengthNode(2)
        x4_1_2_nodes = (
            shared.LengthNode(1),
            shared.LengthNode(1),
            shared.LengthNode(1),
            shared.LengthNode(2),
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
        tree = shared.LengthTree(nodes, level_names)
        expected_lengths = [
            2,
            [1, 3],
            [[2], [1, 2, 4]],
            [[[1, 3]], [[1], [2, 2], [1, 1, 1, 2]]],
        ]
        self.assertListEqual(tree.to_list(), expected_lengths)

    def test_normalize_path1(self):
        """
        First index ID is negative so no context
        """
        qpath = "segments[-1].layers[XX].test.positions[YY]"
        normalized_qpath_expected = "segments[1].layers[XX].test.positions[YY]"
        normalized_qpath = self.tree.normalize_path(qpath)
        self.assertEqual(normalized_qpath_expected, normalized_qpath)

    def test_normalize_path2(self):
        """
        Second index ID is negative there's context
        """
        qpaths = (
            "segments[0].layers[-1].test.positions[:]",
            "segments[1].layers[-1].test.positions[:]",
        )
        normalized_qpaths_expected = (
            "segments[0].layers[2].test.positions[:]",
            "segments[1].layers[3].test.positions[:]",
        )

        for qpath, expected_qpath in zip(qpaths, normalized_qpaths_expected):
            path = self.tree.normalize_path(qpath)
            with self.subTest(path=path, expected_qpath=expected_qpath):
                self.assertEqual(expected_qpath, path)

    def test_normalize_path3(self):
        qpath = "segments[1].layers[3].test.positions[-1]"
        expected_qpath = "segments[1].layers[3].test.positions[3]"
        normalized_qpath = self.tree.normalize_path(qpath)
        self.assertEqual(expected_qpath, normalized_qpath)

    def test_expand_mpath1(self):
        """Expand to full template path"""
        path = "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"

        # 1 + 3 + 2 values for segment 0 and 5 + 1 + 2 + 4 values for segment 1
        # All all 18 elements
        expected_paths = [
            [  # IDX_SEG element 0 has 3 IDX_LAY elements
                [  # IDX_LAY element 0 has 1 IDX_POS elements
                    "segments.0.layers.0.test.positions.0"
                ],
                [  # IDX_LAY element 1 has 3 IDX_POS elements
                    "segments.0.layers.1.test.positions.0",
                    "segments.0.layers.1.test.positions.1",
                    "segments.0.layers.1.test.positions.2",
                ],
                [  # IDX_LAY element 2 has 2 IDX_POS elements
                    "segments.0.layers.2.test.positions.0",
                    "segments.0.layers.2.test.positions.1",
                ],
            ],
            [  # IDX_SEG element 1 has 4 IDX_LAY elements
                [  # IDX_LAY element 0 has 5 IDX_POS elements
                    "segments.1.layers.0.test.positions.0",
                    "segments.1.layers.0.test.positions.1",
                    "segments.1.layers.0.test.positions.2",
                    "segments.1.layers.0.test.positions.3",
                    "segments.1.layers.0.test.positions.4",
                ],
                [  # IDX_LAY element 0 has 1 IDX_POS elements
                    "segments.1.layers.1.test.positions.0",
                ],
                [  # IDX_LAY element 0 has 2 IDX_POS elements
                    "segments.1.layers.2.test.positions.0",
                    "segments.1.layers.2.test.positions.1",
                ],
                [  # IDX_LAY element 0 has 4 IDX_POS elements
                    "segments.1.layers.3.test.positions.0",
                    "segments.1.layers.3.test.positions.1",
                    "segments.1.layers.3.test.positions.2",
                    "segments.1.layers.3.test.positions.3",
                ],
            ],
        ]

        paths = self.tree.expand_path(path, as_internal_path=True)
        self.assertSequenceEqual(paths, expected_paths)

    def test_expand_path2(self):
        """Expand path"""
        paths = (
            "segments[:@IDX_SEG].layers[:@IDX_LAY].test",
            "segments[:].layers[:].test",
        )
        path_types = (
            "model",
            "query",
        )

        # path = "segments.:@IDX_SEG.layers.:@IDX_LAY.test"
        seg_node = shared.LengthNode(2)
        lay_nodes = shared.LengthNode(2), shared.LengthNode(2)
        seg_node.set_children(lay_nodes)

        nodes = [seg_node]
        nodes.extend(lay_nodes)
        level_names = "IDX_SEG", "IDX_LAY"
        tree = shared.LengthTree(nodes, level_names)
        # 2  values for segment 0 and 2 values for segment 1
        expected_paths = [
            ["segments[0].layers[0].test", "segments[0].layers[1].test"],
            [
                "segments[1].layers[0].test",
                "segments[1].layers[1].test",
            ],
        ]

        for path, path_type in zip(paths, path_types):
            with self.subTest(path=path, path_type=path_type):
                expanded_paths = tree.expand_path(path, path_type=path_type)
                self.assertSequenceEqual(expanded_paths, expected_paths)

    def test_expand_mpath3(self):
        """Prune tree before expanding. Two indices vary so
        expanded paths is 2D
        """
        path = "segments[0].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        template_path = (
            "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        )
        self.tree.prune_from_path(
            shared.convert_to_internal_path(path),
            shared.convert_to_internal_path(template_path),
        )
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
        paths = self.tree.expand_path(path)
        self.assertSequenceEqual(paths, expected_paths)

    def test_expand_mpath4(self):
        """Prune tree before expanding. Ine index varies so
        expanded paths is 1D
        """
        path = "segments[0].layers[:@IDX_LAY].test.positions[1]"
        template_path = (
            "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        )
        self.tree.prune_from_path(
            shared.convert_to_internal_path(path),
            shared.convert_to_internal_path(template_path),
        )
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
            "attrs": "items[:@IDX1].attr.items[:@IDX2].path",
            "number": "some_number",
        }
        expected_result = {
            "attrs": [
                ["items[0].attr.items[0].path", "items[0].attr.items[1].path"],
                ["items[1].attr.items[0].path", "items[1].attr.items[1].path"],
            ],
            "number": ["some_number"],
        }
        tree_for_name = {
            name: shared.LengthTree.from_data(path, input_data)
            for name, path in path_consumed_for_name.items()
        }

        result = {
            name: tree.expand_path(path_consumed_for_name[name], as_internal_path=False)
            for name, tree in tree_for_name.items()
        }

        self.assertDictEqual(expected_result, result)

    def test_expand_mpath6(self):
        """As test 8 but the consumed path only subscribes to element 0
        of the (leftmost) items. Thus, the expasion leads to a flat list
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
            "attrs": "items_a[1@IDX1].attr.items[:@IDX2].path",
            "number": "some_number",
        }

        expected_result = {
            "attrs": ["items_a[1].attr.items[0].path", "items_a[1].attr.items[1].path"],
            "number": ["some_number"],
        }

        tree_for_name = {
            name: shared.LengthTree.from_data(path, input_data)
            for name, path in path_consumed_for_name.items()
        }

        result = {
            name: tree.expand_path(path_consumed_for_name[name], path_type="model")
            for name, tree in tree_for_name.items()
        }

        self.assertDictEqual(expected_result, result)


if __name__ == "__main__":
    unittest.main()
