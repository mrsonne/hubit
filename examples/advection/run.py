import pathlib
import pprint
import time
import yaml
import os
from hubit.model import HubitModel
import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import cumulative_trapezoid

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
        {
            "delta_x": input_data["domain"]["length"]
            / (input_data["init"]["n_positions"] - 1)
        }
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

    # model_caching = "after_execution"
    # use_multi_processing = False
    # use_results = "cached"

    model_caching = "after_execution"
    use_multi_processing = False
    use_results = "none"

    # model_caching = "after_execution"
    # use_multi_processing = True
    # use_results = "none"

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
    n_pos = inp["init"]["n_positions"]
    print(f"Number of time-cell elements is {n_pos*n_times}")
    delta_x = inp["calc"]["delta_x"]
    pos = delta_x * np.arange(n_pos)

    qpaths = [f"time[-1].position[-1].u"]
    t_start = time.perf_counter()
    model.set_model_caching(model_caching)
    response = model.get(
        qpaths, use_multi_processing=use_multi_processing, use_results=use_results
    )
    elapsed_time = time.perf_counter() - t_start
    print(response)
    print(f"Response enerated in {elapsed_time} s")
    print(model.log())

    # Collect data u[time, pos]
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
    ts = np.array(ts)
    pos = np.array(pos)

    # Calculate total amount in each time step
    u_tot = [
        cumulative_trapezoid(y=u_profile, x=pos, dx=delta_x, initial=0.0)[-1]
        for u_profile in us.transpose()
    ]

    return response, ts, pos, us, u_tot


def plot(ts, pos, us, u_tot):
    fig, axs = plt.subplots(2, 1, figsize=(12, 8))
    # Plot time series for each position
    num_time_series = 5
    idxs_pos = np.unique(
        np.linspace(0, pos.shape[0] - 1, dtype="int", num=num_time_series)
    )
    for idx_pos in idxs_pos:
        axs[0].plot(ts, us[idx_pos, :], label=f"Pos {pos[idx_pos]:7.2e}")

    # Transpose to get times in first index
    num_domain_profiles = 12
    idxs_time = np.unique(
        np.linspace(0, ts.shape[0] - 1, dtype="int", num=num_domain_profiles)
    )
    for idx_time in idxs_time:
        axs[1].plot(
            pos,
            us[:, idx_time],
            label=f"Time {ts[idx_time]:7.1e} (u_tot={u_tot[idx_time]:7.2e})",
        )

    axs[0].set_xlim(ts[0], ts[-1])
    axs[1].set_xlim(pos[0], pos[-1])
    axs[0].set_xlabel("Time")
    axs[0].set_ylabel("u")
    axs[1].set_xlabel("Position")
    axs[1].set_ylabel("u")
    axs[0].legend()
    axs[1].legend(ncol=2, loc="upper right")

    # axs[0].set_title("Inlet (x=0)")
    fig.savefig(TMP_DIR.joinpath("advection.png"))

    # qpaths = ["time[:].position[0].u"]
    # response = model.get(qpaths)
    # print(response)


if __name__ == "__main__":
    inp = make_input()
    print("Input ready")
    response, ts, pos, us, u_tot = run(inp)
    plot(ts, pos, us, u_tot)
