# hubit: a calculation hub  

hubit is allows tools to communicate without coupling them tightly.

Compatible with: __Python 2.7-3.7__.

## Motivation
It seems not uncommon that an ecosystem of stand-alone tools exists within a company or department. These tools may be developped by  different teams using different programming laguages and using different input/output formats. Neverthetheless, the tools often depend on results provided the other tools leading to complicated and errorprone workflows.

By defining input and results data structures shared between your tools hubit allows all your Python-wrapable tools to be seamlessly executed as a single model.

## cquen workflow

### Wrapping & wiring
A cqen _component_ is a tool from your ecosystem wrapped to comply with cetain cqen standards. A component _consumes_ certain attributes from the shared input data structure, may _consume_ cetain attributes from the shared results data structure and _provides_ attributes to the shared results data structures. The attributes consumed and provided for each component are defined in an _model_ file, which also points to the module where each component is implemented.

### I/O
in order to respond to a user-query.
- The _Results_ object contains all results (including intermediate results) calculated in order to respond to the user-query.
- The _Response_ object is the subset of calculated Results that match the user-query.


### Example
As an example imagine we want to calculate the total price of a car. For historic reasons two tools are available. The first tool "total_price" calculates the total price of a car based on the engine size, the color and the total prize of the wheels. The second tool "wheel_price" calculates the price of one wheel. cqen provides a smooth way of connecting the two tools and calculate the car price in a single step.

The input data structure for the car prize calculator could look something like this.

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
   path: ../models/wheelprice.py # path to the model
   consumes:
      input:
         rimsize: car.wheels.rim # "rimsize" is the internal name used in the component "car.wheels.rim" is a path in the input data structure
         compound: car.wheels.tire
   provides:
      price: car.wheels.price # "price" is the internal name used in the component "car.wheels.price" is a path in the results data structure
total_price: 
   path: ../models/carprice.py 
   consumes:
      input: 
         car.color
         car.engine.size
         car.wheels.number_of_wheels
      results:
         wheelprize: car.wheels.price # consumes "car.wheels.price" which is provided by the "wheel_price" component
   provides:
      price: car.price
```
The price calculation 

```python
model = CQModel("modelfile.yml")
query = ["car.price"]
response = model.get(query)
results = model.results()
```

The response would look like this.

```python
{car.price: [1000.]}
```

The results data structure for the car prize calculation would look like this.

```python
[{car: {price: 1000., wheels: {price: 25.}}}]
```




## Getting started



------------------


## Installation

```sh
pip install XXXX
```

------------------
## Why this name, Ortoo?



