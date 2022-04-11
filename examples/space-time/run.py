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
    with open(os.path.join(THIS_DIR, "input.yml"), "r") as stream:
        input_data = yaml.load(stream, Loader=yaml.FullLoader)

    # Create all cells
    input_ = {
        "batches": [{"cells": [input_data["cell"]] * input_data["calc"]["n_cells"]}]
        * input_data["calc"]["n_batches"]
    }

    # Boundary condition all cells at  t = 0
    feed_concs = [0.0 for _ in input_data["feed"]["concs"]]
    input_["feed"] = [
        {"concs": feed_concs, "V": 0} for icell in range(input_data["calc"]["n_cells"])
    ]
    input_["feed"][0]["concs"] = input_data["feed"]["concs"]
    input_["feed"][0]["V"] = input_data["feed"]["V"]

    # Save input (not necessary)
    with open(os.path.join(TMP_DIR, "input_expanded.yml"), "w") as handle:
        yaml.dump(input_, handle)

    return input_


def run():
    # Load the model
    with open(os.path.join(THIS_DIR, "model.yml"), "r") as stream:
        model_cfg = yaml.load(stream, Loader=yaml.FullLoader)
    pprint.pprint(model_cfg)


if __name__ == "__main__":
    inp = make_input()
    pprint.pprint(inp)
    run()