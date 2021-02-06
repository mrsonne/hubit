import logging
from .utils import get_model, HubitModel

logging.basicConfig(level=logging.INFO)

def query_with_custom_results(hmodel: HubitModel, mpworkers=False) -> None:
    """
    Demonstrates how to manually set results on the model. 
    Hubit then ommits re-calculating the results thus bypassing 
    the component that is normally responsible for 
    calculating the results.
    
    The values that are set manually could represent some 
    new measurements that we want to see the effect of when 
    propagated in through the remaining components downstream 
    of the component that is normally responsible for 
    calculating the results that are manually set.
    """
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
    query = ["segments[:].layers[:].outer_temperature"]
    response = hmodel.get(query,
                          mpworkers=mpworkers,
                          reuse_results=True)
    print(response)




if __name__ == '__main__': # Main guard required on windows if mpworkers = True
    hmodel = get_model(render=False)
    use_multiprocessing = True
    query_with_custom_results(hmodel, mpworkers=use_multiprocessing)
