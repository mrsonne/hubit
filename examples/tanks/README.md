# Cascading tanks

This example shows how to set up models where one compartment (cell, element) consumes the result of an upstream neighboring compartment (cell, element). In the example, a liquid flows from one tank to the next in a cascading fashion. The example encompass two similar tanks models `model1` and `model2` that illustrate explicit linking of the tanks useful for unstructured problems and a linking pattern for structured problems, respectively.

## Unstructured compartments - explicit indexing (`model1.yml`)
In this example liquid flows into tank 1 with rate `Q_in,1` where some process takes place. The yield from the process is `Q_yield,1`. Tank 2 is similar to tank 1 only the yield is `Q_yield,1`. The two yield streams are mixed in tank 3 where another process takes place with yield `Q_yield,2`. The entire process is schematically illustrated below

```                           
           ║  Q_in,1                ║ Q_in,2                         
           ║                        ║     
        ┌──║───────┐          ┌─────║──┐         
        │  ˅       │          |     ˅  |            
        │          │          |        |        
        │~~~~~~~~~~│          |~~~~~~~~|
        │  Tank 1  │          | Tank 2 |                   
        └───╥──────┘          └─────╥──┘     
            ║ Q_yield,1   Q_yield,2 ║
          ╔═╩══════════╗    ╔═══════╩══╗ 
Q_spill,1 ║            ║    ║          ║ Q_spill,2
          ˅            ║    ║          ˅         
                     ┌─║────║─┐
                     | ˅    ˅ | 
                     |        |                                         
                     |~~~~~~~~|                                         
                     | Tank 3 |                                         
                     └──╥─────┘
                        ║  
                      ╔═╩════╗                                     
           Q_spill,3  ║      ║  Q_yield,3
                      ˅      ˅
                                                                                 
```

For simplicity, the yields are determined simply from a predefined yield fraction parameter i.e. `Q_yield = yield_fraction * Q_in`. Imagine the three cascading tanks represent one production line on a production site. If we consider only one production site with only one production line, the input for the model could look like this

```yaml
- prod_sites:
  - prod_lines:
    tanks:
      - yield_fraction: 0.5
        Q_in: 20.
        Q_transfer: 0.
      - yield_fraction: 0.6
        Q_in: 10.
        Q_transfer: 0.
      - yield_fraction: 0.25
        Q_in: 0.
```

The fields `prod_sites.prod_lines.tanks[0:2].Q_transfer: 0` and `prod_sites.prod_lines.tanks[2].Q_in: 0` are boundary conditions that have been added to allow the implementation of the calculation code to be the same for all tanks. In this example we will refer to the tanks using explicit indexing to tell `Hubit` that e.g. the yield from tank 1 `Q_yield,1` flows into tank 3. For the first tank, the model component could look like this

```yaml
# First tank
- path: ./components/mod1.py 
  provides_results:
    - name: Q_yield
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_yield
  consumes_input:
    - name: spill_fraction
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].yield_fraction
    - name: Q_in
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_in
    - name: Q_transfer
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_transfer
```

We see that, for a given production site and a given production line on that site, the first tank consumes input (`yield_fraction`, `Q_in` and `Q_transfer`) from element zero in the list of tanks in the input data (`tanks[0@IDX_TANK]`). The component stores results (`Q_yield`) on element zero in the tanks list in the results data.

For the second tank, the model component looks like the model component for tank 1 except all index specifiers point to tank 1 i.e. `...tanks[1@IDX_TANK]`. The model component for the third tanks could look like this

```yaml
# Third tank
- path: ./components/mod1.py 
  provides_results:
    - name: Q_yield
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[2@IDX_TANK].Q_yield
  consumes_input:
    - name: yield_fraction
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[2@IDX_TANK].yield_fraction
    - name: Q_in
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[2@IDX_TANK].Q_in
  consumes_results:
    # use outlet flow from previous tank 0
    - name: Q_transfer_1
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_yield
    # use outlet flow from previous tank 1
    - name: Q_transfer_2
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[1@IDX_TANK].Q_yield
```

