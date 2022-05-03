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
    input_ = {
        "time": [
            {
                "position": [
                    {"dummy": [idx_time, idx_pos]}
                    for idx_pos in range(input_data["init"]["n_positions"])
                ]
            }
            for idx_time in range(input_data["init"]["n_times"])
        ]
    }

    input_.update(input_data)

    # Save input (not necessary)
    with open(TMP_DIR.joinpath("input_expanded.yml"), "w") as handle:
        yaml.dump(input_, handle)

    return input_


def run(inp):
    # Load the model
    # with open(THIS_DIR.joinpath("model2.yml"), "r") as stream:
    #     model_cfg = yaml.load(stream, Loader=yaml.FullLoader)
    # pprint.pprint(model_cfg)

    model = HubitModel.from_file(THIS_DIR.joinpath("model2.yml"))
    model.set_input(inp)

    qpaths = ["time[0].position[:].u"]
    response = model.get(qpaths)
    print(response)

    qpaths = ["time[0].position[:].t"]
    response = model.get(qpaths)
    print(response)

    idx_time_max = inp["init"]["n_times"] - 1
    qpaths = [f"time[{idx_time_max}].position[0].u"]
    response = model.get(qpaths, use_multi_processing=False
    print(response)

    for idx_time in range(inp["init"]["n_times"]):
        path = f"time[{idx_time}].position[0].u"
        print(idx_time, model.results[path])

    # qpaths = ["time[:].position[0].u"]
    # response = model.get(qpaths)
    # print(response)


if __name__ == "__main__":
    inp = make_input()
    print("Input ready")
    run(inp)
