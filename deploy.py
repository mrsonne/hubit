"""Do some basic version checks. If these pass and the user confirms 
the code will be tagged and pushed and consequently deployed by the CI/CD pipeline.
"""
from hubit import VERSION
import re
import subprocess

output = subprocess.run(["git", "branch", "--show-current"], capture_output=True)
branch_name = output.stdout.decode("utf-8").replace("\n", "")
assert branch_name == "master", "Can only tag from 'master'"
    

with open("CHANGELOG.md", "r") as stream:
    text = stream.read()

# Get the version from the changelog and see if it matches the package version
versions = re.findall(r"\[(?:(\d+\.(?:\d+\.)*\d+))\]", text)
newest_version = versions[0]
assert (
    newest_version == VERSION
), f"Version mismatch: package version is {VERSION} but 'CHANGELOG.md' version is {newest_version}"

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
    subprocess.run(["git", "tag", VERSION])
    subprocess.run(["git", "push", "origin", VERSION])
else:
    print("Not tagged, not deployed.")
