import pathlib
import pprint
import time
import yaml
import os
from hubit.model import HubitModel
import matplotlib.pyplot as plt
import numpy as np

THIS_DIR = pathlib.Path(__file__).parent
TMP_DIR = THIS_DIR.joinpath("tmp")
pathlib.Path(TMP_DIR).mkdir(parents=True, exist_ok=True)


def n_timesteps(input_data):
    return int(input_data["calc"]["t_end"] / input_data["calc"]["delta_t"]) + 1


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
    n_times = n_timesteps(input_data)
    input_ = {
        "time": [
            {
                "position": [
                    {"dummy": [idx_time, idx_pos]}
                    for idx_pos in range(input_data["init"]["n_positions"])
                ]
            }
            for idx_time in range(n_times)
        ]
    }

    input_.update(input_data)
    input_["calc"].update(
        {"delta_x": input_data["domain"]["length"] / input_data["init"]["n_positions"]}
    )

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

    # TODO: : and -1 doest work yet
    n_times = n_timesteps(inp)
    idx_time_max = n_times - 1
    n_pos = inp["init"]["n_positions"]
    print(f"Number of time-cell elements is {n_pos*n_times}")
    delta_x = inp["calc"]["delta_x"]
    idx_pos_max = n_pos - 1
    pos = delta_x * np.arange(n_pos)

    qpaths = [f"time[{idx_time_max}].position[{idx_pos_max}].u"]
    t_start = time.perf_counter()
    response = model.get(qpaths, use_multi_processing=False)
    elapsed_time = time.perf_counter() - t_start
    print(response)
    print(f"Generated in {elapsed_time} s")

    fig, axs = plt.subplots(2, 1, figsize=(12, 8))

    # Collect data from inlet
    us = [
        [
            model.results[f"time[{idx_time}].position[{idx_pos}].u"]
            for idx_time in range(n_times)
        ]
        for idx_pos in range(n_pos)
    ]

    ts = [
        model.results[f"time[{idx_time}].position[0].t"] for idx_time in range(n_times)
    ]

    us = np.array(us)

    # Plot data from inlet
    for idx_pos, us_ in enumerate(us):
        axs[0].plot(ts, us_, label=f"Idx pos {idx_pos}")

    # Transpose to get times in first index
    us = us.transpose()
    for idx_time, us_ in enumerate(us):
        axs[1].plot(pos, us_, label=f"Idx time {idx_time}")

    axs[0].set_xlabel("time")
    axs[0].set_ylabel("u")
    axs[1].set_xlabel("pos")
    axs[1].set_ylabel("u")
    axs[0].legend()
    axs[1].legend()

    # axs[0].set_title("Inlet (x=0)")
    fig.savefig(TMP_DIR.joinpath("advection.png"))

    # qpaths = ["time[:].position[0].u"]
    # response = model.get(qpaths)
    # print(response)


if __name__ == "__main__":
    inp = make_input()
    print("Input ready")
    run(inp)
