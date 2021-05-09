import os
import sys
import pathlib
THIS_FILE_DIR =  pathlib.Path(__file__).parent.absolute()
print(THIS_FILE_DIR)
WORK_DIR = os.getcwd()
# sys.path.insert(0, THIS_FILE_DIR)
sys.path.insert(0, THIS_FILE_DIR.joinpath("hubit"))
# print(sys.path)

from hubit import VERSION

def define_env(env):
    "Hook function for mkdocs"

    @env.macro
    def get_version():
        return VERSION
