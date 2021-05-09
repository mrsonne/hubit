import os
WORK_DIR = os.getcwd()
THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
print('WORK_DIR', WORK_DIR)
print('THIS_FILE_DIR', THIS_FILE_DIR)

from .hubit import VERSION

def define_env(env):
    "Hook function for mkdocs"

    @env.macro
    def get_version():
        return VERSION
