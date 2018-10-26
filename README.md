# cqen: connected calculations  

cqen is a calculation engine that allows tools to communicate without coupling them tightly.

Compatible with: __Python 2.7-3.7__.

## Motivation
It seems not uncommon that an ecosystem of stand-alone tools exists within a company or department. These tools may be developped by experts in different teams using different programming laguages and using different input/output formats. Neverthetheless, the tools often depend on the results provided by other tools in the ecosystem leading to complicated and errorprone workflows.

By defining input and results data structures shared between the tools in your your ecosystem cqen allows all your Python-wrapable tools to be seamlessly executed in a single workflow.

## cquen workflow

### Wrapping & wiring
A cqen _model_ is simply a tool from your ecosystem wrapped to comply with cetain cqen standards. A model will _consume_ certain attributes on the shared input data structure, may _consume_ cetain attributes on the shared results data structure and will _provide_ attributes to the shared results data structures. The attribute consumed and provided for each model are defined in an _interface_ file, which also points to the location module where each model is implemented.

Wrap each tool in your ecosystem as a cqen _model_, which simply involves "conneting" the input attributes that are consumed to the corresponding input attribute in the tool input. Similarly the attributes being provided to the shared results object should be "connected" to the corresponding output attribute in the tool output.

As an example let us consider the car defined in the car input 
```yml
car:
   wheels:
      front:
         size: 16
         tire:
         rim:
      back:
         size: 14
         tyre: 
         rim:
```

A tool calculates the weight and another tool calculates the price for all four wheels on the car.

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



