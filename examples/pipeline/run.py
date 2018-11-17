import yaml
import os
from hubit.model import HubitModel, QueryRunner
THISPATH = os.path.dirname(os.path.abspath(__file__))


if __name__ == '__main__':
    modelfile = os.path.join(THISPATH, "model.yml")
    modelname = 'pipe'
    hmodel = HubitModel.from_file(modelfile, name=modelname, odir=THISPATH)

    inputfile = os.path.join(THISPATH, "input_thermal_old.yml")
    with open(inputfile, "r") as stream:
        input_data = yaml.load(stream)

    # Execute components using multiprocessing
    mpworkers = False

    # Validate model
    hmodel.validate()

    # Render model
    hmodel.render(fileidstr='F3')

    # Render query
    querystrings = ["segs.0.walls.temps"]
    hmodel.render(querystrings, input_data, fileidstr='F3')

    # Do the actual query 
    response = hmodel.get(querystrings, input_data, mpworkers=mpworkers, validate=True)
    print(response)

    # Sweep over multiple inputs created as the Cartesian product of the input perturbations 
    paths = ("segs.0.walls.materials",
            "segs.0.walls.thicknesses")
    values = ((('pvdf', 'pa11'), ('xlpe', 'pa11'), ('pvdf', 'hdpe'), ('pa11', 'hdpe')), 
                ([[0.008, 0.01], [0.01, 0.01], [0.012, 0.01]]))
    input_perturbations = dict(zip(paths, values))

    res, inps = hmodel.get_many(querystrings,
                                input_data,
                                input_perturbations,
                                plot=False)

    # Parallel coordinates plot 
    # hmodel.plot(res, inps)

    for i, r in zip(inps, res):
        print i
        print r
        print


    # Query using wildcard for iloc
    querystrings = ["segs.:.walls.temps"]
    hmodel.get(querystrings, input_data, mpworkers=mpworkers, validate=True)

    # Query all components (assumes required input is defined)
    # self.hmodel.get(self.input_data, mpworkers=self.mpworkers)




