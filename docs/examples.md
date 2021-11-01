{% include 'docs/shared/header.html' %}

# Examples

The examples described on the following pages are summarized below.

* [`Car`](example-car.md) encompass four similar car models and is a good first introduction to basic `Hubit` terminology. The examples illustrate how you can model configuration file to interface with toy calculations for the price of a car that each have different levels of modularity. Further, the example illustrates model-level caching and component-level caching.
* [`Wall`](example-wall.md) illustrates heat flow calculations and cost calculations for a wall with three segments. Each wall segment has multiple wall layers that consist of different materials and has different thicknesses. The example demonstrates model rendering (`render.py`), simple queries (`run_queries.py`) with model level caching, reusing previously calculated results `run_precompute.py`, setting results manually (`run_set_results.py`) and input parameter sweeps (`run_sweep.py`). In `run_queries.py` a toggle makes it easy to run with or without multi-processing and the the effect on the wall time.
* [`Tanks`](example-tanks.md). This example shows how to set up models where one domain (compartment/cell/element) consumes results from a neighboring domain. In the example, a liquid flows from one tank to the next in a cascading fashion. The example encompass two similar tanks models `model_1` and `model_2`. The former illustrates explicit linking of the tanks, which is useful for an unstructured network of tanks. The latter illustrates a linking pattern which is useful for a structured network of tanks.

To run, for example, the car example clone the repository and execute the command below from the project root

```sh
python -m examples.car.run
```

In the examples all calculations are, for simplicity, carried out directly in the 
`Hubit` entrypoint function, but the function could just as well wrap a C library, request 
data from a web service or use an installed Python package.