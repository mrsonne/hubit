import sys
import pathlib
THIS_FILE_DIR =  pathlib.Path(__file__).parent.absolute()
print(THIS_FILE_DIR)
# WORK_DIR = os.getcwd()
# THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_FILE_DIR)
# sys.path.insert(0, os.path.join(THIS_FILE_DIR, "hubit"))
# print(sys.path)

from hubit import VERSION

def define_env(env):
    "Hook function for mkdocs"

    @env.macro
    def get_version():
        return VERSION
