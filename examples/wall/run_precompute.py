import logging
import pprint
from .utils import get_model, HubitModel

logging.basicConfig(level=logging.INFO)


def query_with_precomputed_results(
    hmodel: HubitModel, use_multi_processing: bool = False
) -> None:
    """
    Demonstrates the use_results flag.

    Here two identical queries are performed in sequence. The second is very fast
    since it we reused results already stored on the model. Thus, in the
    second queriy nothin is actually calculated.
    """
    query = ["segments[:].layers[:].outer_temperature"]

    # First query
    response = hmodel.get(query, use_multi_processing=use_multi_processing)

    # Same query and reuse stored results
    response = hmodel.get(
        query, use_multi_processing=use_multi_processing, use_results="current"
    )

    print("response", response)
    # Get the full results object
    results = hmodel.results

    print("\n*** RESULTS (FlatData) ***")
    pprint.pprint(results)

    print("\n*** RESULTS (as dict) ***")
    pprint.pprint(results.as_dict())

    print("\n*** RESULTS (inflated)***")
    pprint.pprint(results.inflate())

    print(
        "outer_temperature",
        results.inflate()["segments"][0]["layers"][1]["outer_temperature"],
    )


if (
    __name__ == "__main__"
):  # Main guard required on windows if use_multi_processing = True
    hmodel = get_model()
    use_multiprocessing = True
    query_with_precomputed_results(hmodel, use_multi_processing=use_multiprocessing)
