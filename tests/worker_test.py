from __future__ import print_function
import unittest
import pprint

from hubit.worker import Worker, HubitWorkerError

class DummyModel(object):

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
        TODO: improve error meassage
        """
        hmodel = None
        cname = None
        func = None
        version = None
        ilocstr = '_ILOC'
        inputdata = None
        comp_data = {'provides': {
                            'attr1': 'shared.results.attr1.path',
                            'attr2': 'shared.results.attr2.path',
                           },
                      'consumes': {
                            'input' : {'attr':'shared.input.attr.path'}, 
                            'results' : {},
                           }
                    }

        # inputdata = {'shared' : {"input": {"attr": {"path": 2}}}}
                    
        querystring = 'shared.attr.path'
        # with self.assertRaises(IndexError) as context:
        w = Worker(hmodel,
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
                        {
                        'attr1': 'shared.results.attr1.path',
                        'attr2': 'shared.results.attr2.path',
                        },
                     'consumes': 
                       {
                        'input' : {'attr':'shared.input.attr.path'}, 
                        'results' : {},
                       }
                    }

        # Query something known to exist
        querystring = comp_data['provides'].values()[0]
        w = Worker(hmodel,
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
        cfg = {'consumes': {'input' : {'attr':'shared.input.attr.path'}, 
                            'results' : {},}}

        inputdata = None
        querystring = 'shared.results.attr1.path'

        with self.assertRaises(HubitWorkerError) as context:
            w = Worker(hmodel,
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
        """
        hmodel = DummyModel()
        cname = None
        func = None
        version = None
        ilocstr = '_ILOC'
        cfg = {'provides': {
                            'attrs1': 'items.:.attr.items.:.path1',
                           },
               'consumes': {
                            'input' : {'attrs' : 'items.:.attr.items.:.path',
                                       'number' : 'some_number'}, 
                            'results' : {'dependency' : 'value',
                                         'dependency2' : 'items.:.value'},
                           }
              }

        # Required for shape inference. TODO: change when shapes are defined in model
        inputdata = {'items' : [
                                {"attr": {"items": [{"path": 2}, {"path": 1}]}},
                                {"attr": {"items": [{"path": 3}, {"path": 4}]}},
                               ],
                      'some_number': 33,
                    }
                    
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(inputdata)
        querystring = 'items.1.attr.items.0.path1'

        w = Worker(hmodel,
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

        # add input attributes one by one
        for key, val in input_values.items():
            w.set_consumed_input(key, val)
            print(w)
            print(w.is_ready_to_work())


        results_values = {'value': 11.,
                          'items.1.value': 71.,
                          'items.0.value': 49.,
                          }

        # add results attribute.
        for key, val in results_values.items():
            w.set_consumed_result(key, val)
            print(w)
            print(w.is_ready_to_work())

        # After adding last attribute the worker starts running (sequentially)
        print(w.results_ready())


if __name__ == '__main__':
    unittest.main()