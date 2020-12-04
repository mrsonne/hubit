from __future__ import print_function
# import math
import unittest

from hubit import shared

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
        querystring = "segs.:.walls.:.temps"
        queries, maxilocs = shared.expand_query(querystring, self.flat_input)
        # Expected result from highest index in self.flat_input
        expected_maxilocs = [1, 2]
        expected_length = 6 # math.prod(expected_maxilocs) # TODO: py3
        length = len(queries)
        self.assertTrue( maxilocs == expected_maxilocs and
                         length == expected_length)


    def test_query_wildcard_2(self):
        querystring = "segs.0.walls.temps.0"
        queries = shared.expand_query(querystring, self.flat_input)
        print('queries', queries)


    def test_query_all(self):
        """
        """
        providerstrings = (
                        'price',
                        "segs._ILOC.walls.values",
                        "segs._ILOC.walls._ILOC.heat_flow",
                        "segs._ILOC.walls._ILOC.temp_in",
                        )

        qall = shared.query_all(providerstrings, self.flat_input, self.ilocstr)
        # Make general query
        print(qall)


    def test_get_from_datadict(self):
        datadict = {'a' : {'b' : [4, 5]}}
        keys = ['a', 'b', 0]
        value = shared.get_from_datadict(datadict, keys)
        self.assertTrue(value == 4)


    def test_wildcard(self):
        cfg = {'provides': {
                            'attrs1': 'items.:.attr.items.:.path1',
                            'attr2': 'attr2.path',
                           },
               'consumes': {
                            'input' : {'attr' : 'items.:.attr.path'}, 
                            'results' : {},
                           }
              }

        inputdata = {'items' : [
                                # {"attr": {"items": [{"path": 2}]}},
                                # {"attr": {"items": [{"path": 2}]}},
                                {"attr": {"items": [{"path": 2}, {"path": 1}]}},
                                {"attr": {"items": [{"path": 3}, {"path": 4}]}},
                               ] 
                    }
        pstr = cfg["provides"]["attrs1"]
        shape = shared.pstr_shape(pstr, inputdata, ".", ":")
        pstrs = shared.pstr_expand(pstr, shape, ":")

        l0 = 'as', 'fv', 'dsd'
        for val in shared.traverse(l0):
            print('l0', val)

        # iterate over all indices
        import itertools
        shape = (2, 3)
        for ilocs in itertools.product(*[xrange(s) for s in shape]):
            print(ilocs)

        # Wrap values as mutable
        # https://stackoverflow.com/questions/37501632/is-it-possible-to-make-wrapper-object-for-numbers-e-g-float-to-make-it-mutabl
        # l1 = [shared.Container(1), 
        #        [shared.Container(2) , shared.Container(3) , 
        #          [shared.Container(4), shared.Container(5)]
        #        ]
        #      ]

        # l1 = [1, [2 , 3 , [4, 5]]]
        # l2 = [11, [12,13,[14, 15]]]
        # pstrs = ['attr1', "attr2", "attr3", "attr4"]
        # pstrs = ['attr1', ["attr2", "attr3", "attr4"]]
        # pstrs = ['attr1', ["attr2", "attr3"], "attr4"]
        # pstrs = ['attr1', ["attr2"], "attr3", "attr4"]
        pstrs = [['attr1', "attr2"], ["attr3", "attr4"]]
        # pstrs = [['attr1', "attr2", "attr3", "attr4"]]
        # pstrs = 'attr1'
        valuemap = {'attr1':1, "attr2":2, "attr3":3, "attr4":4}
        # print l1
        # print l2

        print('XXX', shared.setelemtents(pstrs, valuemap))


        # for i, (val1, val2) in enumerate(zip(shared.traverse(l1), shared.traverse(l2))):
        #     print val1, val2
        #     val1.val = 56 + i
        #     # val1 = 56 + i
        # print 'L1', l1
        # for val1 in shared.traverse(l1):
        #     val1 = val1.val
        # print 'L1', l1

        print('')
        print(shape)
        print(pstrs)
        print(pstrs[0][1])
        print('')



if __name__ == '__main__':
    unittest.main()