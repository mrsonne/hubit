from __future__ import print_function
import unittest
import yaml

from hubit.model import (HubitModel, 
                         HubitModelNoInputError,
                         HubitModelQueryError)

yml_input = None
model = None

def setUpModule():
        global yml_input
        global model

        # Paths are relative to the root directory where the tests are executed from
        # This model collects wall data in a list on the end node
        model = """
        - 
            func_name: multiply_by_2
            # Path from project root. TODO: make relative to model file
            path: ./tests/components/comp1.py 
            provides: {"comp1_results": "list._IDX.some_attr.two_x_numbers"}
            consumes:
                input: 
                    numbers_consumed_by_comp1: list._IDX.some_attr.numbers
        -
            func_name: multiply_by_factors
            path: ./tests/components/comp2.py
            provides:
                temperatures: list._IDX.some_attr.two_x_numbers_x_factor
            consumes:
                input: 
                    factors: list._IDX.some_attr.factors
                results: 
                    numbers_provided_by_comp1: list._IDX.some_attr.two_x_numbers
        """

        yml_input = """
        list:
            - some_attr:
                numbers: [0.2, 0.3]
                factors: [2., 3.]
            - some_attr:
                numbers: [0.4, 0.5]
                factors: [4., 5.]
        """



class TestModel(unittest.TestCase):

    def setUp(self):
        modelname = 'Test model'
        model_data = yaml.load(model)
        self.hmodel = HubitModel(model_data,
                                 name=modelname,
                                 output_path='./tmp')
        self.input = yaml.load(yml_input)
        self.mpworkers = False

        # Query which does not consume results
        self.querystr_level0 = "list.1.some_attr.two_x_numbers"
        self.expected_result_level0 = [2*x for x in self.input["list"][1]["some_attr"]["numbers"]]


        self.querystr_level1 = "list.1.some_attr.two_x_numbers_x_factor"

        self.querystr_level0_slice = "list.:.some_attr.two_x_numbers"
        self.querystr_level0_last = "list.-1.some_attr.two_x_numbers"

    def test_validate(self):
        """
        Model validation
        """
        self.assertTrue(self.hmodel.validate())


    def test_validate_query_first_element(self):
        """
        Validate query for first list element
        """
        self.hmodel.set_input(self.input)
        querystrings = [self.querystr_level0]
        is_ok = self.hmodel.validate(querystrings)
        self.assertTrue( is_ok )


    def test_validate_query_all_elements(self):
        """
        Validate query for all list element
        """
        self.hmodel.set_input(self.input)
        querystrings = [self.querystr_level0_slice]
        is_ok = self.hmodel.validate(querystrings)
        self.assertTrue( is_ok )


    def test_validate_query_last_element(self):
        """
        Validate query for last list element.
        """
        self.skipTest('Broken')
        self.hmodel.set_input(self.input)
        querystrings = [self.querystr_level0_last]
        is_ok = self.hmodel.validate(querystrings)
        print(is_ok)


    def test_render_model(self):
        """
        Test that rendering the model does not raise an exception
        """
        self.hmodel.render()


    def test_render_query_fail(self):
        """
        Render the query, but not input.
        """
        querystrings = ["list.1.some_attr.two_x_numbers"]

        with self.assertRaises(HubitModelNoInputError) as context:
            self.hmodel.render(querystrings)


    def test_render_query(self):
        """
        Render the query
        """
        self.hmodel.set_input( self.input )
        querystrings = [self.querystr_level0]
        self.hmodel.render( querystrings )


    def test_get_fail_no_input(self):
        """
        Simple request with no input. Fails
        """
        querystrings = [self.querystr_level0]
        with self.assertRaises(HubitModelNoInputError) as context:
            response = self.hmodel.get(querystrings,
                                       mpworkers=self.mpworkers)


    def test_get_fail_query_error(self):
        """
        Simple request with no input. Fails
        """
        self.hmodel.set_input(self.input)
        querystrings = ["list.1.some_attr.i_dont_exist"]
        with self.assertRaises(HubitModelQueryError) as context:
            self.hmodel.get(querystrings, mpworkers=self.mpworkers)


    def test_get(self):
        """
        Simple request
        """
        self.hmodel.set_input(self.input)
        querystrings = [self.querystr_level0]
        response = self.hmodel.get(querystrings, mpworkers=self.mpworkers, validate=True)
        self.assertSequenceEqual(response[self.querystr_level0], 
                                 self.expected_result_level0)


    def test_get_slice(self):
        """
        Query all list element
        """
        self.hmodel.set_input(self.input)
        querystrings = [self.querystr_level0_slice]
        response = self.hmodel.get(querystrings,
                                   mpworkers=self.mpworkers,
                                   validate=True)
        print(response)


    def test_get_last(self):
        """
        Query last list element
        """
        self.skipTest('Broken')
        self.hmodel.set_input(self.input)
        querystrings = [self.querystr_level0_last]
        response = self.hmodel.get(querystrings,
                                   mpworkers=self.mpworkers)
        self.assertSequenceEqual(response[self.querystr_level0], 
                                 self.expected_result_level0)



    def test_get_all(self):
        """
        No query yields all results
        """
        self.skipTest('Not implemented')
        self.hmodel.set_input(self.input)
        response = self.hmodel.get(mpworkers=self.mpworkers)
        print(response)


