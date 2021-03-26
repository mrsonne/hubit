VERSION = "0.2.0"

import shutil
import os

# Make HubitModel available as from hubit import model
from .model import HubitModel, _CACHE_DIR


def clear_hubit_cache():
    shutil.rmtree(_CACHE_DIR, ignore_errors=True)
