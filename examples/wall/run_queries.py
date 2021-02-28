import logging
import time
from .utils import get_model, HubitModel

logging.basicConfig(level=logging.INFO)


def simple_query() -> None:
    query = [
        #  "total_cost",
        "segments[:].cost"
        #  "heat_transfer_number"
    ]
    response = hmodel.get(query)
    print(response)


def query(hmodel: HubitModel, use_multi_processing: bool = False) -> None:
    """Demonstrates some query functionality into the thermal part of the
    wall composite model.

    Args:
        hmodel (HubitModel): Hubit model to be used
        render (bool, optional): Run query rendering. Defaults to True.
        use_multi_processing (bool, optional): Use multiprocessing. Defaults to False.
    """
    # Query validation fails for at
    # try:
    #     hmodel.validate(["segments.0.layers.0.doesnt_exist"])
    # except HubitModelQueryError as err:
    #     print(err)

    # Make the queries
    query = (
        ["segments[:].layers[:].weight"],
        ["heat_transfer_number", "energy_class", "total_cost"],
        ["heat_transfer_number"],
        ["segments[:].heat_flow"],
        ["segments[:].layers[:].outer_temperature"],
        ["segments[0].layers[0].outer_temperature"],
        ["segments[:].layers[1].k_therm"],
        ["segments[0].layers[0].k_therm"],
        ["segments[0].layers[:].k_therm"],
        ["segments[:].layers[0].k_therm"],
        ["segments[:].layers[:].k_therm"],
    )

    time1 = time.time()

    # Run queries one by one (slow)
    for path in query:
        print(f"Query: {path}")
        response = hmodel.get(path, use_multi_processing=use_multi_processing)
        print(response)
        print("")

    time2 = time.time()

    # Run queries as one (fast). The speed increase comes from Hubit's
    # results caching that acknowledges that the first query actually produces
    # the results for all the remaining queries
    query = [item for path in query for item in path]
    time3 = time.time()
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    print(response)
    time4 = time.time()

    print(f"\nSummary")
    print(f"Time for separate queries: {time2 - time1:.1f} s")
    print(f"Time for joint queries: {time4 - time3:.1f} s")


if (
    __name__ == "__main__"
):  # Main guard required on windows if use_multi_processing = True
    hmodel = get_model()
    use_multiprocessing = True
    # simple_query()
    query(hmodel, use_multi_processing=use_multiprocessing)
