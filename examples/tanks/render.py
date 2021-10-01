from .shared import get_model

models = (
    "model1.yml",
    "model2.yml",
    "model3.yml",
)
query = (
    "sites[0].lines[0].tanks[2].vol_outlet_flow",
    "sites[0].lines[:].tanks[:].vol_outlet_flow",
)
for _id, model in enumerate(models, 1):
    hmodel = get_model(model, model_id=_id)
    hmodel.render()
    hmodel.render(query)
