import unittest
import os
import pathlib
import yaml
import logging
# logging.basicConfig(level=logging.DEBUG)

from hubit.model import (HubitModel, 
                         HubitModelNoInputError,
                         HubitModelQueryError,
                         _QueryRunner)
from hubit.shared import convert_to_internal_path, inflate, flatten

yml_input = None
model = None

THIS_DIR = os.path.dirname(os.path.realpath(__file__))
REL_TMP_DIR = './tmp'
TMP_DIR = os.path.join(THIS_DIR, REL_TMP_DIR)
pathlib.Path(TMP_DIR).mkdir(parents=True, exist_ok=True)

def setUpModule():
        global yml_input
        global model

        # Paths are relative to the root directory where the tests are executed from
        # This model collects wall data in a list on the end node
        model = """
        -   
            # move a number
            func_name: move_number
            path: ./components/comp0.py 
            provides: 
                - name: number
                  path: first_coor[IDX1].second_coor[IDX2].value 
            consumes:
                input: 
                    - name: number
                      path: list[IDX1].some_attr.inner_list[IDX2].xval

        -
            func_name: multiply_by_2
            # Path relative to base_path
            path: ./components/comp1.py 
            provides: 
                - name: comp1_results
                  path: list[IDX1].some_attr.two_x_numbers
            consumes:
                input: 
                    - name: numbers_consumed_by_comp1
                      path: list[IDX1].some_attr.numbers
        -
            func_name: multiply_by_factors
            path: ./components/comp2.py
            provides:
                - name: temperatures
                  path: list[IDX1].some_attr.two_x_numbers_x_factor
            consumes:
                input: 
                    - name: factors
                      path: list[IDX1].some_attr.factors
                results: 
                    - name: numbers_provided_by_comp1
                      path: list[IDX1].some_attr.two_x_numbers
        -
            func_name: slicing
            path: ./components/comp3.py # consumes factors for all list items and stores them in nested list
            provides:
              - name: mylist
                path: factors
            consumes:
                input: 
                    - name: factors
                      path: list[:@IDX1].some_attr.factors
        -
            func_name: fun4
            path: ./components/comp4.py
            provides:
                - name: yvals
                  path: list[IDX1].some_attr.inner_list[:@IDX2].yval
            consumes:
                input:
                    - name: fact
                      path: list[IDX1].some_attr.x_to_y_fact
                    - name: xvals
                      path: list[IDX1].some_attr.inner_list[:@IDX2].xval
        """

        yml_input = """
        list:
            - some_attr:
                numbers: [0.2, 0.3]
                factors: [2., 3.]
                x_to_y_fact: 2.
                inner_list:
                    - 
                        xval: 1.
                    - 
                        xval: 2.
            - some_attr:
                numbers: [0.4, 0.5]
                factors: [4., 5.]
                x_to_y_fact: 3.
                inner_list:
                    - 
                        xval: 3.
                    - 
                        xval: 4.
        """

def level0_results_at_idx(input, idx):
    fact = 2.
    return [fact*x for x in input["list"][idx]["some_attr"]["numbers"]]


def level1_results_at_idx(input, idx):
    level0_fact = 2.
    return [level0_fact*level1_fact*number
            for number, level1_fact 
            in zip(input["list"][idx]["some_attr"]["numbers"],
                   input["list"][idx]["some_attr"]["factors"])]