The nodes `provides_results` and `consumes_input` look a lot like the equivalent nodes for tanks 1 and 2 except that all index specifiers now refer to index 2 (`[2@IDX_TANK]`). One other important difference is that the second tank consumes the outlet flows `Q_yield` from tanks 1 and 2. Notice that the path to the entrypoint function is the same for both tanks i.e it is the same code that does the actual calculation for each tank although the configuration differs. The complete model definition can be seen in `examples/tanks/model1.yml` in the repository.

With the model in place we can explore some queries and responses.

SHOW EXAMPLE QUERY & RESPONSE HERE. MENTION THAT ALL THREE TANKS ARE EXECUTED. No explicit looping and bookkeeping only `Hubit` configuration. Allow developers of the tank model, which is quite simple here, to work isolated on the tank model and not the entire context in which it will be used.

Note that using _component contexts_ the model components for tanks 1 and two can be refactored to 

```yaml
- path: ./components/mod4.py 
  context:
    IDX_TANK: "0:2"
  provides_results:
    - name: Q_yield
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[IDX_TANK].Q_yield
  consumes_input:
    - name: yield_fraction
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[IDX_TANK].yield_fraction
    - name: Q_in
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[IDX_TANK].Q_in
    - name: Q_transfer
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[IDX_TANK].Q_transfer
```

In this case the component context `context.IDX_TANK: "0:2"` assures that the component is only applied for tank indices 0 and 1. Consequently, the explicit indices i.e. `0@IDX_TANK` and `1@IDX_TANK` are no longer required in this component. The model component for tank 2 shown above can be used as before. This version of the model is shown in `model_1a.yml`.

## Structured compartments - component contexts and index offsets (`model2.yml`)

While it is nice to refer to neighboring tanks it is tiresome if we have many tanks. Further, the model presented above would need to be changed when the number of tanks change which is not attractive. However, one use case for explicit indexing would be models where the cells (compartments/elements) are connected in an unstructured fashion. In such cases the `Hubit` model can be constructed programmatically based on the mesh of cells (compartments/elements). In more structured cases such as this tank example it is better to leverage the two `Hubit` features _component contexts_ and _index offsets_.


```
           ║  Q_in,1                          
           ║              
        ┌──║───────┐           
        │  ˅       │             
        │          │          
        │~~~~~~~~~~│          
        │  Tank 1  │          ║ Q_in,2               
        └───╥──────┘          ║ 
            ║  Q_next,1 ┌─────║──┐
          ╔═╩═══════════|═╗   ˅  | 
Q_spill,1 ║             | ˅      |
          ˅             |~~~~~~~~|
                        | Tank 2 |            ║ Q_in,3
                        └───╥────┘            ║
                            ║  Q_next,2 ┌─────║──┐
                Q_spill,2 ╔═╩═══════════|═╗   ˅  | 
                          ˅             | ˅      |                                         
                                        |~~~~~~~~|                                         
                                        | Tank 3 |                                         
                                        └──╥─────┘
                                           ║  
                               Q_spill,3 ╔═╩════╗                                     
                                         ˅      ˅ Q_next,3
                                                                                 
```

Liquid enters the first tank with a rate `Q_in,1`. The liquid may either be spilled with rate `Q_spill,1` or flow downstream to the next tank with rate `Q_next,1`. Tank 2 receives liquid from tank 1 with `Q_next,1` and additionally fresh liquid is added with rate `Q_in,2`. Similarly for tank 3. For simplicity, the flow rate in the spill streams are determined as some fraction `spill_fraction` of the total flow rate into the tank. For tank 2 the calculation of the spill rate reads 

```
Q_spill,2 = spill_fraction_2 * (Q_next,1 + Q_in,2)
```

while the flow from tank 2 into tank 3 may be written

```
Q_next,2 = (1 - spill_fraction_2) * (Q_next,1 + Q_in,2)
```



To address the issues identified in `model1.yml` we must resort to two features namely component contexts and index offset.

Component contexts limited to to one item => 0 dim and 1 dim problems. forward bla bla 