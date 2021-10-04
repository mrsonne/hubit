from pprint import pprint
from .shared import get_model

# logging.basicConfig(level=logging.INFO)
# For hard refs


def run():
    model_id = "model4.yml"

    hmodel = get_model(model_id, input_file="input4.yml")

    query = ["prod_sites[0].prod_lines[0].tanks[2].Q_yield"]
    print(f"\nQuery")
    pprint(query)
    print(f"Spawns 1 worker")
    response = hmodel.get(query, use_multi_processing=False)
    print("Response (one path & value):")
    pprint(response)
    print(hmodel.log())
    hmodel.clean_log()


if __name__ == "__main__":
    run()
