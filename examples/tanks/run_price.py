import logging
from pprint import pprint
from .shared import get_model

# logging.basicConfig(level=logging.INFO)


def run_sales_calc(model_id, input_file="input.yml"):
    use_multi_processing = True
    hmodel = get_model(model_id, input_file)
    response = hmodel.get(
        [
            "prod_sites[:].prod_lines[:].revenue",
        ],
        use_multi_processing=use_multi_processing,
    )
    print("\nModel results")
    pprint(hmodel.results)

    print("\nModel response")
    print(response)

    print("\nRun log")
    print(hmodel.log())


if __name__ == "__main__":
    input_file = "input.yml"
    run_sales_calc("model_1.yml", input_file)
    run_sales_calc("model_1a.yml", input_file)
    run_sales_calc("model_1b.yml", input_file)
    run_sales_calc("model_2.yml", input_file)
