# Cascading tanks

This example shows how to set up models where one compartment (cell, element) consumes the result of a neighboring compartment (cell, element). In the example, a liquid flows from one tank to the next in a cascading fashion. The example encompass two similar tanks models `model1` and `model2` that illustrate explicit linking of the tanks and a more generic linking pattern, respectively.

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
            ║  Q_out,1  ┌─────║──┐
          ╔═╩═══════════|═╗   ˅  | 
Q_spill,1 ║             | ˅      |
          ˅             |~~~~~~~~|
                        | Tank 2 |            ║ Q_in,3
                        └───╥────┘            ║
                            ║  Q_out,2  ┌─────║──┐
                Q_spill,2 ╔═╩═══════════|═╗   ˅  | 
                          ˅             | ˅      |                                         
                                        |~~~~~~~~|                                         
                                        | Tank 3 |                                         
                                        └──╥─────┘
                                           ║  
                               Q_spill,3 ╔═╩════╗                                     
                                         ˅      ˅ Q_out,3
                                                                                 
```

Describe the model with words here. Could be after Q_out,3 i.e. the final product stream from this process.

The input could look like this 

```yaml
vol_inlet_flow: 20.
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

## Explicit indexing (`model1.yml`)

```yaml
# First tank
- path: ./components/mod1.py 
  provides_results:
    - name: Q_out
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_out
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

Describe what is going on

```yaml
# Second tank
- path: ./components/mod1.py 
  provides_results:
    - name: Q_out
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[1@IDX_TANK].Q_out
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
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_out
```

Describe what is going on and differences wrt component 1...
Notice that the path to the entrypoint function is the same for both tanks i.e it is the same code that does the actual calculation for each tank although the configuration differs.


The third tank is quite similar to the second only all indices are bumped by one. 

SHOW EXAMPLE QUERY & RESPONSE HERE. MENTION THAT ALL THREE TANKS ARE EXECUTED.

While it is nice to refer to neighboring tanks it is tiresome if we have many tanks. 
Further, the model presented above would need to be changed when the number of tanks change which is not attractive.

## Component contexts and index offset (`model2.yml`)
To address the issues identified in `model1.yml` we must resort to two features namely component contexts and index offset.
