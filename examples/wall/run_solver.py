import logging
import pprint
from .utils import get_model

logging.basicConfig(level=logging.INFO)


def run() -> None:
    query = ["segments[0].heat_flux"]
    query = ["segments[0].layers[:].k_therm"]
    response = hmodel.get(query)
    print(response)
    pprint.pprint(hmodel.results)


if __name__ == "__main__":
    hmodel = get_model("model_1.yml")
    use_multiprocessing = True
    run()
