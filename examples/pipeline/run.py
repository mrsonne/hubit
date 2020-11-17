import yaml
import os
from itertools import product
from hubit.model import HubitModel, QueryRunner
THISPATH = os.path.dirname(os.path.abspath(__file__))
TMPPATH = os.path.join(THISPATH, 'tmp')

model_file = "model.yml"
modelfile = os.path.join(THISPATH, model_file)
modelname = 'mypipe'
hmodel = HubitModel.from_file(modelfile, name=modelname, odir=TMPPATH)

inputfile = os.path.join(THISPATH, "input.yml")
with open(inputfile, "r") as stream:
    input_data = yaml.load(stream)

# Set the input on the model object
hmodel.set_input(input_data)


# Validate model # TODO: passes even when the key in results_provided["k_therm"] is misspelled
# hmodel.validate()

# Render model
# hmodel.render()

# Render the query
querystrings = ["segments.0.layers.:.temperature"] # ok
# querystrings = ["segments.0.layers.0.temperature"] # ok
# querystrings = ["segments.:.layers.1.k_therm"] # ok
# querystrings = ["segments.0.layers.0.k_therm"] # ok
# querystrings = ["segments.0.layers.:.k_therm"] #ok 
# querystrings = ["segments.:.layers.:.k_therm"] # not ok 
# hmodel.render(querystrings)

# Execute components using multiprocessing
mpworkers = False

# Do the actual query 
# response = hmodel.get(querystrings, mpworkers=mpworkers)
# print(response)

# For segment 0 sweep over multiple inputs created as the Cartesian product of the input perturbations 
input_values_for_path = {"segments.0.layers.0.material": ('pvdf', 'xlpe'),
                         "segments.0.layers.0.thickness": (0.008, 0.01,),
                        }


# Important: call multiprocessing from main like this
if __name__ == '__main__':
    responses, inps = hmodel.get_many(querystrings,
                                      input_data,
                                      input_values_for_path,
                                      plot=False,
                                      nproc=4)

    for inp, response in zip(inps, responses):
        print('Input',
              inp["segments.0.layers.0.material"],
              inp["segments.0.layers.0.thickness"])
        print('Response', response)
        print('')

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




