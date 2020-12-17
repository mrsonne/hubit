import unittest
import yaml
from hubit.worker import _Worker, HubitWorkerError

class DummyModel:

    def __init__(self):
        pass
    
    def _set_worker(self, worker):
        pass

    def _set_worker_working(self, worker):
        pass


class TestWorker(unittest.TestCase):

    def setUp(self):
        pass


    def test_1(self):
        """
        Fails since query does not match.
        """
        hmodel = None
        cname = None
        func = None
        version = None
        ilocstr = '_ILOC'
        inputdata = None
        comp_data = {'provides': 
                            [{'name': 'attr1', 'path': 'shared.results.attr1.path'},
                             {'name': 'attr2', 'path': 'shared.results.attr2.path'}]
                           ,
                      'consumes': {
                            'input':
                                   [{'name': 'attr',
                                     'path': 'shared.input.attr.path'}
                                   ],
                            'results': [],
                           }
                    }

        # inputdata = {'shared' : {"input": {"attr": {"path": 2}}}}
                            # [{'name':, 'path':},
                            # {'name':, 'path':}]
                    
        querystring = 'shared.attr.path'
        with self.assertRaises(HubitWorkerError) as context:
            w = _Worker(hmodel,
                        cname,
                        comp_data,
                        inputdata,
                        querystring,
                        func, 
                        version,
                        ilocstr,
                        multiprocess=False,
                        dryrun=True)



    def test_2(self):
        """
        Initialize a simple worker with no ILOC locations or ILOC wildcards
        """
        hmodel = None
        cname = None
        func = None
        version = None
        ilocstr = '_ILOC'
        inputdata = None
        comp_data = {'provides': 
                        [
                        {'name': 'attr1', 'path': 'shared.results.attr1.path'},
                        {'name':'attr2', 'path': 'shared.results.attr2.path'},
                        ],
                     'consumes': 
                       {
                        'input' : [{'name': 'attr', 'path': 'shared.input.attr.path'}], 
                        'results' : [],
                       }
                    }

        # Query something known to exist
        querystring = comp_data['provides'][0]['path']
        w = _Worker(hmodel,
                    cname,
                    comp_data,
                    inputdata,
                    querystring,
                    func, 
                    version,
                    ilocstr,
                    multiprocess=False,
                    dryrun=True)


    def test_3(self):
        """
        Componet provides nothing => error
        """
        hmodel = None
        cname = 'Test component'
        func = None
        version = None
        ilocstr = '_ILOC'
        inputdata = None
        cfg = {'consumes': {'input' : [{'name': 'attr',
                                        'path': 'shared.input.attr.path'
                                       }
                                      ], 
                            'results' : [],
                           }}

        inputdata = None
        querystring = 'shared.results.attr1.path'

        with self.assertRaises(HubitWorkerError) as context:
            w = _Worker(hmodel,
                        cname,
                        cfg,
                        inputdata,
                        querystring,
                        func,
                        version,
                        ilocstr,
                        multiprocess=False,
                        dryrun=True)



    def test_4(self):
        """
        Adding required data to worker stepwise to see that it 
        starts working when all expected consumptions are present

        TODO: split in multiple tests
        """
        hmodel = DummyModel()
        cname = None
        func = None
        version = None
        ilocstr = '_ILOC'
        cfg = {'provides': [{'name': 'attrs1',
                             'path': 'items.:.attr.items.:.path1',}
                            ],
               'consumes': {
                            'input' : [{'name': 'attrs', 
                                        'path': 'items.:.attr.items.:.path'
                                       },
                                       {'name': 'number',
                                        'path': 'some_number'
                                       }
                                       ],
                            'results' : [{'name': 'dependency',
                                          'path': 'value'
                                         },
                                         {'name': 'dependency2',
                                          'path': 'items.:.value'
                                         }
                                        ],
                           }
              }

        # Required for shape inference. TODO: change when shapes are defined in model
        inputdata = {'items' : [
                                {"attr": {"items": [{"path": 2}, {"path": 1}]}},
                                {"attr": {"items": [{"path": 3}, {"path": 4}]}},
                               ],
                      'some_number': 33,
                    }
                    
        querystring = 'items.1.attr.items.0.path1'

        w = _Worker(hmodel,
                    cname,
                    cfg,
                    inputdata,
                    querystring,
                    func,
                    version,
                    ilocstr,
                    multiprocess=False, # Avoid race conditions
                    dryrun=True # Use dryrun to easily predict the result
                    )

        # Set current consumed input and results to nothing so we can fill manually
        w.set_values({}, {})

        input_values = {'some_number': 64.,
                        'items.0.attr.items.0.path': 17.,
                        'items.0.attr.items.1.path': 18.,
                        'items.1.attr.items.0.path': 19.,
                        'items.1.attr.items.1.path': 20.,
                        }

        # Local version of worker input paths pending
        pending_input_paths = list(input_values.keys())

        # add input attributes one by one
        tests_paths_pending = []
        tests_ready_to_work = []
        for key, val in input_values.items():
            w.set_consumed_input(key, val)

            # Update local version
            pending_input_paths.remove(key)

            tests_paths_pending.append(set(pending_input_paths) == 
                                       set(w.pending_input_paths))
            
            # Worker should not be ready to work since consumed results are missing
            tests_ready_to_work.append( w.is_ready_to_work() == False) 


        results_values = {'value': 11.,
                          'items.1.value': 71.,
                          'items.0.value': 49.,
                          }

        pending_results_paths = list(results_values.keys())

        # Add results values
        for key, val in results_values.items():
            w.set_consumed_result(key, val)

            # Update local version
            pending_results_paths.remove(key)

            tests_paths_pending.append(set(pending_results_paths) == 
                                       set(w.pending_results_paths))
            
            # All input is added so should be ready to work when all consumed 
            # results have been set 
            tests_ready_to_work.append( w.is_ready_to_work() == 
                                        (len(pending_results_paths) == 0)) 

        # After adding last attribute the worker starts running (sequentially)
        test_results_ready = w.results_ready() == True

        self.assertTrue(test_results_ready and 
                        all(tests_paths_pending) and 
                        all(tests_ready_to_work))


    def test_5(self):
        """
        Initialize worker with ILOC locations in 
        query and ILOC wildcards in bindings
        """
        hmodel = None
        cname = None
        func = None
        version = None
        ilocstr = '_IDX'
        inputdata = None
        comp_yml = """
                    provides : 
                        - name: k_therm 
                          path: segments._IDX.layers.:.k_therm
                    consumes:
                        input:
                        - name: material
                          path: segments._IDX.layers._IDX.material
                    """
        comp_data = yaml.load(comp_yml, Loader=yaml.FullLoader)

        # Query something known to exist
        querystring = "segments.0.layers.0.k_therm"
        w = _Worker(hmodel,
                    cname,
                    comp_data,
                    inputdata,
                    querystring,
                    func, 
                    version,
                    ilocstr,
                    multiprocess=False,
                    dryrun=True)


    def test_6(self):
        """
        Get bindings for query with two location IDs and component 
        bindings with one index ID and one index wildcard
        """
        bindings = [{"name": "k_therm" ,
                     "path": "segments._IDX.layers.:.k_therm"
                    }]
        ilocstr = "_IDX"
        querystring = "segments.0.layers.0.k_therm"
        path_for_name, ilocs = _Worker.get_bindings(bindings,
                                                    querystring,
                                                    ilocstr)

        # ILOCS for [_IDX] and [:] are both zero base on the query
        expected_ilocs = '0', '0'
        with self.subTest():
            self.assertTupleEqual(ilocs, expected_ilocs)
    
        # This is what will be provided for the query: The attribute 'k_therm' 
        # for all layers for the specific index ID _IDX=0
        expected_path_for_name = {"k_therm": "segments.0.layers.:.k_therm"}
        with self.subTest():
            self.assertDictEqual(expected_path_for_name, path_for_name)


    def test_7(self):
        """Queries should be expanded (location specific)
        otherwise a HubitWorkerError is raised
        """
        provides = [{"name": "k_therm" ,
                    "path": "segments._IDX.layers._IDX.k_therm"
                    }]
        ilocstr = "_IDX"
        querystring = "segments.0.layers.:.k_therm"
        with self.assertRaises(HubitWorkerError) as context:
            _Worker.get_bindings(provides,
                                 querystring,
                                 ilocstr)


    def test_8(self):
        """Expand subscription path with two wildcards gives a nested list
        """
        inputdata =  {'items': [{'attr': {'items': [{'path': 2}, {'path': 1}]}}, 
                                {'attr': {'items': [{'path': 3}, {'path': 4}]}}], 
                      'some_number': 33}
        path_consumed_for_name = {'attrs': 'items.:.attr.items.:.path', 'number': 'some_number'}
        expected_result  = {'attrs': [['items.0.attr.items.0.path', 'items.0.attr.items.1.path'],
                                      ['items.1.attr.items.0.path', 'items.1.attr.items.1.path']], 
                            'number': ['some_number']}
        result, _ = _Worker.expand(path_consumed_for_name,inputdata)
        self.assertDictEqual(expected_result, result)


    def test_9(self):
        """As test 8 but the consumed path only subscribes to element 0 
        of the (leftmost) items. Thus, the expasion leads to a flat list 
        corresponding to the (rightmost) items
        """
        inputdata =  {'items': [{'attr': {'items': [{'path': 2}, {'path': 1}]}}, 
                                {'attr': {'items': [{'path': 3}, {'path': 4}]}}],
                      'some_number': 33}
        path_consumed_for_name = {'attrs': 'items.0.attr.items.:.path', 'number': 'some_number'}
        expected_result  = {'attrs': ['items.0.attr.items.0.path', 'items.0.attr.items.1.path'], 
                            'number': ['some_number']}
        result, _ = _Worker.expand(path_consumed_for_name, inputdata)
        self.assertDictEqual(expected_result, result)

if __name__ == '__main__':
    unittest.main()