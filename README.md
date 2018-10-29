# hubit - a calculation hub  

`hubit` is a hub for your existing calculation tools. It allows you to 

- execute calculation tools as one composite model without coupling them tightly,
- make parameter sweeps,
- feed old results into new calculations,
- run your tools in parallel,
- visualize the composite model.

Compatible with: __Python 2.7-3.7__.

## Motivation
It seems not uncommon that an ecosystem of stand-alone tools exists within a company or department. These tools may be developped by  different teams using different programming laguages and using different input/output formats. Neverthetheless, the tools often depend on results provided the other tools leading to complicated and errorprone workflows.

By defining input and results data structures shared between your tools hubit allows all your Python-wrapable tools to be seamlessly executed as a single model.


## Getting started



------------------


## Installation

```sh
pip install XXXX
```

------------------


## cquen workflow

### Wrapping & wiring
A `hubit` _component_ is a tool from your ecosystem wrapped to comply with cetain `hubit` standards. A component 

- _consumes_ certain attributes from the shared input data structure, 
- may _consume_ cetain attributes from the shared results data structure, and 
- _provides_ attributes to the shared results data structures. 

The attributes consumed and provided are defined in a _model_ file.

### I/O
in order to respond to a user-query.
- The _Results_ object contains all results (including intermediate results) calculated in order to respond to the user-query.
- The _Response_ object is the subset of calculated Results that match the user-query.


### Example
As an example imagine we want to calculate the total price of a car. For historic reasons two tools are available. The first tool "total_price" calculates the total price of a car based on the engine size, the color and the total prize of the wheels. The second tool "wheel_price" calculates the price of one wheel. `hubit` provides a smooth way of connecting the two tools and calculate the car price in a single step.

The shared input data structure for the car prize calculation could look something like this.

```yml
car:
   color: silver
   engine:
      size: 1.6
   wheels:
      number_of_wheels: 4
      tire: soft
      rim: 16
```

The model file could look something like this 

```yml
wheel_price: # the component name
   path: ../models/wheelprice.py # path to the component
   consumes:
      input:
         rimsize: car.wheels.rim # "rimsize" is the internal name used in the "wheel_price" component. "car.wheels.rim" is a path in the shared input data structure
         compound: car.wheels.tire
   provides:
      price: car.wheels.price # "price" is the internal name used in the "wheel_price" component. "car.wheels.price" is a path in the shared results data structure
total_price: 
   path: ../models/carprice.py 
   consumes:
      input: 
         car.color
         car.engine.size
         car.wheels.number_of_wheels
      results:
         wheelprize: car.wheels.price # consumes "car.wheels.price" from the shared results data structure. 
   provides:
      price: car.price
```
The price calculation 

```python
from hubit import HubitModel
hmodel = HubitModel("modelfile.yml")
query = ["car.price"]
response = hmodel.get(query)
results = model.results()
```

The response would look like this.

```python
{car.price: [1000.]}
```

The results for the car prize calculation includes all intermediate results and would look like this.

```python
[{car: {price: 1000., wheels: {price: 25.}}}]
```

`hubit` manages the execution order of the tools in the model so that the wheel price calculation is executed before the car price calculation. For the same model the query `car.wheels.price` would give a response like this

```python
{car.wheels.price: 100}
```

In this case, `hubit` wil only execute the wheel price tool. Running the wheel price and the car price in two steps can be achieved like this

```python
from hubit import HubitModel
hmodel = HubitModel("modelfile.yml")
query = ["car.wheels.price"]
response = hmodel.get(query)
oldresults = model.results()
response = hmodel.get("car.price", results=oldresults)
results = model.results()
```

In this case, the second the calculation corresponding to the query `car.price` will not require the "wheel_price" tool to be executed since the results are provided from a previous calculation. This allows for results patching.