class TestModel(unittest.TestCase):

    def setUp(self):
        modelname = 'Test model'
        model_data = yaml.load(model, Loader=yaml.FullLoader)
        self.hmodel = HubitModel(model_data,
                                 name=modelname,
                                 base_path=THIS_DIR,
                                 output_path=REL_TMP_DIR)
        self.input = yaml.load(yml_input, Loader=yaml.FullLoader)
        self.mpworkers_values = False, True

        # Query which does not consume results
        self.idx = 1
        self.querystr_level0 = "list[{}].some_attr.two_x_numbers".format(self.idx)
        self.expected_result_level0 = level0_results_at_idx(self.input, self.idx)

        self.querystr_level1 = "list[{}].some_attr.two_x_numbers_x_factor".format(self.idx)

        self.querystr_level0_slice = "list[:].some_attr.two_x_numbers"
        self.expected_result_level0_slice = [level0_results_at_idx(self.input, 0),
                                             level0_results_at_idx(self.input, 1)]

        self.querystr_level0_last = "list[-1].some_attr.two_x_numbers"


    def test_from_file(self):
        """
        Test if model can successfully be loaded from a file
        """
        fpath = os.path.join(TMP_DIR, 'model.yml')
        with open(fpath, 'w') as handle:
            yaml.dump(yaml.load(model, Loader=yaml.FullLoader), handle,
                      default_flow_style=False)
        _ = HubitModel.from_file(fpath)
        self.assertTrue(True)


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
        queries = [self.querystr_level0]
        is_ok = self.hmodel.validate(queries)
        self.assertTrue( is_ok )


    def test_validate_query_all_elements(self):
        """
        Validate query for all list element
        """
        self.hmodel.set_input(self.input)
        queries = [self.querystr_level0_slice]
        is_ok = self.hmodel.validate(queries)
        self.assertTrue( is_ok )


    def test_validate_query_last_element(self):
        """
        Validate query for last list element.
        """
        self.skipTest('Broken')
        self.hmodel.set_input(self.input)
        queries = [self.querystr_level0_last]
        is_ok = self.hmodel.validate(queries)


    def test_render_model(self):
        """
        Test that rendering the model does not raise an exception
        TODO: could test the dot object instead
        """
        self.hmodel.render()


    def test_render_query_fail(self):
        """
        Render the query, but not input.
        """
        queries = ["list.1.some_attr.two_x_numbers"]

        # ModuleNotFoundError raised if graphviz is not installed
        with self.assertRaises(HubitModelNoInputError) as context:
            self.hmodel.render(queries)


    def test_render_query(self):
        """
        Render the query
        TODO: could test the dot object instead
        Sometimes (?!?!) gives this warning:
        Warning: _Query -> cluster_resultslist: head not inside head cluster cluster_results
        Warning: cluster_resultslist -> _Response: tail not inside tail cluster cluster_results
        """
        self.hmodel.set_input( self.input )
        queries = [self.querystr_level0]
        self.hmodel.render( queries )


    def test_get_fail_no_input(self):
        """
        Simple request with no input. Fails
        """
        queries = [self.querystr_level0]

        def test():
            with self.assertRaises(HubitModelNoInputError) as context:
                self.hmodel.get(queries, mpworkers=mpworkers)

        for mpworkers in self.mpworkers_values:
            with self.subTest(mpworkers=mpworkers):
                test()


    def test_get_fail_query_error(self):
        """
        Simple request with no input. Fails
        """
        self.hmodel.set_input(self.input)
        queries = ["list.1.some_attr.i_dont_exist"]

        def test():
            with self.assertRaises(HubitModelQueryError) as context:
                self.hmodel.get(queries, mpworkers=mpworkers)

        for mpworkers in self.mpworkers_values:
            with self.subTest(mpworkers=mpworkers):
                test()


    def test_get_level0(self):
        """
        Level 0 query (no dependencies)
        """
        self.hmodel.set_input(self.input)

        queries = [self.querystr_level0]

        def test():
            response = self.hmodel.get(queries,
                                       mpworkers=mpworkers,
                                       validate=False)
    
            self.assertSequenceEqual(response[self.querystr_level0], 
                                     self.expected_result_level0)

        for mpworkers in self.mpworkers_values:
            with self.subTest(mpworkers=mpworkers):
                test()


    def test_get_level1(self):
        """
        Level 1 query (one dependency)
        """
        self.hmodel.set_input(self.input)
        queries = [self.querystr_level1]

        def test():
            response = self.hmodel.get(queries,
                            mpworkers=mpworkers,
                            validate=True)
            self.assertSequenceEqual(response[self.querystr_level1],
                                    level1_results_at_idx(self.input, 1))

        for mpworkers in self.mpworkers_values:
            with self.subTest(mpworkers=mpworkers):
                test()

    def test_comsume_2_idxids(self):
        """Level 1 fixed, level 2 fixed"""
        mpworkers = False
        self.hmodel.set_input(self.input)
        response = self.hmodel.get(['first_coor[0].second_coor[0].value'],
                                    mpworkers=mpworkers,
                                    validate=False)
        expected_response = {'first_coor[0].second_coor[0].value': 1.0}
        self.assertDictEqual(response, expected_response)


    def test_comsume_2_idxids_idxwc(self):
        """Level 1 fixed, index wildcard on level 2"""
        mpworkers = False
        self.hmodel.set_input(self.input)
        response = self.hmodel.get(['first_coor[0].second_coor[:].value'],
                                    mpworkers=mpworkers,
                                    validate=False)
        expected_response = {'first_coor[0].second_coor[:].value': [1.0, 2.0]}
        self.assertDictEqual(response, expected_response)


    def test_comsume_2_idxids_idxwc_a(self):
        """Index wildcard on level 1. Level 2 fixed"""
        mpworkers = False
        self.hmodel.set_input(self.input)
        response = self.hmodel.get(['first_coor[:].second_coor[0].value'],
                                    mpworkers=mpworkers,
                                    validate=False)
        expected_response = {'first_coor[:].second_coor[0].value': [1.0, 3.0]}
        self.assertDictEqual(response, expected_response)


    def test_comsume_2_idxids_2_idxwc(self):
        """Level 1 fixed, index wildcard on level 2"""
        mpworkers = False
        self.hmodel.set_input(self.input)
        response = self.hmodel.get(['first_coor[:].second_coor[:].value'],
                                    mpworkers=mpworkers,
                                    validate=False)
        print(response)
        expected_response = {'first_coor[:].second_coor[:].value': [[1., 2.], [3., 4.]]}
        self.assertDictEqual(response, expected_response)


    def test_get_slice(self):
        """
        Query all list element
        """
        self.hmodel.set_input(self.input)
        queries = [self.querystr_level0_slice]
        def test():
            response = self.hmodel.get(queries,
                                       mpworkers=mpworkers,
                                       validate=True)
            self.assertSequenceEqual(response[self.querystr_level0_slice], 
                                     self.expected_result_level0_slice)

        for mpworkers in self.mpworkers_values:
            with self.subTest(mpworkers=mpworkers):
                test()


    def test_get_last(self):
        """
        Query last list element
        """
        self.skipTest('Broken')
        self.hmodel.set_input(self.input)
        queries = [self.querystr_level0_last]
        for mpworkers in self.mpworkers_values:
            with self.subTest(mpworkers=mpworkers):
                response = self.hmodel.get(queries,
                                           mpworkers=mpworkers)
                self.assertSequenceEqual(response[self.querystr_level0], 
                                         self.expected_result_level0)



    def test_get_all(self):
        """
        No query yields all results
        """
        self.skipTest('Not implemented')
        self.hmodel.set_input(self.input)
        for mpworkers in self.mpworkers_values:
            with self.subTest(mpworkers=mpworkers):
                response = self.hmodel.get(mpworkers=mpworkers)
                print(response)


    def test_sweep(self):
        """
        Sweep input parameters
        """
        self.skipTest('TODO. Works but not with other test?!?!?')
        idx = 1
        # TODO change this
        path = "list[{}].some_attr.numbers".format(idx)
        # path = "list.{}.some_attr.numbers".format(idx)
        input_values_for_path = {path: ([1., 2., 3.],
                                        [4., 5., 6.]),
                                }
        self.hmodel.set_input( self.input )
        queries = [self.querystr_level0]
        responses, inps, _ = self.hmodel.get_many(queries,
                                                  input_values_for_path)

        print('responses', responses)
        expected_results = []
        calc_responses = []
        # TODO unsafe test since it it depends on logic that creates inps
        for flat_inp, response in zip(inps, responses):
            inp = inflate(flat_inp)
            expected_results.append( level0_results_at_idx( inp, idx ) )
            calc_responses.append( response[self.querystr_level0] )
        
        print('calc_responses', calc_responses)
        print( 'expected_results', expected_results)
        self.assertSequenceEqual(calc_responses,
                                 expected_results)



