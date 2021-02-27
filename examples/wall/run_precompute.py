import logging
from .utils import get_model, HubitModel

logging.basicConfig(level=logging.INFO)


def query_with_precomputed_results(hmodel: HubitModel, mpworkers: bool = False) -> None:
    """
    Demonstrates the reuse_results flag.

    Here two identical queries are performed in sequence. The second is very fast
    since it we reused results already stored on the model. Thus, in the
    second queriy nothin is actually calculated.
    """
    query = ["segments[:].layers[:].outer_temperature"]

    # First query
    response = hmodel.get(query, mpworkers=mpworkers)

    # Same query and reuse stored results
    response = hmodel.get(query, mpworkers=mpworkers, reuse_results=True)

    print("response", response)
    # Get the full results object
    results = hmodel.get_results()
    print("results", results)
    print("outer_temperature", results["segments"][0]["layers"][1]["outer_temperature"])


if __name__ == "__main__":  # Main guard required on windows if mpworkers = True
    hmodel = get_model()
    use_multiprocessing = True
    query_with_precomputed_results(hmodel, mpworkers=use_multiprocessing)
