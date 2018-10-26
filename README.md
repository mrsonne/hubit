# cqen: connected calculations  

cqen is a calculation engine that allows tools to communicate without coupling them tightly.

Compatible with: __Python 2.7-3.7__.

## Motivation
It seems not uncommon that an ecosystem of stand-alone tools exists within a company or department. These tools may be developped by experts in different teams using different programming laguages and using different input/output formats. Neverthetheless, the tools often depend on the results provided by other tools in the ecosystem leading to complicated and errorprone workflows.

By defining a common data structure cqen allows all your Python-wrapable tools to be seamlessly executed in a single workflow.

## Terminology

- A _model_ is a component that carries out a domain specific calculation.
- A _Worker_ is a model wrapped to fit the framework.
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