def subscriptions_for_query(query, query_runner):
    """Get subscriptions from worker
    """
    w = query_runner._worker_for_query(query)
    consumes = list( w.ipath_consumed_for_name.values() )
    consumes += list( w.rpath_consumed_for_name.values() )
    provides = list( w.rpath_provided_for_name.values() )
    return consumes, provides


def subscriptions_for_component_idx(model_data, comp_idx, iloc, idxid):
    """Get subscriptions from model
    """
    ilocstr = str(iloc)

    consumes = []
    try:
        consumes.extend( [ binding['path'] 
                         for binding in model_data[comp_idx]["consumes"]["input"] ] )
    except KeyError:
        pass

    try:
        consumes.extend( [ binding['path'] 
                          for binding in model_data[comp_idx]["consumes"]["results"] ] )
    except KeyError:
        pass
    
    # Replace ilocstr with actual iloc 
    consumes = [path.replace(idxid, ilocstr) for path in consumes]

    provides = [ binding['path'] for binding in model_data[comp_idx]["provides"] ]
    provides = [ path.replace(idxid, ilocstr) for path in provides ]

    return consumes, provides


class TestRunner(unittest.TestCase):

    def setUp(self):
        self.model_data = yaml.load(model, Loader=yaml.FullLoader)
        self.hmodel = HubitModel(self.model_data,
                                 name='My model',
                                 base_path=THIS_DIR,
                                 output_path=REL_TMP_DIR)
        mpworkers = False
        self.qr = _QueryRunner(self.hmodel, mpworkers)
        self.input = yaml.load(yml_input, Loader=yaml.FullLoader)
        self.hmodel.set_input(self.input)

        # Query which does not consume results
        self.idx = 1
        self.querystr_level0 = "list[{}].some_attr.two_x_numbers".format(self.idx)
        self.querystr_level1 = "list[{}].some_attr.two_x_numbers_x_factor".format(self.idx)


    def test_worker_comp1(self):
        """
        """
        # Component index in model (TODO: brittle)
        comp_idx = 1
        qstr = self.querystr_level0

        (worker_consumes,
        worker_provides) = subscriptions_for_query(qstr, self.qr)
        (worker_consumes_expected,
        worker_provides_expected) = subscriptions_for_component_idx(self.model_data,
                                                                    comp_idx,
                                                                    self.idx,
                                                                    idxid='IDX1')

        test_consumes = set(worker_consumes) == set(worker_consumes_expected)
        test_provides = set(worker_provides) == set(worker_provides_expected)

        with self.subTest(test_consumes):
            self.assertTrue(test_consumes)
            
        with self.subTest(test_provides):
             self.assertTrue(test_provides)


    def test_worker_comp2(self):
        """
        """
        # Component index in model
        comp_idx = 2
        qstr = self.querystr_level1

        (worker_consumes,
        worker_provides) = subscriptions_for_query(qstr,
                                                   self.qr)

        (worker_consumes_expected,
        worker_provides_expected) = subscriptions_for_component_idx(self.model_data,
                                                                    comp_idx,
                                                                    self.idx,
                                                                    idxid='IDX1')

        test_consumes = set(worker_consumes) == set(worker_consumes_expected)
        test_provides = set(worker_provides) == set(worker_provides_expected)

        with self.subTest(test_consumes):
            self.assertTrue(test_consumes)
            
        with self.subTest(test_provides):
             self.assertTrue(test_provides)


    def test_no_provider(self):
        """
        No provider for query since the query has not provider. 
        """
        with self.assertRaises(HubitModelQueryError) as context:
            self.qr._worker_for_query("i.dont.exist")


    def get_worker_counts(self, queries):
        # queries = dot-queries
        all_results = {}
        flat_input = flatten(self.input)
        worker_counts = []
        for q in queries:
            self.qr._deploy(q, flat_input, 
                            all_results, flat_input, dryrun=True)
            worker_counts.append( len(self.qr.workers) )

        return worker_counts


    def test_number_of_workers_level0(self):
        """Test number of workers on level 0 quries ie queries 
        that have no dependencies
        """
        queries = [(self.querystr_level0,),]
        
        expected_worker_counts = [1, # Level 0 worker on specific index yields 1 worker
                                 ]
        worker_counts = self.get_worker_counts(queries)
        self.assertListEqual(worker_counts, expected_worker_counts)


    def test_number_of_workers_level1(self):
        """Test number of workers on level 1 quries ie queries
        that have one dependency
        """
        queries = [(self.querystr_level1,),]
        expected_worker_counts = [2, # Level 1 worker on specific index yields 2 workers - one for level 0 and one for level 1
                                 ]
        worker_counts = self.get_worker_counts(queries)
        self.assertListEqual(worker_counts, expected_worker_counts)


    def test_number_of_workers_composite(self):
        """Test composite queries
        """
        queries = [(self.querystr_level0, self.querystr_level1,)
                  ]
        expected_worker_counts = [2, # Level 1 query requires the level 0 attr so self.querystr_level0 is superfluous
                                 ]
        worker_counts = self.get_worker_counts(queries)
        self.assertListEqual(worker_counts, expected_worker_counts)


    def test_number_of_workers_slicing(self):
        """[summary]
        """
        queries = [('factors',),]
        worker_counts = self.get_worker_counts(queries)
        expected_worker_counts = [1, 
                                 ]
        self.assertListEqual(worker_counts,
                             expected_worker_counts)


    def test_number_of_workers_multiple_levels(self):
        """Query level-1 attribute. Should deploy 2 level-0 workers
        and 2 level-1 workers.
        """
        queries = [('list.0.some_attr.two_x_numbers_x_factor',
                    'list.1.some_attr.two_x_numbers_x_factor')]
        worker_counts = self.get_worker_counts(queries)
        expected_worker_counts = [4,]
        self.assertListEqual(worker_counts, expected_worker_counts)


    def test_number_of_workers_case6(self):
        """Query multiple attributes that are actually supplied by the 
        same component. Therefore, only one worker should be deployed.
        """

        # _deploy take internal paths
        queries = [('list.0.some_attr.inner_list.0.yval',
                    'list.0.some_attr.inner_list.1.yval',)
                  ]

        worker_counts = self.get_worker_counts(queries)
        expected_worker_counts = [1,]
        self.assertListEqual(worker_counts, expected_worker_counts)


    if __name__ == '__main__':
        unittest.main()