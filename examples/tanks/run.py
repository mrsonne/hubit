import logging
from pprint import pprint
from .shared import get_model

# logging.basicConfig(level=logging.INFO)
# For hard refs


def run(model_id, input_file="input.yml"):
    use_multi_processing = False

    ltot = 100
    ltitle = len(model_id)
    lpad = int(0.5 * (ltot - ltitle))
    rpad = ltot - lpad - ltitle

    print("*" * ltot)
    print("{:<}{}{:>}".format("*" * lpad, model_id, "*" * rpad))
    print("*" * ltot)
    hmodel = get_model(model_id, input_file)

    prod_site = 0

    # Should result in a number
    query = [f"prod_sites[{prod_site}].prod_lines[0].tanks[0].Q_yield"]
    print(f"\nQuery")
    pprint(query)
    print(f"Spawns 1 worker")
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    print("Response (one path & value):")
    pprint(response)
    print(hmodel.log())
    hmodel.clean_log()

    # Should result in a number
    query = [f"prod_sites[{prod_site}].prod_lines[0].tanks[1].Q_yield"]
    print(f"\nQuery")
    pprint(query)
    print(f"Spawns 2 workers")
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    print("Response (one path & value):")
    pprint(response)
    print(hmodel.log())
    hmodel.clean_log()

    # Should result in a number
    print(f"\nQuery")
    query = [f"prod_sites[{prod_site}].prod_lines[0].tanks[2].Q_yield"]
    pprint(query)
    print(f"Spawns 3 workers")
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    print("Response (one path & value):")
    pprint(response)
    # pprint(hmodel.results)
    print(hmodel.log())
    hmodel.clean_log()

    # Should result in a number
    # TODO: negative-indices. this is not right!!!!
    print(f"\nQuery")
    query = [f"prod_sites[-1].prod_lines[0].tanks[-1].Q_yield"]
    # query = [f"prod_sites[1].prod_lines[0].tanks[2].Q_yield"]
    pprint(query)
    print(f"Spawns 3 workers")
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    print("Response (one path & value):")
    print(response)
    print(hmodel.log())
    hmodel.clean_log()

    # Should result in double nested list
    print(f"\nQuery")
    query = ["prod_sites[:].prod_lines[:].tanks[-1].Q_yield"]
    pprint(query)
    print(f"Spawns 6 workers")
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    print("Response (one path with double nested list as value):")
    pprint(response)
    print(hmodel.log())
    hmodel.clean_log()

    # Should result in double nested list
    print(f"\nQuery")
    query = ["prod_sites[:].prod_lines[:].tanks[2].Q_yield"]
    pprint(query)
    print(f"Spawns 6 workers")
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    print("Response (one path with double nested list as value):")
    pprint(response)
    print(hmodel.log())
    hmodel.clean_log()

    # # Should result in three numbers
    query = [
        f"prod_sites[{prod_site}].prod_lines[0].tanks[0].Q_yield",
        f"prod_sites[{prod_site}].prod_lines[0].tanks[1].Q_yield",
        f"prod_sites[{prod_site}].prod_lines[0].tanks[2].Q_yield",
    ]
    print(f"\nQuery")
    pprint(query)
    print(f"Spawns 3 workers")
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    print("Response (three paths & corresponding values)")
    pprint(response)
    print(hmodel.log())
    hmodel.clean_log()

    # Should result in 1D array
    query = [f"prod_sites[{prod_site}].prod_lines[0].tanks[:].Q_yield"]
    print(f"\nSpawns 3 workers: {query}")
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    print("Response (One path with list as value):")
    print(response)
    print(hmodel.log())
    hmodel.clean_log()

    # Should result in double nested list
    query = [f"prod_sites[{prod_site}].prod_lines[:].tanks[:].Q_yield"]
    print(f"\nSpawns 3 workers: {query}")
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    print("Response (One path with double nested list as value):")
    print(response)
    print(hmodel.log())
    hmodel.clean_log()

    # Should result in triple nested list
    query = ["prod_sites[:].prod_lines[:].tanks[:].Q_yield"]
    print(f"\nSpawns 3 workers: {query}")
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    print("Response (One path with triple nested list as value):")
    print(response)
    print(hmodel.log())
    hmodel.clean_log()


if __name__ == "__main__":
    input_file = "input.yml"
    run("model_1.yml", input_file)
    run("model_1a.yml", input_file)
    run("model_1b.yml", input_file)
    run("model_2.yml", input_file)

    # input_file = "input_2_prod_sites.yml"
    # run("model_1.yml", input_file)
    # run("model_1a.yml", input_file)
    # run("model_1b.yml", input_file)
    # run("model_2.yml", input_file)
