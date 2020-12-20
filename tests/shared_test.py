import unittest
import yaml

from hubit import shared


def get_data():
    cfg = {'provides': 
                        [{'name': 'attrs1',
                          'path': 'items.:.attr.items.:.path1'},
                         {'name': 'attr2',
                          'path': 'attr2.path'},
                        ]
                        ,
            'consumes': {
                        'input' : [{'name': 'attr', 'path': 'items.:.attr.path'}], 
                        'results' : {},
                        }
            }

    inputdata = {'items' : [
                            {"attr": {"items": [{"path": 2}, {"path": 1}]}},
                            {"attr": {"items": [{"path": 3}, {"path": 4}]}},
                            ] 
                }
    return cfg, inputdata



class TestShared(unittest.TestCase):

    def setUp(self):
        self.flat_input = {"segs.0.walls.0.kval": 1,
                           "segs.0.walls.1.kval": 2,
                           "segs.0.walls.2.kval": None,
                           "segs.1.walls.0.kval": 3,
                           "segs.1.walls.1.kval": 7,
                           "segs.1.walls.2.kval" : 5,
                           "segs.0.length" : 13,
                           "segs.1.length" : 14,
                           "weight":567}

        self.ilocstr = "_ILOC"
        self.providerstring = "segs._ILOC.walls._ILOC.temps"
        self.querystring = "segs.42.walls.3.temps"


    def test_get_indices(self):
        """Test that indices from query string are extracted correctly
        """
        idxs = shared.get_iloc_indices(self.querystring,
                                       self.providerstring,
                                       self.ilocstr)
        idxs_expected = ('42', '3')
        self.assertSequenceEqual(idxs, idxs_expected)


    def test_get_matches(self):
        """Test that we can find the provider strings 
        that match the query
        """
        providerstrings = ('price',
                           self.providerstring,
                           "segs._ILOC.walls.thicknesses",
                           self.querystring,
                           "segs._ILOC.walls._ILOC.thicknesses",
                           "segs._ILOC.walls._ILOC", 
                           )

        idxs_match_expected = (1, 3)
        idxs_match = shared.idxs_for_matches(self.querystring,
                                             providerstrings,
                                             self.ilocstr)

        self.assertSequenceEqual(idxs_match, idxs_match_expected)


    def test_set_ilocs(self):
        """Insert real numbers where the ILOC placeholder is found
        """
        expected_pathstr = "segs.34.walls.3.temps" 
        path = shared.set_ilocs_on_path("segs._ILOC.walls._ILOC.temps",
                                        ("34", "3"),
                                        self.ilocstr)
        self.assertEqual(path, expected_pathstr)


    def test_expand_query(self):
        """Expand a query that uses : to its constituents
        """
        # querystring = "segs[:].walls[:].temps"
        querystring = "segs.:.walls.:.temps"
        queries, maxilocs = shared.expand_query(querystring,
                                                self.flat_input)

        expected_maxilocs = [1, 2]
        expected_length = 6 # math.prod(expected_maxilocs) # TODO: py3.8
        length = len(queries)
        self.assertTrue( maxilocs == expected_maxilocs and
                         length == expected_length)


    def test_expand_query2(self):
        """Expand a query that does not use : to its constituents
        i.e. itself
        """
        # querystring = "segs[0].walls[0].kval"
        querystring = "segs.0.walls.0.kval"
        queries, maxilocs = shared.expand_query(querystring,
                                                self.flat_input)
        expected_maxilocs = []
        expected_length = 1 
        length = len(queries)
        self.assertTrue( maxilocs == expected_maxilocs and
                         length == expected_length)


    def test_query_all(self):
        """
        """
        self.skipTest('Feature not used yet')
        providerstrings = (
                          "price",
                          "segs._ILOC.walls.values",
                          "segs._ILOC.walls._ILOC.heat_flow",
                          "segs._ILOC.walls._ILOC.temp_in",
                          )

        qall = shared.query_all(providerstrings,
                                self.flat_input,
                                self.ilocstr)
        # Make general query
        print(qall)


    def test_get_from_datadict(self):
        """Extract value from nested dict using a list of keys.
        """
        datadict = {'a' : {'b' : [4, 5]}}
        # Should all be of type string
        keys = ['a', 'b', '0']
        value = shared.get_from_datadict(datadict, keys)
        self.assertTrue(value == 4)


    def test_traverse(self):
        """ Thest iterator that traverses nested list """
        l0 = 'as', 'fv', 'dsd', ['fr', 'hj', ['gb', 0]]
        self.assertTrue( len( list( shared.traverse(l0) ) ) == 7 )


    def test_shape(self):
        # Infer the shape of the provision
        cfg, inputdata = get_data()
        path = cfg["provides"][0]["path"]
        shape = shared.path_shape(path, inputdata, ".", ":")
        self.assertSequenceEqual( shape, [2, 2] )


    def test_expand(self):
        # Expand provision into its constituents
        cfg, inputdata = get_data()
        path = cfg["provides"][0]["path"]
        shape = shared.path_shape(path, inputdata, ".", ":")
        paths = shared.path_expand(path, shape, ":")      
        self.assertTrue( len( list(shared.traverse(paths)) ) == shape[0]*shape[1] )


    def test_x(self):
        self.skipTest('Feature not used yet... and not sure what it is')
        cfg, inputdata = get_data()
        path = cfg["provides"]["attrs1"]

        # iterate over all indices
        import itertools
        shape = (2, 3)
        for ilocs in itertools.product(*[range(s) for s in shape]):
            print(ilocs)

        paths = [['attr1', "attr2"], ["attr3", "attr4"]]
        valuemap = {'attr1':1, "attr2":2, "attr3":3, "attr4":4}

        print('XXX', shared.setelemtents(paths, valuemap))


