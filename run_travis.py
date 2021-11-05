#!/usr/bin/python3
import subprocess
import yaml
import logging

logging.basicConfig(level=logging.INFO)

with open(".travis.yml", "r") as stream:
    steps = yaml.load(stream, Loader=yaml.SafeLoader)["script"]

extra_steps = ("coverage html -d htmlcov",)
steps.extend(extra_steps)

nsteps = len(steps)
for istep, step in enumerate(steps, 1):
    logging.info(f"Running step {istep} of {nsteps}: {step}")
    subprocess.run(step, shell=True)