#     def test_sweep(self):
#         """
#         TODO: change model and input IL variations only involve IL i.e. something like
#         segs.0.walls.0.material
#         """
#         paths = ('segs.0.walls.materials',
#                  "segs.0.walls.thicknesses")
#         values = ((('pvdf', 'pa11'), ('xlpe', 'pa11'), ('pvdf', 'hdpe'), ('pa11', 'hdpe')), 
#                   ([[0.008, 0.01], [0.01, 0.01], [0.012, 0.01]]))
#         input_perturbations = dict(zip(paths, values))
#         print('input_perturbations', input_perturbations)

#         querystrings = ["segs.0.walls.temps"]
#         res, inps = self.hmodel.get_many(querystrings,
#                                         #  self.input_data,
#                                          input_perturbations)


#         for i, r in zip(inps, res):
#             print(i)
#             print(r)
#             print('')


# class TestRunner(unittest.TestCase):

#     def setUp(self):
#         modelname = 'Pipe model'
#         cfg = yaml.load(model)
#         self.hmodel = HubitModel(cfg, modelname)
#         self.mpworkers = False
#         self.qr = QueryRunner(self.hmodel, self.mpworkers)
#         inputdata = {'segs': [{
#                                 'walls' : {'temperature': ['steel', 'polymer', 'steel']}, 
#                                 'bore' : {'temperature': None},
#                                 'outside' : {'temperature': None},
#                                 }, 
#                                 {},
#                                 ]
#                          }
#         self.hmodel.set_input(inputdata)



#     def test_worker1(self):
#         """
#         Query thermal conductivities.
#         Consumes: 'segs.0.walls.materials'
#         Provides: 'segs.0.walls.ks'
#         """
#         w = self.qr.worker_for_query("segs.0.walls.ks")
#         consumes = w.inputpath_consumed_for_attrname.values() + w.resultspath_consumed_for_attrname.values()
#         provides = w.resultspath_provided_for_attrname.values()
#         test_consumes = len(consumes) == 1 and consumes[0] == 'segs.0.walls.materials'
#         test_provides = len(provides) == 1 and provides[0] == 'segs.0.walls.ks'
#         self.assertTrue(test_consumes and test_provides)


#     def test_worker2(self):
#         """
#         Query temperatures. 
#         Consumes: 'segs.0.walls.ks', 'segs.0.bore.temperature', 'segs.0.outside.temperature'
#         Provides: 'segs.0.walls.heat_flows' and 'segs.0.walls.temps'
#         """
#         w = self.qr.worker_for_query("segs.0.walls.temps")
#         consumes = w.inputpath_consumed_for_attrname.values() + w.resultspath_consumed_for_attrname.values()
#         provides = w.resultspath_provided_for_attrname.values()
#         test_consumes = len(consumes) == 3 and 'segs.0.walls.ks' in consumes
#         test_consumes = test_consumes and 'segs.0.bore.temperature' in consumes  and 'segs.0.outside.temperature' in consumes
#         test_provides = len(provides) == 2 and 'segs.0.walls.heat_flows' in provides and 'segs.0.walls.temps' in provides
#         self.assertTrue(test_consumes and test_provides)


#     def test_no_provider(self):
#         """
#         No provider for query since the query has a typo. It's "segs.0.walls.kxs" 
#         instead of "segs.0.walls.ks" as correctly specified in test_worker1.
#         """
#         with self.assertRaises(KeyError) as context:
#             self.qr.worker_for_query("segs.0.walls.kxs")

#         self.assertTrue("No provider for query 'segs.0.walls.kxs'" in str(context.exception))

    if __name__ == '__main__':
        unittest.main()