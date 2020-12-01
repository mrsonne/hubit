from __future__ import print_function
import unittest
import pprint

from hubit import worker, shared

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
        cfg = {'provides': {
                            'attr1': 'shared.results.attr1.path',
                            'attr2': 'shared.results.attr2.path',
                           },
               'consumes': {
                            'input' : {'attr':'shared.input.attr.path'}, 
                            'results' : {},
                           }
              }

        inputdata = {'shared' : {"input": {"attr": {"path": 2}}}}
                    
        querystring = 'shared.attr.path'
        with self.assertRaises(IndexError) as context:
            w = worker.Worker(hmodel,
                            cname,
                            cfg,
                            inputdata,
                            querystring,
                            func, 
                            version,
                            ilocstr,
                            multiprocess=False,
                            dryrun=True)

        self.assertTrue('list index out of range' in str(context.exception))


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
        cfg = {'provides': {
                            'attr1': 'shared.results.attr1.path',
                            'attr2': 'shared.results.attr2.path',
                           },
               'consumes': {
                            'input' : {'attr':'shared.input.attr.path'}, 
                            'results' : {},
                           }
              }

        inputdata = None #{'shared' : {"input": {"attr": {"path": 2}}}}            
        querystring = 'shared.results.attr1.path'
        w = worker.Worker(hmodel,
                          cname,
                          cfg,
                          inputdata,
                          querystring,
                          func, 
                          version,
                          ilocstr,
                          multiprocess=False,
                          dryrun=True)

        # TODO: not sure what to test...
        self.assertTrue(True)


    def test_3(self):
        """
        Componet provides nothing => error
        """
        hmodel = None
        cname = 'Test'
        func = None
        version = None
        ilocstr = '_ILOC'
        inputdata = None
        cfg = {'consumes': {
                            'input' : {'attr':'shared.input.attr.path'}, 
                            'results' : {},
                           }
              }

        inputdata = None #{'shared' : {"input": {"attr": {"path": 2}}}}            
        querystring = 'shared.results.attr1.path'

        with self.assertRaises(SystemExit) as context:
            w = worker.Worker(hmodel,
                            cname,
                            cfg,
                            inputdata,
                            querystring,
                            func, 
                            version,
                            ilocstr,
                            multiprocess=False,
                            dryrun=True)

        self.assertTrue('No provider for component "{}"'.format(cname) in str(context.exception))


    def test_4(self):
        """
        Specific query to worker that provides multiple attributes. 
        The worker consumes a single input.
        """
        hmodel = DummyModel()
        cname = None
        func = None
        version = None
        ilocstr = '_ILOC'
        cfg = {'provides': {
                            'attrs1': 'items.:.attr.items.:.path1',
                            'attr2': 'attr2.path',
                           },
               'consumes': {
                            'input' : {'attrs' : 'items.:.attr.path',
                                       'attr' : 'some_number'}, 
                            'results' : {'dependency' : 'value',
                                         'dependency2' : 'items.:.value'},
                           }
              }

        inputdata = {'items' : [
                                # {"attr": {"items": [{"path": 2}]}},
                                # {"attr": {"items": [{"path": 2}]}},
                                {"attr": {"items": [{"path": 2}, {"path": 1}]}},
                                {"attr": {"items": [{"path": 3}, {"path": 4}]}},
                               ] 
                    }
        # pp = pprint.PrettyPrinter(indent=4)
        # pp.pprint(inputdata)
        print inputdata
        # print len(shared.get_from_datadict(inputdata, ("items",)))
        querystring = 'items.0.attr.items.0.path1'        

        w = worker.Worker(hmodel,
                          cname,
                          cfg,
                          inputdata,
                          querystring,
                          func,
                          version,
                          ilocstr,
                          multiprocess=False,
                          dryrun=True)

        print w

        # Set current input (nothing)
        w.set_values(inputdata, {})
        print w

        # add input attribute. Input incomplete.
        w.set_consumed_input('some_number', 64.)
        print w

        # add input attribute. Input incomplete.
        w.set_consumed_input('items.1.attr.path', 17.)
        print w

        # add input attribute. Input complete, but still missing results
        w.set_consumed_input('items.0.attr.path', 21.)
        print w

        # add results attribute.
        w.set_consumed_result('value', 47.)
        print w

        # add results attribute.
        w.set_consumed_result('items.1.value', 71.)
        print w

        # add results attribute. Worker starts running
        w.set_consumed_result('items.0.value', 49.)
        print w

        print w.results_ready()
        print w.result_for_path()


if __name__ == '__main__':
    unittest.main()