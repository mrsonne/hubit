import unittest
from hubit.model import HubitModel, QueryRunner
import yaml

class TestModel(unittest.TestCase):

    def setUp(self):
        modelfile = "./examples/model.yml"
        modelname = 'Pipe model'
        self.hmodel = HubitModel.from_file(modelfile, modelname)

        inputfile = "./examples/input_thermal_old.yml"
        with open(inputfile, "r") as stream:
            self.input_data = yaml.load(stream)

        self.mpworkers = False


    def test_validate(self):
        self.hmodel.validate()


    def test_render_model(self):
        """
        Render the whole model
        """
        self.hmodel.render()


    def test_render_query(self):
        """
        Render the whole model
        """
        querystrings = ["segs.0.walls.temps"]
        self.hmodel.render(querystrings, self.input_data)


    def test_get(self):
        querystrings = ["segs.0.walls.temps"]
        self.hmodel.get(querystrings, self.input_data, mpworkers=self.mpworkers, validate=True)


    def test_sweep(self):
        """
        TODO: change model and input IL variations only involve IL i.e. something like
        segs.0.walls.0.material
        """
        paths = ('segs.0.walls.materials',
                 "segs.0.walls.thicknesses")
        values = ((('pvdf', 'pa11'), ('xlpe', 'pa11'), ('pvdf', 'hdpe'), ('pa11', 'hdpe')), 
                  ([[0.008, 0.01], [0.01, 0.01], [0.012, 0.01]]))
        input_perturbations = dict(zip(paths, values))
        print 'input_perturbations', input_perturbations

        querystrings = ["segs.0.walls.temps"]
        res, inps = self.hmodel.get_many(querystrings,
                                         self.input_data,
                                         input_perturbations)


        for i, r in zip(inps, res):
            print i
            print r
            print


class TestRunner(unittest.TestCase):

    def setUp(self):
        modelfile = "./examples/model.yml"
        modelname = 'Petrobras pipe model'
        self.hmodel = HubitModel.from_file(modelfile, modelname)
        self.mpworkers = False
        self.qr = QueryRunner(self.hmodel, self.mpworkers)

    def test_worker1(self):
        w = self.qr.worker_for_query("segs.0.walls.ks")
        print(w)


    def test_worker2(self):
        w = self.qr.worker_for_query("segs.0.walls.temps")
        print(w)


    def test_no_provider(self):
        """
        No provider for query
        """
        with self.assertRaises(KeyError) as context:
            self.qr.worker_for_query("segs.0.walls.kxs")

        self.assertTrue('No provider for query' in str(context.exception))

if __name__ == '__main__':
    unittest.main()