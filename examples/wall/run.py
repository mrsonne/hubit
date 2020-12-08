import yaml
import os
from itertools import product
from hubit.model import HubitModel, HubitModelQueryError
THISPATH = os.path.dirname(os.path.realpath(__file__))

def get_model(render=True):
    """Create a HubutModel instance from a model file.

    Args:
        render (bool, optional): Render the model. Defaults to True.

    Returns:
        [HubitModel]: A hubit model corresponding to the model file 
    """
    # Create model from a model file
    model_file = "model.yml"
    modelfile = os.path.join(THISPATH, model_file)
    modelname = 'wall'
    hmodel = HubitModel.from_file(modelfile,
                                name=modelname,
                                output_path='./tmp')

    # Load the input
    inputfile = os.path.join(THISPATH, "input.yml")
    with open(inputfile, "r") as stream:
        input_data = yaml.load(stream, Loader=yaml.FullLoader)

    # Set the input on the model object
    hmodel.set_input(input_data)

    # Validate model 
    hmodel.validate()

    # Render model
    if render:
        hmodel.render()
    return hmodel


def make_queries(hmodel, render=True, mpworkers=False):
    """Show some query functionality

    Args:
        hmodel (HubitModel): Hubit model to be used
        render (bool, optional): Run query rendering. Defaults to True.
        mpworkers (bool, optional): Use multiprocessing. Defaults to False.
    """
    # Query validation fails for at
    # try:
    #     hmodel.validate(["segments.0.layers.0.doesnt_exist"])
    # except HubitModelQueryError as err:
    #     print(err)

    # Make the queries
    # querystrings = ["segments.0.layers.:.outer_temperature"] # problem using multiprocessing
    querystrings = ["segments.0.layers.0.outer_temperature"]  
    # querystrings = ["segments.:.layers.1.k_therm"] 
    # querystrings = ["segments.0.layers.0.k_therm"] 
    # querystrings = ["segments.0.layers.:.k_therm"]  
    querystrings = ["segments.:.layers.:.k_therm"] 

    # Render the query
    if render:
        hmodel.render(querystrings)

    response = hmodel.get(querystrings, mpworkers=mpworkers)
    print(response)


def make_sweep(hmodel, nproc=4):
    """Run a parameter sweep

    Args:
        hmodel (HubitModel): Hubit model to be used
    """
    querystrings = ["segments.0.layers.:.outer_temperature"] 

    # For segment 0 sweep over multiple inputs created as the Cartesian product of the input perturbations 
    input_values_for_path = {"segments.0.layers.0.material": ('brick', 'concrete'),
                             "segments.0.layers.0.thickness": (0.08, 0.12,),
                            }


    responses, inps = hmodel.get_many(querystrings,
                                      input_values_for_path,
                                      nproc=nproc)

    for inp, response in zip(inps, responses):
        print('Input',
              inp["segments.0.layers.0.material"],
              inp["segments.0.layers.0.thickness"])
        print('Response', response)
        print('')


if __name__ == '__main__': # Main guard required on windows if mpworkers = True
    hmodel = get_model(render=False)
    make_queries(hmodel, render=False, mpworkers=True)
    # make_sweep(hmodel)