import logging
import pprint

from hubit.model import HubitModel
from .utils import get_model

logging.basicConfig(level=logging.INFO)


def run_query(hmodel: HubitModel, use_multi_processing: bool):
    response = hmodel.get(
        ["service_layer_minimum_temperature"],
        use_multi_processing=use_multiprocessing,
    )

    print(hmodel.log())
    pprint.pprint(hmodel.results)
    print("\nResponse", response)


if __name__ == "__main__":
    hmodel = get_model()
    use_multiprocessing = True
    run_query(hmodel, use_multi_processing=use_multiprocessing)
