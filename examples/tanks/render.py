from pathlib import Path
from .shared import get_model

model_files = (
    "model_1.yml",
    "model_1a.yml",
    "model_1b.yml",
    "model_2.yml",
)
input_file = "input.yml"
query = ("prod_sites[0].prod_lines[0].tanks[1].Q_yield",)
for model_file in model_files:
    hmodel = get_model(model_file, input_file, model_id=Path(model_file).stem)
    hmodel.render()
    hmodel.render(query)
