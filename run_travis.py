#!/usr/bin/python3
import subprocess
import yaml
import logging

logging.basicConfig(level=logging.INFO)

with open(".travis.yml", "r") as stream:
    steps = yaml.load(stream, Loader=yaml.SafeLoader)["script"]

# TODO: find examples automatically and run a unit tests marked "slow"
local_steps = (
    "coverage html -d htmlcov",
    "python -m examples.car.run",
    "python -m examples.car.render",
    "python -m examples.tanks.run",
    "python -m examples.tanks.render",
    "python -m examples.tanks.run_price",
    "python -m examples.wall.run_queries",
    "python -m examples.wall.render",
    "python -m examples.wall.run_precompute",
    "python -m examples.wall.run_set_results",
    "python -m examples.wall.run_min_temperature",
    "python -m examples.wall.run_sweep",
)
steps.extend(local_steps)

nsteps = len(steps)
for istep, step in enumerate(steps, 1):
    logging.info(f"Running step {istep} of {nsteps}: {step}")
    subprocess.run(step, shell=True, check=True)
