import yaml
import os
from hubit.model import HubitModel, QueryRunner
THISPATH = os.path.dirname(os.path.abspath(__file__))
TMPPATH = os.path.join(THISPATH, 'tmp')

model_file = "model2.yml"
modelfile = os.path.join(THISPATH, model_file)
modelname = 'mypipe'
hmodel = HubitModel.from_file(modelfile, name=modelname, odir=TMPPATH)

inputfile = os.path.join(THISPATH, "input_thermal2.yml")
with open(inputfile, "r") as stream:
    input_data = yaml.load(stream)

# Set the input on the model object
hmodel.set_input(input_data)


# Validate model
hmodel.validate()

# Render model
hmodel.render()

# Render the query
# querystrings = ["segments.0.layers.:.temps"]
# querystrings = ["segments.0.layers.0.temps"]
querystrings = ["segments.:.layers.0.ktherm"] # ok
# querystrings = ["segments.0.layers.0.ktherm"] # ok
# querystrings = ["segments.0.layers.:.ktherm"] #ok 
hmodel.render(querystrings)

# Execute components using multiprocessing
mpworkers = False

# Do the actual query 
# response = hmodel.get(querystrings, mpworkers=mpworkers)
# print(response)

# # Sweep over multiple inputs created as the Cartesian product of the input perturbations 
# paths = ("segs.0.walls.materials",
#         "segs.0.walls.thicknesses")
# values = ((('pvdf', 'pa11'), ('xlpe', 'pa11'), ('pvdf', 'hdpe'), ('pa11', 'hdpe')), 
#             ([[0.008, 0.01], [0.01, 0.01], [0.012, 0.01]]))
# input_perturbations = dict(zip(paths, values))

# res, inps = hmodel.get_many(querystrings,
#                             input_data,
#                             input_perturbations,
#                             plot=False)

# # Parallel coordinates plot 
# # hmodel.plot(res, inps)

# for i, r in zip(inps, res):
#     print i
#     print r
#     print


# Query using wildcard for iloc
# querystrings = ["segs.:.walls.temps"]
# hmodel.get(querystrings, input_data, mpworkers=mpworkers, validate=True)

# Query all components (assumes required input is defined)
# self.hmodel.get(self.input_data, mpworkers=self.mpworkers)




