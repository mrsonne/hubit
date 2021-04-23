﻿[![Build Status](https://travis-ci.com/mrsonne/hubit.svg?branch=master)](https://travis-ci.com/mrsonne/hubit)
[![Coverage Status](https://coveralls.io/repos/github/mrsonne/hubit/badge.svg?branch=master)](https://coveralls.io/github/mrsonne/hubit?branch=master)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Version](https://img.shields.io/pypi/v/hubit.svg)](https://pypi.python.org/pypi/hubit/)
[![Python versions](https://img.shields.io/pypi/pyversions/hubit.svg)](https://pypi.python.org/pypi/hubit/)

# hubit - a calculation hub  

## At a glance

`hubit` is an event-driven orchestration hub for your existing calculation tools. It allows you to 

- execute calculation tools as one `hubit` composite model with a loose coupling between the model components,
- easily run your existing calculation tools in asynchronously in multiple processes,
- query the model for specific results thus avoiding explicitly coding (fixed) call graphs and running superfluous calculations,
- make parameter sweeps,
- feed previously calculated results into new calculations thus augmenting old results objects,
- incremental results caching and calculation restart from cache,
- caching of model component results allowing `hubit` to bypass repeated calculations,
- visualize your `hubit` composite model i.e. visualize your existing tools and the attributes that flow between them.

## Motivation
Many work places have developed a rich ecosystem of stand-alone tools. These tools may be developed/maintained by different teams using different programming languages and using different input/output data models. Nevertheless, the tools often depend on results provided the other tools leading to complicated and error-prone (manual) workflows.

By defining input and results data structures that are shared between your tools `hubit` allows all your Python-wrappable tools to be seamlessly executed asynchronously as a single model. Asynchronous multi-processor execution often assures a better utilization of the available CPU resources compared to sequential single-processor execution. This is especially true when some time is spent in each component. In practice this performance improvement often compensates the management overhead introduced by `hubit`.
Executing a fixed call graph is faster than executing the same call graph dynamically created by `hubit`. Nevertheless, a fixed call graph will typically encompass all relevant calculations and provide all results, which in many cases will represent wasteful compute since only a subset of the results are actually needed. `hubit` dynamically creates the smallest possible call graph that can provide the results that satisfy the user's query.  


## Installation & requirements

Install from pypi
```sh
pip install hubit
```


Install from GitHub
```sh
pip install git+git://github.com/mrsonne/hubit.git
```

To render `hubit` models and queries you need to install Graphviz (https://graphviz.org/download/). On e.g. Ubuntu, Graphviz can be installed using the command

```sh
sudo apt install graphviz
```

## Teaser

The full documentation, use cases and an in-depth tutorial can be found in the [`Hubit` examples ](https://mrsonne.github.io/hubit/examples/), which is a part of the documentation. Below is a brief example of how to use `Hubit` once the model is configured.

To get results from a `Hubit` model requires you to submit a _query_, which tells `Hubit` what attributes from the results data structure you want to have calculated. After `Hubit` has processed the query, i.e. executed relevant components, the values of the queried attributes are returned in the _response_.

```python
# Load model from file
hmodel = HubitModel.from_file('model1.yml',
                              name='car')

# Load the input
with open("input.yml", "r") as stream:
    input_data = yaml.load(stream, Loader=yaml.FullLoader)

# Set the input on the model object
hmodel.set_input(input_data)

# Query the model
query = ['cars[0].price']
response = hmodel.get(query)
```

The response looks like this

```python
{'cars[0].price': 4280.0}
```

A query for parts prices for all cars looks like this

```python
query = ['cars[:].parts[:].price']
response = hmodel.get(query)
```

and the corresponding response is

```python
{'cars[:].parts[:].price': [[480.0, 1234.0, 178.0, 2343.0, 45.0],
                            [312.0, 1120.0, 178.0, 3400.0]],
```


`Hubit` can render models and queries. In the example below we have [rendered][hubit.model.HubitModel.render] the query `cars[0].price` i.e. the price of the car at index 0 using 

```python
query = ['cars[0].price']
hmodel.render(query)
```

which yields the graph shown below.

<a target="_blank" rel="noopener noreferrer" href="https://github.com/mrsonne/hubit/blob/master/examples/car/images/query_car_2.png">
  <img src="https://github.com/mrsonne/hubit/raw/master/examples/car/images/query_car_2.png" width="1000" style="max-width:100%;">
</a>

The graph illustrates nodes in the input data structure, nodes in the the results data structure, the calculation components involved in creating the response as well as hints at which attributes flow in and out of these components.
