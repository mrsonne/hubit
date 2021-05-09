# Required for Github actions to work...
import sys
import pathlib

THIS_FILE_DIR = pathlib.Path(__file__).parent.absolute()
sys.path.insert(0, THIS_FILE_DIR.as_posix())
sys.path.insert(0, THIS_FILE_DIR.joinpath("hubit").as_posix())

from hubit import VERSION


def define_env(env):
    "Hook function for mkdocs"

    @env.macro
    def get_version():
        return VERSION
