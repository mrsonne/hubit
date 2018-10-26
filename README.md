# cqen: connected calculations  

cqen is a calculation engine that allows tools to communicate without coupling them tightly.

Compatible with: __Python 2.7-3.7__.

## Motivation
It seems not uncommon that an ecosystem of stand-alone tools exists within a company or department. These tools may be developped by experts in different teams using different programming laguages and using different input/output formats. Neverthetheless, the tools often depend on the results provided by other tools in the ecosystem leading to complicated and errorprone workflows.

By defining input and results data structures shared between the tools in your your ecosystem cqen allows all your Python-wrapable tools to be seamlessly executed in a single workflow.

## cquen workflow

### Wrapping

Each tool in your ecosystem should be wrpped as a cqen _model_ so that each model carries out some domain-specific calculation. In an _interface_ file you define how your models interact with the shared input and output data structures. A model may _consume_ certain input attributes and should _provide_ some results attributes.

A _Worker_ is a model wrapped to fit the framework. This wrapping is automatically handled by cqen  

- A _Task_ manages a collection of workers in order to respond to a user-query. 
- A _Tasks_ manages a collection tasks.
- The _Results_ object contains all results (including intermediate results) calculated in order to respond to the user-query.
- The _Response_ object is the subset of calculated Results that match the user-query.

## Getting started

```python
some_example(args)
```


------------------


## Installation

```sh
pip install XXXX
```

------------------
## Why this name, Ortoo?



