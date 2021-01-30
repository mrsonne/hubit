import yaml
import os
import logging
from itertools import product
from hubit.model import HubitModel, HubitModelQueryError
THISPATH = os.path.dirname(os.path.realpath(__file__))

# logging.basicConfig(level=logging.INFO)

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


def query(hmodel, render=True, mpworkers=False):
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
    # queries = ["segments[:].layers[:].outer_temperature"] # not ok. Only results for 0,0 and 1,1
    queries = ["segments[0].layers[:].outer_temperature"] 
    # queries = ["segments[0].layers[0].outer_temperature"]   
    # queries = ["segments[:].layers[1].k_therm"] 
    # queries = ["segments[0].layers[0].k_therm"] 
    # queries = ["segments[0].layers[:].k_therm"] 
    # queries = ["segments[:].layers[0].k_therm"] 
    # queries = ["segments[:].layers[:].k_therm"] # not ok. Only results for 0,0 and 1,1

    # Render the query
    if render:
        hmodel.render(queries)

    response = hmodel.get(queries,
                          mpworkers=mpworkers)
    print(response)


def query_with_precomputed_results(hmodel, mpworkers=False):
    queries = ["segments.:.layers.:.outer_temperature"]

    # First query
    response = hmodel.get(queries,
                          mpworkers=mpworkers)

    # Same query and reuse stored results
    response = hmodel.get(queries,
                          mpworkers=mpworkers,
                          reuse_results=True)

    print(response)
    # Get the full results object
    results = hmodel.get_results()
    print(results)


def query_with_custom_results(hmodel, mpworkers=False):
    # Use the set_results method to run a model that bypasses 
    # the default thermal conductivity calculation and uses the 
    # conductivities specified below. These values could 
    # represent some new measurements that we want to see 
    # the effect of in the thermal profile
    results_data = {'segments': {'0': {'layers': 
                                        {'0': {'k_therm': 0.47 },
                                         '1': {'k_therm': 0.025 },
                                         '2': {'k_therm': 0.47 }
                                        },
                                    },
                                 '1': {'layers': 
                                        {'0': {'k_therm': 1.1},
                                         '1': {'k_therm': 0.04},
                                         '2': {'k_therm': 1.1,}
                                        }
                                    }
                                }
                    }
    hmodel.set_results(results_data)
    response = hmodel.get(["segments.:.layers.:.outer_temperature"],
                          mpworkers=mpworkers,
                          reuse_results=True)
    print(response)


def make_sweep(hmodel, nproc=4):
    """Run a parameter sweep

    Args:
        hmodel (HubitModel): Hubit model to be used
        nproc (int, optional): Number of processes
    """
    queries = ["segments.0.layers.:.outer_temperature"] 

    # For segment 0 sweep over multiple inputs created as the Cartesian product of the input perturbations 
    input_values_for_path = {"segments.0.layers.0.material": ('brick', 'concrete'),
                             "segments.0.layers.0.thickness": (0.08, 0.12, 0.15, 0.46,),
                            }


    responses, inps, _ = hmodel.get_many(queries,
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
    use_multiprocessing = True
    query(hmodel, render=False, mpworkers=use_multiprocessing)
    # query_with_precomputed_results(hmodel, mpworkers=use_multiprocessing)
    # query_with_custom_results(hmodel, mpworkers=use_multiprocessing)
    # make_sweep(hmodel, nproc=None)