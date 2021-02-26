import yaml
import os
from hubit.model import HubitModel

THISPATH = os.path.dirname(os.path.realpath(__file__))


def get_model() -> HubitModel:
    """Create a HubutModel instance from a model file.

    Args:
        render (bool, optional): Render the model. Defaults to True.

    Returns:
        [HubitModel]: A hubit model corresponding to the model file
    """
    # Create model from a model file
    model_file = "model.yml"
    modelfile = os.path.join(THISPATH, model_file)
    modelname = "wall"
    hmodel = HubitModel.from_file(modelfile, name=modelname, output_path="./tmp")

    # Load the input
    inputfile = os.path.join(THISPATH, "input.yml")
    with open(inputfile, "r") as stream:
        input_data = yaml.load(stream, Loader=yaml.FullLoader)

    # Set the input on the model object
    hmodel.set_input(input_data)

    # Validate model
    hmodel.validate()

    return hmodel
