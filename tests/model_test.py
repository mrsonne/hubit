import unittest
from hubit.model import HubitModel, QueryRunner
import yaml

yml_input = None
model = None

def setUpModule():
        global yml_input
        global model

        # Paths are relative to the root directory where the tests are executed from
        model = """
        rawmaterial_price:
            path: ./examples/pipeline/hcomp_rawmaterial_price.py
            provides: 
                price_tot : price
            consumes:
                input:
                    lengths: segs.:.length
                    materials: segs.:.walls.materials
                    thicknesses: segs.:.walls.thicknesses
                    odias: segs.:.walls.odias
        thermal_conductivity:
            path: ./examples/pipeline/hcomp_thermal_conductivity.py
            provides : {"ks_walls" : "segs._IDX.walls.ks"}
            consumes:
                input: 
                    materials: segs._IDX.walls.materials
        radial_thermal_prof:
            path: ./examples/pipeline/hcomp_radial_thermal_profile.py
            provides:
                temperatures: segs._IDX.walls.temps
                heat_flows: segs._IDX.walls.heat_flows
            consumes:
                input: 
                    temp_bore: segs._IDX.bore.temperature
                    temp_out: segs._IDX.outside.temperature
                results: 
                    ks_walls : segs._IDX.walls.ks
        """

        yml_input = """
        segs:
            - walls:
                odias: [0.2, 0.3]
                thicknesses: [0.01, 0.02]
                materials: [pvdf, pa11]
              bore: 
                temperature: 350.
              outside: 
                temperature: 300.
        """



class TestModel(unittest.TestCase):

    def setUp(self):
        modelname = 'Pipe model'
        cfg = yaml.load(model)
        self.hmodel = HubitModel(cfg, modelname)

        self.input_data = yaml.load(yml_input)
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
        Render the query
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
        modelname = 'Pipe model'
        cfg = yaml.load(model)
        self.hmodel = HubitModel(cfg, modelname)
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