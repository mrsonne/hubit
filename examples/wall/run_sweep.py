import logging
from typing import Any
from .utils import get_model, HubitModel
logging.basicConfig(level=logging.INFO)

def make_sweep(hmodel: HubitModel, nproc:Any=None) -> None:
    """Run a parameter sweep

    Args:
        hmodel (HubitModel): Hubit model to be used
        nproc (Any, optional): Number of processes. Default is None and 
        leaves it to Hubit to determine the number of processes to use.
    """
    queries = ["segments[0].layers[:].outer_temperature"] 

    # For segment 0 sweep over multiple inputs created as the 
    # Cartesian product of the input perturbations 
    input_values_for_path = {"segments[0].layers[0].material": ('brick', 'concrete'),
                             "segments[0].layers[0].thickness": (0.08, 0.12, 0.15, 0.46,),
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
    make_sweep(get_model(render=False), nproc=None)