import logging
from pprint import pprint
from .shared import get_model

# logging.basicConfig(level=logging.INFO)
# For hard refs


def run(model_id, input_file="input.yml"):

    ltot = 100
    ltitle = len(model_id)
    lpad = int(0.5 * (ltot - ltitle))
    rpad = ltot - lpad - ltitle

    print("*" * ltot)
    print("{:<}{}{:>}".format("*" * lpad, model_id, "*" * rpad))
    print("*" * ltot)
    hmodel = get_model(model_id, input_file)

    query = [f"prod_sites[0].prod_lines[0].tanks[0].Q_yield"]
    run_yield_calc(
        use_multi_processing,
        hmodel,
        query,
        response_description="one path & corresponding value",
    )

    query = [f"prod_sites[0].prod_lines[0].tanks[2].Q_yield"]
    run_yield_calc(
        use_multi_processing,
        hmodel,
        query,
        response_description="one path & corresponding value",
    )

    query = [f"prod_sites[0].prod_lines[0].tanks[-1].Q_yield"]
    run_yield_calc(
        use_multi_processing,
        hmodel,
        query,
        response_description="one path & corresponding value",
    )

    query = [f"prod_sites[-1].prod_lines[0].tanks[-1].Q_yield"]
    run_yield_calc(
        use_multi_processing,
        hmodel,
        query,
        response_description="one path & corresponding value",
    )

    query = ["prod_sites[:].prod_lines[:].tanks[-1].Q_yield"]
    run_yield_calc(
        use_multi_processing,
        hmodel,
        query,
        response_description="one path with values as items in double nested list",
    )

    query = ["prod_sites[:].prod_lines[:].tanks[2].Q_yield"]
    run_yield_calc(
        use_multi_processing,
        hmodel,
        query,
        response_description="one path with values as items in double nested list",
    )

    query = [
        f"prod_sites[0].prod_lines[0].tanks[0].Q_yield",
        f"prod_sites[0].prod_lines[0].tanks[1].Q_yield",
        f"prod_sites[0].prod_lines[0].tanks[2].Q_yield",
    ]
    run_yield_calc(
        use_multi_processing,
        hmodel,
        query,
        response_description="three paths & corresponding values",
    )

    query = [f"prod_sites[0].prod_lines[0].tanks[:].Q_yield"]
    run_yield_calc(
        use_multi_processing,
        hmodel,
        query,
        response_description="one path with values as items in a list",
    )

    query = [f"prod_sites[0].prod_lines[:].tanks[:].Q_yield"]
    run_yield_calc(
        use_multi_processing,
        hmodel,
        query,
        response_description="one path with values as items in double nested list",
    )

    query = ["prod_sites[:].prod_lines[:].tanks[:].Q_yield"]
    run_yield_calc(
        use_multi_processing,
        hmodel,
        query,
        response_description="one path with values as items in triple nested list",
    )


def run_yield_calc(use_multi_processing, hmodel, query, response_description):
    """The yield calculation is sequential and in this example there is always
    one worker per tank
    """
    # This is where the actions is
    response = hmodel.get(query, use_multi_processing=use_multi_processing)

    # Below is some consistency checks and printing
    print("\nQuery")
    pprint(query)
    n_workers_expected = len(hmodel.results)
    log = hmodel.log()
    n_workers = sum(log.get_all("worker_counts")[0].values())
    assert (
        n_workers == n_workers_expected
    ), f"Expected {n_workers_expected} worker but {n_workers} were spawned."
    print(f"Spawns {n_workers_expected} workers")
    print(f"Response ({response_description}):")
    pprint(response)
    print(log)
    hmodel.clean_log()


if __name__ == "__main__":
    use_multi_processing = False

    # One production site with one production line.
    input_file = "input.yml"
    run("model_1.yml", input_file)
    run("model_1a.yml", input_file)
    run("model_1b.yml", input_file)
    run("model_2.yml", input_file)

    # Same model definitions but different input used for
    # two production sites each with one production line.
    # The production lines in the two sites have 3
    # and 4 tanks, respectively.
    input_file = "input_2_prod_sites.yml"
    run("model_1.yml", input_file)
    run("model_1a.yml", input_file)
    run("model_1b.yml", input_file)
    run("model_2.yml", input_file)
