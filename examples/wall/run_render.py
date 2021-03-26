from .utils import get_model

hmodel = get_model()
hmodel.render()
hmodel.render(query=["segments[:].layers[:].outer_temperature"])
