from black import Path
import yaml
import os
from hubit.model import HubitModel

THISPATH = os.path.dirname(os.path.realpath(__file__))


def get_model(filename, input_file, model_id=""):
    hmodel = HubitModel.from_file(
        os.path.join(THISPATH, filename),
        name=f"tank_{model_id}_{Path(input_file).stem}",
        output_path="./tmp",
    )

    # Load the input
    with open(
        os.path.join(THISPATH, input_file),
        "r",
    ) as stream:
        input_data = yaml.load(stream, Loader=yaml.FullLoader)

    # Set the input on the model object
    hmodel.set_input(input_data)
    return hmodel
