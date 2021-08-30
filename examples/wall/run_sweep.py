import logging
from pprint import pprint
from math import isclose
from operator import getitem
from typing import Any, Dict
from .utils import get_model, HubitModel
from hubit.config import FlatData, HubitModelPath

logging.basicConfig(level=logging.INFO)


def skipfun(flat_input: FlatData) -> bool:
    """
    Skip factor combination if the thickness of the two wall segments differ
    """
    input = flat_input.inflate()

    inner_materials = [
        segment["layers"][0]["material"]
        for segment in input["segments"].values()
        if segment["type"] == "wall"
    ]
    different_inner_mat = len(set(inner_materials)) > 1

    outer_materials = [
        segment["layers"][len(segment["layers"]) - 1]["material"]
        for segment in input["segments"].values()
        if segment["type"] == "wall"
    ]
    different_outer_mat = len(set(outer_materials)) > 1

    seg_thcks = [
        sum([layer["thickness"] for layer in segment["layers"].values()])
        for segment in input["segments"].values()
        if segment["type"] == "wall"
    ]

    ref = seg_thcks[0]
    not_all_eq_tck = not all(
        [isclose(ref, seg_thck, rel_tol=1e-5) for seg_thck in seg_thcks[1:]]
    )
    return not_all_eq_tck or different_inner_mat or different_outer_mat


def make_sweep(hmodel: HubitModel, nproc: Any = None) -> None:
    """Run a parameter sweep

    Args:
        hmodel (HubitModel): Hubit model to be used
        nproc (Any, optional): Number of processes. Default is None and
        leaves it to Hubit to determine the number of processes to use.
    """
    query = ["heat_transfer_number", "energy_class", "total_cost"]

    # Cartesian product of the input perturbations
    input_values_for_path = {
        "segments[0].layers[0].material": ("brick", "concrete"),  # inner layer
        "segments[2].layers[0].material": ("brick", "concrete"),
        "segments[0].layers[3].material": ("brick", "concrete"),  # outer layer
        "segments[2].layers[2].material": ("brick", "concrete"),
        "segments[0].layers[2].thickness": (
            0.08,
            0.12,
        ),  # insulation thickness
        "segments[2].layers[1].thickness": (
            0.025,
            0.065,
        ),
    }

    # The skip function determines which factor combinations should be included
    responses, inps, _ = hmodel.get_many(
        query, input_values_for_path, skipfun=skipfun, nproc=nproc
    )

    # Print results in a primitive table with no fancy dependecies
    header_for_path = {
        "segments[0].layers[0].material": "Inner Mat.",
        "segments[0].layers[3].material": "Outer Mat.",
        "segments[0].layers[2].thickness": "Seg0 Ins. Thck. [m]",
        "segments[2].layers[1].thickness": "Seg1 Ins. Thck. [m]",
    }

    input_paths = list(header_for_path.keys())
    headers = [header_for_path[path] for path in input_paths] + list(
        responses[0].keys()
    )
    q_float_formats = dict(zip(query, [".2f", "", ".0f"]))
    float_formats = [
        q_float_formats[header] if header in q_float_formats else ""
        for header in headers
    ]
    padding = 3
    widths = [len(header) + padding for header in headers]
    fstr = "".join([f"{{:<{width}}}" for width in widths])
    sepstr = sum(widths) * "-"
    lines = ["\nWall sweep", sepstr]
    lines.append(fstr.format(*headers))
    lines.append(sepstr)
    fstr = "".join(
        [
            f"{{:<{width}{float_format}}}"
            for width, float_format in zip(widths, float_formats)
        ]
    )
    for inp, response in zip(inps, responses):
        values = [getitem(inp, ipath) for ipath in input_paths]
        values.extend([response[qpath] for qpath in query])
        lines.append(fstr.format(*values))
    lines.append(sepstr)

    print("\n".join(lines))


if (
    __name__ == "__main__"
):  # Main guard required on windows if use_multi_processing = True
    make_sweep(get_model(), nproc=None)
