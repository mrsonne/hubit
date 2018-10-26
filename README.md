# cqen: connected calculations  

cqen is a calculation engine that allows tools to communicate without coupling them tightly.

Compatible with: __Python 2.7-3.7__.

## Motivation
It seems not uncommon that an ecosystem of stand-alone tools exists within a company or department. These tools may be developped by experts in different teams using different programming laguages and using different input/output formats. Neverthetheless, the tools often depend on the results provided by other tools in the ecosystem leading to complicated and errorprone workflows.

By defining input and results data structures shared between the tools in your your ecosystem cqen allows all your Python-wrapable tools to be seamlessly executed in a single workflow.

## cquen workflow

### Wrapping & wiring
A cqen _model_ is a tool from your ecosystem wrapped to comply with cetain cqen standards. A model will _consume_ certain attributes from the shared input data structure, may _consume_ cetain attributes from the shared results data structure and will _provide_ attributes to the shared results data structures. The attributes consumed and provided for each model are defined in an _interface_ file, which also points to the module where each model is implemented.

### I/O
in order to respond to a user-query. 
- A _Tasks_ manages a collection tasks.
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


The interface file could look something like this 

```yml
wheel_price: # the model name
   path: ../models/wheelprice.py # path to the model
   consumes:
      input:
         rimsize: car.wheels.rim # "rimsize" is the internal name used in the model "car.wheels.rim" is a path in the input data structure
         compound: car.wheels.tire
   provides:
      price: car.wheels.price # "price" is the internal name used in the model "car.wheels.price" is a path in the results data structure
total_price: 
   path: ../models/carprice.py 
   consumes:
      input: 
         car.color
         car.engine.size
         car.wheels.number_of_wheels
      results:
         wheelprize: car.wheels.price # consumes "car.wheels.price" which is provided by the "wheel_price" model
   provides:
      price: car.price
```
The price calculation 

```python
task = Task("interfacefile.yml")
query = "car.price"
response = task.request(query)
results = task.results()
```

The response would look like this.

```
car.price: 1000.
```

The results data structure for the car prize calculation would look like this.

```python
{car: {price: 1000., wheels: {price: 25.}}}
```




## Getting started



------------------


## Installation

```sh
pip install XXXX
```

------------------
## Why this name, Ortoo?



