import os
import sys
WORK_DIR = os.getcwd()
THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(THIS_FILE_DIR, "hubit"))
print(sys.path)

from hubit import VERSION

def define_env(env):
    "Hook function for mkdocs"

    @env.macro
    def get_version():
        return VERSION
