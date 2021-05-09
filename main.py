import pathlib
import sys
path = pathlib.Path(__file__).parent.absolute().joinpath("hubit")
sys.path.insert(0, path)
from hubit import VERSION


def define_env(env):
    "Hook function for mkdocs"

    @env.macro
    def get_version():
        return VERSION
