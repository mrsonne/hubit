# cqen: connected calculations  

cqen is a calculation engine that allows tools to communicate without coupling them tightly.

Compatible with: __Python 2.7-3.7__.

## Motivation
It seems not uncommon that an ecosystem of stand-alone tools exists within a company or department. These tools may be developped by experts in different teams using different programming laguages and using different input/output formats. Neverthetheless, the tools often depend on the results provided by other tools in the ecosystem leading to complicated and errorprone workflows.

By defining input and results data structures shared between the tools in your your ecosystem cqen allows all your Python-wrapable tools to be seamlessly executed in a single workflow.

## cquen workflow

### Wrapping & wiring
A cqen _model_ is simply a tool from your ecosystem wrapped to comply with cetain cqen standards. A model will _consume_ certain attributes from the shared input data structure, may _consume_ cetain attributes from the shared results data structure and will _provide_ attributes to the shared results data structures. The attributes consumed and provided for each model are defined in an _interface_ file, which also points to the module where each model is implemented.

As an example imagine we want to calculate the total price of a car. Two tools are available. The first tool "total_price" calculates the total price of a car based on some XXX such at the model, the engine size, the color and the total prize of the wheels. The second tool "wheel_price" calculates the price of one wheel. cqen provides a smooth way of connecting the two tools in a single task.

The input data structure for the car prize calculator could look something like this.

```yml
car:
   model: cruise
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
total_price:
   path: ../models/
   consumes:
      input: 
         car.model
         car.color
         car.engine.size
         car.wheels.number_of_wheels
      results:
         wheelprize: car.wheels.price
   provides:
      price: car.price
wheel_price:
   path: ../models/
   consumes:
      input:
         rimsize: car.wheels.rim
         compound: car.wheels.tire
   provides:
      price: car.wheels.price
```

The results data structure for the car prize calculation would look something like this.

```yml
car:
   price: 1000.
   wheels:
      price: 25.
```


### Running
To set up a cqen _Task_ you need to provide a query on the Results object. If, for example, we wish to calculate the weight and the price of the left back wheel of a car the yaml query could look somthing like this

```yml
car:
   wheels:
       price, weight
```

A query can also be provided a json. based on the consumers and providers in the interface file cqen will call the models required to produce a response to the query. 



in order to respond to a user-query. 
- A _Tasks_ manages a collection tasks.
- The _Results_ object contains all results (including intermediate results) calculated in order to respond to the user-query.
- The _Response_ object is the subset of calculated Results that match the user-query.

### Running


## Getting started



------------------


## Installation

```sh
pip install XXXX
```

------------------
## Why this name, Ortoo?