class Test(unittest.TestCase):

    def test_1(self):
        """Extract idxids from path
        """
        path = "segs[IDX_SEG].walls[IDX_WALL].heat_flow"
        expected_idxids = ['IDX_SEG', 'IDX_WALL']
        idxids = shared.idxids_from_path(path)
        self.assertSequenceEqual( expected_idxids, idxids )


    def test_2(self):
        """Convert from Hubit user path to internal Hubit path 
        """
        path = "segs[IDX_SEG].walls[IDX_WALL].heat_flow"
        expected_internal_path = "segs.IDX_SEG.walls.IDX_WALL.heat_flow"
        internal_path = shared.convert_to_internal_path(path)
        self.assertSequenceEqual( expected_internal_path, internal_path )


    def test_2a(self):
        """Convert from Hubit user path to internal Hubit path 
        """
        path = "segs[:@IDX_SEG].walls[:@IDX_WALL].heat_flow"
        expected_internal_path = "segs.:@IDX_SEG.walls.:@IDX_WALL.heat_flow"
        internal_path = shared.convert_to_internal_path(path)
        self.assertSequenceEqual( expected_internal_path, internal_path )


    def test_3(self):
        path = "segments[IDX_SEG].layers[IDX_LAY].test.positions[IDX_POS]"
        idxids = shared.idxids_from_path(path)
        internal_paths =shared._paths_between_idxids(path, idxids)
        # Last element is empty since there are no attribute after IDX_POS
        expected_internal_paths = ['segments', 'layers', 'test.positions', '']
        self.assertSequenceEqual( expected_internal_paths, internal_paths )


    def test_4(self):
        """Extract lengths from input for path
        """
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
                                  material: styrofoam
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
        path = "segments[:@IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        path = "segments[IDX_SEG].layers[:@IDX_LAY].test.positions[:@IDX_POS]"
        # TODO test paths in this case
        # path = "segments[:@IDX_SEG].layers[:@IDX_LAY].test"
        # TODO: nest last list
        # expected_lengths = [[2], [3, 4], [[1, 3, 2], [5, 1, 2, 4]] ]
        expected_lengths = (('IDX_SEG', [2]),
                            ('IDX_LAY', [3, 4]), 
                            ('IDX_POS', [1, 3, 2, 5, 1, 2, 4])) 
        calculated_lengths, paths = shared.lengths_for_path(path, input_data)
        self.assertSequenceEqual( expected_lengths, calculated_lengths )


    def test_5(self):
        """No lengths since there are no index IDs in path 
        """
        path = "segments.layers.positions"
        expected_lengths = None
        calculated_lengths, _ = shared.lengths_for_path(path, {})
        self.assertEqual( expected_lengths, calculated_lengths )


    def test_expand_new(self):
        path = "segments.:@IDX_SEG.layers.:@IDX_LAY.test.positions.:@IDX_POS"
        template_path = path
        lengths = (('IDX_SEG', 2),
                   ('IDX_LAY', [3, 4]), 
                   ('IDX_POS', [[1, 3, 2], [5, 1, 2, 4]])) 

        # 1 + 3 + 2 values for segment 0 and 5 + 1 + 2 + 4 values for segment 1
        # All all 18 elements
        expected_paths = [
                          [ # IDX_SEG element 0 has 3 IDX_LAY elements
                           [ # IDX_LAY element 0 has 1 IDX_POS elements
                               'segments.0.layers.0.test.positions.0'
                           ],
                           [ # IDX_LAY element 1 has 3 IDX_POS elements
                               'segments.0.layers.1.test.positions.0',
                               'segments.0.layers.1.test.positions.1' ,
                               'segments.0.layers.1.test.positions.2'
                           ],
                           [ # IDX_LAY element 2 has 2 IDX_POS elements
                               'segments.0.layers.2.test.positions.0',
                               'segments.0.layers.2.test.positions.1',
                           ]
                          ],
                          [ # IDX_SEG element 1 has 4 IDX_LAY elements
                            [ # IDX_LAY element 0 has 5 IDX_POS elements
                               'segments.1.layers.0.test.positions.0',
                               'segments.1.layers.0.test.positions.1',
                               'segments.1.layers.0.test.positions.2',
                               'segments.1.layers.0.test.positions.3',
                               'segments.1.layers.0.test.positions.4',
                            ],
                            [ # IDX_LAY element 0 has 1 IDX_POS elements
                               'segments.1.layers.1.test.positions.0',
                            ],
                            [ # IDX_LAY element 0 has 2 IDX_POS elements
                               'segments.1.layers.2.test.positions.0',
                               'segments.1.layers.2.test.positions.1',
                            ],
                            [ # IDX_LAY element 0 has 4 IDX_POS elements
                               'segments.1.layers.3.test.positions.0',
                               'segments.1.layers.3.test.positions.1',
                               'segments.1.layers.3.test.positions.2',
                               'segments.1.layers.3.test.positions.3'
                            ]
                           ]
                         ]
        paths = shared.expand_new(path, template_path, lengths)
        self.assertSequenceEqual( paths, expected_paths )



    def test_expand_new1(self):
        path = "segments.:@IDX_SEG.layers.:@IDX_LAY.test"
        template_path = path
        lengths = (('IDX_SEG', 2),
                   ('IDX_LAY', [2, 2]), ) 

        # 2  values for segment 0 and 2 values for segment 1
        expected_paths = [['segments.0.layers.0.test',
                          'segments.0.layers.1.test'],
                          ['segments.1.layers.0.test',
                          'segments.1.layers.1.test',]]
        paths = shared.expand_new(path, template_path, lengths)
        self.assertSequenceEqual( paths, expected_paths )


    def test_expand_new2(self):
        path = "segments.0.layers.:@IDX_LAY.test.positions.:@IDX_POS"
        template_path = "segments.:@IDX_SEG.layers.:@IDX_LAY.test.positions.:@IDX_POS"
        lengths = [['IDX_SEG', 2],
                   ['IDX_LAY', [3, 4]],
                   ['IDX_POS', [[1, 3, 2], [5, 1, 2, 4]]]] 

        # 1 + 3 + 2 values for segment 0
        expected_paths = [
                           [
                              'segments.0.layers.0.test.positions.0',
                           ],
                           [
                             'segments.0.layers.1.test.positions.0',
                             'segments.0.layers.1.test.positions.1',
                             'segments.0.layers.1.test.positions.2',
                           ],
                           [
                             'segments.0.layers.2.test.positions.0',
                             'segments.0.layers.2.test.positions.1',
                           ]
                        ]
        paths = shared.expand_new(path, template_path, lengths,)
        # TODO: reduce size of _all_lengths['IDX_SEG'] to 1
        print(paths)
        self.assertSequenceEqual( paths, expected_paths )


    def test_expand_new3(self):
        path = "segments.0.layers.:@IDX_LAY.test.positions.1"
        template_path = "segments.:@IDX_SEG.layers.:@IDX_LAY.test.positions.:@IDX_POS"
        lengths = [['IDX_SEG', 2],
                   ['IDX_LAY', [3, 4]], 
                   ['IDX_POS', [[1, 3, 2], [5, 1, 2, 4]]]] 

        # 1 + 3 + 2 values for segment 0
        expected_paths = [
                           'segments.0.layers.1.test.positions.1',
                           'segments.0.layers.2.test.positions.1',
                         ]
        paths = shared.expand_new(path, template_path, lengths,)
        print('RESULT', paths)
        self.assertSequenceEqual( paths, expected_paths )


class TestTree(unittest.TestCase):

    def test_1(self):
        lengths = [['IDX_SEG', 2],
                   ['IDX_LAY', [3, 4]],
                   ['IDX_POS', [[1, 3, 2], [5, 1, 2, 4]]]] 

        lev0_nodes = shared.LenghtNode(2)
        lev1_nodes = shared.LenghtNode(3), shared.LenghtNode(4)
        lev2a_nodes = shared.LenghtNode(1), shared.LenghtNode(3), shared.LenghtNode(2)
        lev2b_nodes = shared.LenghtNode(5), shared.LenghtNode(1), shared.LenghtNode(2), shared.LenghtNode(4)

        lev0_nodes.set_children(lev1_nodes)
        lev1_nodes[0].set_children(lev2a_nodes)
        lev1_nodes[1].set_children(lev2b_nodes)

        nodes = [lev0_nodes]
        nodes.extend(lev1_nodes) 
        nodes.extend(lev2a_nodes) 
        nodes.extend(lev2b_nodes)
        level_names = 'IDX_SEG', 'IDX_LAY', 'IDX_POS'
        tree = shared.LengthTree(nodes, level_names)
        print(tree)


if __name__ == '__main__':
    unittest.main()