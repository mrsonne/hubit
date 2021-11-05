#!/usr/bin/python3
import subprocess
import yaml

with open(".travis.yml", "r") as stream:
    steps = yaml.load(stream)["script"]

extra_steps = ("coverage html -d htmlcov",)
steps.extend(extra_steps)

nsteps = len(steps)
for istep, step in enumerate(steps, 1):
    print(f"Running step {istep} of {nsteps}: {step}")
    subprocess.run(step, shell=True)
