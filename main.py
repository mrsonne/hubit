import pathlib
print(pathlib.Path(__file__).parent.absolute().joinpath("hubit"))
from hubit import VERSION


def define_env(env):
    "Hook function for mkdocs"

    @env.macro
    def get_version():
        return VERSION
