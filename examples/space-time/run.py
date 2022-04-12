import pathlib
import pprint
import yaml
import os
from hubit.model import HubitModel

THIS_DIR = pathlib.Path(__file__).parent
TMP_DIR = THIS_DIR.joinpath("tmp")
pathlib.Path(TMP_DIR).mkdir(parents=True, exist_ok=True)


def make_input():
    """Take the original input and create input object more
    suitable for Hubit

    The input specifies the number of (identical) cells and the number
    of batches we want to run through the cells as well as the parameters
    for the cells.
    """
    # Load the input
    with open(THIS_DIR.joinpath("input.yml"), "r") as stream:
        input_data = yaml.load(stream, Loader=yaml.FullLoader)

    # Boundary condition all cells at t = 0
    feed_concs = [0.0 for _ in input_data["feed"]["concs"]]

    # Create all cells
    input_ = {
        "batches": [
            {
                "cells": [{**input_data["cell"], "ini": {"concs": feed_concs, "V": 0}}]
                * input_data["calc"]["n_cells"]
            }
        ]
        * input_data["calc"]["n_batches"]
    }

    for batch in input_["batches"]:
        batch["cells"][0]["ini"]["concs"] = input_data["feed"]["concs"]
        batch["cells"][0]["ini"]["V"] = input_data["feed"]["V"]

    # input_["cells"] = [
    #     {"ini": {"concs": feed_concs, "V": 0}}
    #     for _ in range(input_data["calc"]["n_cells"])
    # ]

    # input_["cells"][0]["ini"]["concs"] = input_data["feed"]["concs"]
    # input_["cells"][0]["ini"]["V"] = input_data["feed"]["V"]

    # Save input (not necessary)
    with open(TMP_DIR.joinpath("input_expanded.yml"), "w") as handle:
        yaml.dump(input_, handle)

    return input_


def run(inp):
    # Load the model
    with open(THIS_DIR.joinpath("model.yml"), "r") as stream:
        model_cfg = yaml.load(stream, Loader=yaml.FullLoader)
    # pprint.pprint(model_cfg)

    model = HubitModel.from_file(THIS_DIR.joinpath("model.yml"))
    model.set_input(inp)

    qpaths = ["batches[0].cells[-1].mole_numbers_feed"]
    # qpaths = ["batches[0].cells[-1].V_liq"]
    response = model.get(qpaths)
    print(response)


if __name__ == "__main__":
    inp = make_input()
    # pprint.pprint(inp)
    run(inp)