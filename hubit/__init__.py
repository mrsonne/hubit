VERSION = "0.3.0"
import shutil


# Make HubitModel available as from hubit import model
from .model import HubitModel, _CACHE_DIR


def clear_hubit_cache():
    """
    Clear the cache for all models. Will delete all serialized model cache
    from the disk.
    """
    shutil.rmtree(_CACHE_DIR, ignore_errors=True)
