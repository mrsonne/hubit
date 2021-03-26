import logging
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

    # Run queries one by one (slow)
    hmodel.set_model_caching("after_execution")
    for path in query:
        print(f"Query: {path}")
        response = hmodel.get(path, use_multi_processing=use_multi_processing)
        print(response)
        print("")
    t_separate = sum(hmodel.log().get_all("elapsed_time"))

    for path in query:
        response = hmodel.get(
            path, use_results="cached", use_multi_processing=use_multi_processing
        )
    t_separate_cached = sum(hmodel.log().get_all("elapsed_time")) - t_separate

    # Run queries as one (fast). The speed increase comes from Hubit's
    # results caching that acknowledges that the first query actually produces
    # the results for all the remaining queries
    query = [item for path in query for item in path]
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    print(response)
    t_joint = sum(hmodel.log().get_all("elapsed_time")) - t_separate_cached - t_separate

    response = hmodel.get(
        query, use_results="cached", use_multi_processing=use_multi_processing
    )
    print(response)
    t_joint_cached = (
        sum(hmodel.log().get_all("elapsed_time"))
        - t_joint
        - t_separate_cached
        - t_separate
    )

    print(f"\nSummary")
    print(f"Time for separate queries: {t_separate:.1f} s")
    print(f"Time for separate queries using model cache: {t_separate_cached:.1f} s")
    print(f"Time for joint query: {t_joint:.1f} s")
    print(f"Time for joint query using model cache: {t_joint_cached:.1f} s")


if (
    __name__ == "__main__"
):  # Main guard required on windows if use_multi_processing = True
    hmodel = get_model()
    use_multiprocessing = True
    # simple_query()
    query(hmodel, use_multi_processing=use_multiprocessing)
