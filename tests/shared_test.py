from __future__ import print_function
# import math
import unittest

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
        self.flat_input = {"segs.0.walls.0.kval" : 1, "segs.0.walls.1.kval" : 2, "segs.0.walls.2.kval" : None,
                           "segs.1.walls.0.kval" : 3, "segs.1.walls.1.kval" : 7, "segs.1.walls.2.kval" : 5,
                           "segs.0.length" : 13, "segs.1.length" : 14,
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
        pathstr = shared.set_ilocs_on_pathstr("segs._ILOC.walls._ILOC.temps",
                                             ("34", "3"),
                                             self.ilocstr)
        self.assertEqual(pathstr, expected_pathstr)


    def test_expand_query(self):
        """Expand a query that uses : to its constituents
        """
        querystring = "segs.:.walls.:.temps"
        queries, maxilocs = shared.expand_query(querystring,
                                                self.flat_input)
        # Expected result from highest index in self.flat_input
        expected_maxilocs = [1, 2]
        expected_length = 6 # math.prod(expected_maxilocs) # TODO: py3
        length = len(queries)
        self.assertTrue( maxilocs == expected_maxilocs and
                         length == expected_length)


    def test_expand_query2(self):
        """Expand a query that does not use : to its constituents
        i.e. itself
        """
        querystring = "segs.0.walls.temps.0"
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
        pstr = cfg["provides"][0]["path"]
        shape = shared.pstr_shape(pstr, inputdata, ".", ":")
        self.assertSequenceEqual( shape, [2, 2] )


    def test_expand(self):
        # Expand provision into its constituents
        cfg, inputdata = get_data()
        pstr = cfg["provides"][0]["path"]
        shape = shared.pstr_shape(pstr, inputdata, ".", ":")
        pstrs = shared.pstr_expand(pstr, shape, ":")      
        self.assertTrue( len( list(shared.traverse(pstrs)) ) == shape[0]*shape[1] )


    def test_x(self):
        self.skipTest('Feature not used yet... and not sure what it is')
        cfg, inputdata = get_data()
        pstr = cfg["provides"]["attrs1"]

        # iterate over all indices
        import itertools
        shape = (2, 3)
        for ilocs in itertools.product(*[range(s) for s in shape]):
            print(ilocs)

        pstrs = [['attr1', "attr2"], ["attr3", "attr4"]]
        valuemap = {'attr1':1, "attr2":2, "attr3":3, "attr4":4}

        print('XXX', shared.setelemtents(pstrs, valuemap))


if __name__ == '__main__':
    unittest.main()