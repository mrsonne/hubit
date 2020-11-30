import yaml
import os
from itertools import product
from hubit.model import HubitModel, HubitModelQueryError
THISPATH = os.path.dirname(os.path.abspath(__file__))
TMPPATH = os.path.join(THISPATH, 'tmp')

# Create model from a model file
model_file = "model.yml"
modelfile = os.path.join(THISPATH, model_file)
modelname = 'mypipe'
hmodel = HubitModel.from_file(modelfile,
                              name=modelname,
                              output_path=TMPPATH)

# Load the input
inputfile = os.path.join(THISPATH, "input.yml")
with open(inputfile, "r") as stream:
    input_data = yaml.load(stream)

# Set the input on the model object
hmodel.set_input(input_data)

# Validate model # TODO: passes even when the key in results_provided["k_therm"] is misspelled
hmodel.validate()

# Render model
hmodel.render()

# Make the queries
# querystrings = ["segments.0.layers.:.outer_temperature"] # ok
querystrings = ["segments.0.layers.0.outer_temperature"] # ok
# querystrings = ["segments.:.layers.1.k_therm"] # ok
# querystrings = ["segments.0.layers.0.k_therm"] # ok
# querystrings = ["segments.0.layers.:.k_therm"] #ok 
# querystrings = ["segments.:.layers.:.k_therm"] # ok


# Query validation fails for at
try:
    hmodel.validate(["segments.0.layers.0.doesnt_exist"])
except HubitModelQueryError as err:
    print(err)
    # raise err

# Render the query
hmodel.render(querystrings)

# Execute components using multiprocessing
# TODO: mpworkers = True fails to import thermal_conductivity
mpworkers = False

# Important: call multiprocessing from main like this
if __name__ == '__main__': # Required on windows if mpworkers = True
# if True: # Required on windows if mpworkers = True
    # Do the actual query 
    response = hmodel.get(querystrings, mpworkers=mpworkers)
    # print(response)


    
    # For segment 0 sweep over multiple inputs created as the Cartesian product of the input perturbations 
    input_values_for_path = {"segments.0.layers.0.material": ('brick', 'concrete'),
                             "segments.0.layers.0.thickness": (0.08, 0.12,),
                            }


    # responses, inps = hmodel.get_many(querystrings,
    #                                   input_data,
    #                                   input_values_for_path,
    #                                   plot=False,
    #                                   nproc=4)

    # for inp, response in zip(inps, responses):
    #     print('Input',
    #           inp["segments.0.layers.0.material"],
    #           inp["segments.0.layers.0.thickness"])
    #     print('Response', response)
    #     print('')





