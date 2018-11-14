import yaml
from hubit.model import HubitModel, QueryRunner


if __name__ == '__main__':
    modelfile = "model.yml"
    modelname = 'Pipe model'
    hmodel = HubitModel.from_file(modelfile, modelname)

    inputfile = "input_thermal_old.yml"
    with open(inputfile, "r") as stream:
        input_data = yaml.load(stream)

    # Execute components using multiprocessing
    mpworkers = False

    # Validate model
    hmodel.validate()

    # Render model
    hmodel.render()

    # Render query
    querystrings = ["segs.0.walls.temps"]
    hmodel.render(querystrings, input_data)

    # Do the actual query 
    response = hmodel.get(querystrings, input_data, mpworkers=mpworkers, validate=True)
    print(response)

    # Sweep over multiple inputs created as the Cartesian product of the input perturbations 
    paths = ("segs.0.walls.materials",
            "segs.0.walls.thicknesses")
    # values = ((('pvdf', 'pa11'), ('xlpe', 'pa11'), ('pvdf', 'hdpe'), ('pa11', 'hdpe')), 
    #             ([[0.008, 0.01], [0.01, 0.01], [0.012, 0.01]]))
    values = ((('pvdf', 'pa11'), ('xlpe', 'pa11')), 
                ([[0.008, 0.01], [0.01, 0.01]]))
    input_perturbations = dict(zip(paths, values))

    res, inps = hmodel.get_many(querystrings,
                                input_data,
                                input_perturbations)


    for i, r in zip(inps, res):
        print i
        print r
        print
