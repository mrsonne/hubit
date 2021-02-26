import yaml
import os
from hubit.model import HubitModel

THISPATH = os.path.dirname(os.path.realpath(__file__))


def get_model(filename, model_id=""):
    hmodel = HubitModel.from_file(
        os.path.join(THISPATH, filename), name=f"car_{model_id}", output_path="./tmp"
    )

    # Load the input
    with open(os.path.join(THISPATH, "input.yml"), "r") as stream:
        input_data = yaml.load(stream, Loader=yaml.FullLoader)

    # Set the input on the model object
    hmodel.set_input(input_data)
    return hmodel
