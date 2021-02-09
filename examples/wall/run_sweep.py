import logging
from math import isclose
from operator import getitem
from typing import Any, Dict
from .utils import get_model, HubitModel
from hubit.shared import convert_to_internal_path, inflate
logging.basicConfig(level=logging.INFO)


def skipfun(flat_input: Dict) -> bool:
    """
    Skip factor combination if the thickness of the two segments differ
    """
    input = inflate(flat_input)
    seg_thcks = [ sum([layer["thickness"] for layer in segment["layers"].values()]) 
                  for segment in input["segments"].values() ]
    ref = seg_thcks[0]
    return not all( [isclose(ref, seg_thck, rel_tol=1e-5) 
                    for seg_thck in seg_thcks[1:]] )


def make_sweep(hmodel: HubitModel, nproc:Any=None) -> None:
    """Run a parameter sweep

    Args:
        hmodel (HubitModel): Hubit model to be used
        nproc (Any, optional): Number of processes. Default is None and 
        leaves it to Hubit to determine the number of processes to use.
    """
    queries = ['heat_transfer_number', 'energy_class', 'total_cost']

    # For segment 0 sweep over multiple inputs created as the 
    # Cartesian product of the input perturbations 
    input_values_for_path = {"segments[0].layers[2].material": ('rockwool', 'glasswool'),
                             "segments[0].layers[2].thickness": (0.04, 0.08, 0.12, 0.16),
                             "segments[1].layers[1].thickness": (0.025, 0.065, 0.105),
                            }

    input_paths = list(input_values_for_path.keys())
    # TODO implement zip-style get_many
    responses, inps, _ = hmodel.get_many(queries,
                                         input_values_for_path,
                                         skipfun=skipfun,
                                         nproc=nproc)

    # Print results in a primitive table
    header_for_path = {"segments[0].layers[2].material": 'Seg0 Ins. Mat.',
                       "segments[0].layers[2].thickness": 'Seg0 Ins. Thck. [m]',
                       "segments[1].layers[1].thickness": 'Seg1 Ins. Thck. [m]',
                       }
    headers = [header_for_path[path] for path in input_paths] + list(responses[0].keys())
    widths = [len(header) + 5 for header in headers]
    fstr = ''.join( [f'{{:<{width}}}' for width in widths])
    sepstr = sum(widths)*'-'
    lines = ['\nInsulation sweep', sepstr]
    lines.append( fstr.format(*headers) )
    lines.append( sepstr )
    for inp, response in zip(inps, responses):
        values = [getitem(inp, convert_to_internal_path(ipath)) 
                  for ipath in input_paths]
        values.extend( [response[qpath] for qpath in queries] )
        lines.append( fstr.format(*values) )
    lines.append( sepstr )

    print('\n'.join(lines))

if __name__ == '__main__': # Main guard required on windows if mpworkers = True
    make_sweep(get_model(), nproc=None)