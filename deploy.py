#!/usr/bin/python3
"""Do some basic version checks. If these pass and the user confirms 
the code will be tagged and pushed and consequently deployed by the CI/CD pipeline.
"""
from hubit import VERSION
import re
import subprocess
import yaml

allowed_branch = "master"

# Tag only from "allowed_branch"
output = subprocess.run(["git", "branch", "--show-current"], capture_output=True)
branch_name = output.stdout.decode("utf-8").replace("\n", "")
assert branch_name == allowed_branch, f"Can only tag from '{allowed_branch}'"
print(f"On allowed branch: {branch_name}")

# Do not allow local HEAD to be behind origin
subprocess.run(["git", "fetch"])
output = subprocess.run(
    ["git", "rev-list", "--count", f"{allowed_branch}..origin/{allowed_branch}"],
    capture_output=True,
)
behind = output.stdout.decode("utf-8").replace("\n", "")
assert behind == "0", f"Local version version is behind by {behind} commits"

# Do not allow local HEAD to be ahead of origin
output = subprocess.run(
    ["git", "rev-list", "--count", f"origin/{allowed_branch}..{allowed_branch}"],
    capture_output=True,
)
ahead = output.stdout.decode("utf-8").replace("\n", "")
assert ahead == "0", f"Local version version is ahead by {ahead} commits"


with open("CHANGELOG.md", "r") as stream:
    text = stream.read()

# Get the version from the changelog and see if it matches the package version
versions = re.findall(r"\[(?:(\d+\.(?:\d+\.)*\d+))\]", text)
newest_version = versions[0]

assert (
    newest_version == VERSION
), f"Version mismatch: package version is {VERSION} but 'CHANGELOG.md' version is {newest_version}"

with open("mkdocs.yml", "r") as fhandle:
    docs_version = yaml.load(fhandle, Loader=yaml.SafeLoader)["extra"]["version"]

assert (
    docs_version == VERSION
), f"Version mismatch: package version is {VERSION} but 'mkdocs.yml' version is {docs_version}"

# Make sure the Unreleased section does not appear
assert (
    "Unreleased" not in text
), "Cannot deploy with unreleased features in 'CHANGELOG.md'"

# USer confirmation
confirm_deploy = "OK"
answer = input(
    f"Confirm tag & deploy as version '{VERSION}' by typing '{confirm_deploy}': "
)
if answer == confirm_deploy:
    # Tag and push
    subprocess.run(["git", "tag", "-a", VERSION, "-m", f"'Version: {VERSION}'"])
    subprocess.run(["git", "push", "origin", VERSION])
else:
    print("Not tagged, not deployed.")
