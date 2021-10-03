# Cascading tanks

This example shows how to set up models where one compartment (cell, element) consumes the result of an upstream neighboring compartment (cell, element). In the example, a liquid flows from one tank to the next in a cascading fashion. The example encompass two similar tanks models `model1` and `model2` that illustrate explicit linking of the tanks and a more generic linking pattern, respectively.

The two models have three tanks connected as schematically illustrated below.

---------------------


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

Imagine the three cascading tanks represent one production line on a production site. If we consider only show one production site with only one production line, the input for the model could look like this

```yaml
- prod_sites:
  - prod_lines:
    tanks:
      - spill_fraction: 0.5
        Q_in: 20.
        Q_prev: 0.
      - spill_fraction: 0.6
        Q_in: 0.
      - spill_fraction: 0.25
        Q_in: 0.
```

The field `prod_sites.prod_lines.tanks[0].Q_prev: 0` is a boundary condition that allows the implementation of the calculation code to be the same for all tanks. Let us explore two ways of constructing the `Hubit` model.
## Explicit indexing (`model1.yml`)

In this example we will refer to upstream tanks using explicit indexing to tell `Hubit` that e.g. the flow out of tank 1 `Q_next,1` flows into tanks 2. For the first tank, the model component could look like this

```yaml
# First tank
- path: ./components/mod1.py 
  provides_results:
    - name: Q_out
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_next
    - name: Q_spill
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_spill
  consumes_input:
    - name: spill_fraction
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].spill_fraction
    - name: Q_in
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_in
    - name: Q_prev
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_prev
```

We see that, for a given production site and a given production line on that site, the first tank consumes input (`spill_fraction`, `Q_in` and `Q_prev`) from element zero in the list of tanks in the input data (`tanks[0@IDX_TANK]`). The component stores its results (`Q_next` and `Q_spill`) on element zero in the tanks list in the results data.

For the second tank, the model component could look like this

```yaml
# Second tank
- path: ./components/mod1.py 
  provides_results:
    - name: Q_out
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[1@IDX_TANK].Q_next
    - name: Q_spill
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[1@IDX_TANK].Q_spill
  consumes_input:
    - name: spill_fraction
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[1@IDX_TANK].spill_fraction
    - name: Q_in
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[1@IDX_TANK].Q_in
  consumes_results:
    # use outlet flow from previous tank (0)
    - name: Q_prev
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_next
```

The nodes `provides_results` and `consumes_input` look a lot like the equivalent nodes for tank 1 except that all index specifiers now refer to index 1 (`[1@IDX_TANK]`) instead of index 0. One other important difference is that the second tank consumes the outlet flow `Q_next` from the first tank. Notice that the path to the entrypoint function is the same for both tanks i.e it is the same code that does the actual calculation for each tank although the configuration differs. The third tank is quite similar to the second only all indices are bumped by one. The complete model definition can be seen in `examples/tanks/model1.yml` in the repository.

With the model in place we can explore some queries and responses.

SHOW EXAMPLE QUERY & RESPONSE HERE. MENTION THAT ALL THREE TANKS ARE EXECUTED. No explicit looping and bookkeeping only `Hubit` configuration. Allow developers of the tank model, which is quite simple here, to work isolated on the tank model and not the entire context in which it will be used.

While it is nice to refer to neighboring tanks it is tiresome if we have many tanks. Further, the model presented above would need to be changed when the number of tanks change which is not attractive. One use case for explicit indexing would be cells (compartments/elements) connected a more irregular fashion. In such cases the `Hubit` model can be constructed programmatically based on the mesh of cells (compartments/elements). In more regular cases such as this tank example it is better to leverage the two `Hubit` features _component contexts_ and _index offsets_.

## Component contexts and index offsets (`model2.yml`)
To address the issues identified in `model1.yml` we must resort to two features namely component contexts and index offset.

Component contexts limited to to one item => 0 dim and 1 dim problems. forward bla bla 