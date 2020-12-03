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
        Adding required data to worker stepwise and manually
        """
        hmodel = DummyModel()
        cname = None
        func = None
        version = None
        ilocstr = '_ILOC'
        cfg = {'provides': {
                            'attrs1': 'items.:.attr.items.:.path1',
                            # 'attr2': 'attr2.path',
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
                   multiprocess=False,
                   dryrun=True)

        # Set current consumed input and results to nothing so we can fill manually
        w.set_values({}, {})
        print('No data yet\n', w)

        # add input attribute. Input incomplete.
        w.set_consumed_input('some_number', 64.)
        print(w)

        # add input attribute. Input complete, but still missing results
        w.set_consumed_input('items.0.attr.items.0.path', 17.)
        w.set_consumed_input('items.0.attr.items.1.path', 18.)
        w.set_consumed_input('items.1.attr.items.0.path', 19.)
        # w.set_consumed_input('items.1.attr.items.1.path', 20.)
        print(w)

        # add results attribute.
        w.set_consumed_result('value', 47.)
        print(w)

        # add results attribute.
        w.set_consumed_result('items.1.value', 71.)
        print(w)

        # add results attribute. Worker starts running
        w.set_consumed_result('items.0.value', 49.)
        print(w)

        print(w.results_ready())
        # print(w.result_for_path())


if __name__ == '__main__':
    unittest.main()