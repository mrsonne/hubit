from .shared import get_model

models = (
    "model_1.yml",
    # "model_2.yml",
)
query = (
    "prod_sites[0].prod_lines[0].tanks[2].Q_yield",
    "prod_sites[0].prod_lines[:].tanks[:].Q_yield",
)
for _id, model in enumerate(models, 1):
    hmodel = get_model(model, model_id=_id)
    hmodel.render()
    hmodel.render(query)
