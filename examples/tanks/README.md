# Connected tanks

This example shows how to set up models where one compartment (cell, element) consumes a result of an upstream compartment (cell, element). In the example, a liquid flows from one tank to the next and encompass two similar tanks models `model_1.yml` and `model_2.yml`. The former illustrates explicit linking of the tanks which is useful for unstructured problems while the latter shows a linking pattern useful for structured problems. Notice that all the model components presented below share the same entrypoint function even though the configurations are quite different. This highlights the powerful separation of implementation and configuration in `Hubit`.

## Unstructured compartments - explicit indexing (`model_1.yml`)
In this example liquid flows into tank 1 with rate `Q_in,1`. In tank 1 some process takes place and the yield rate is `Q_yield,1`. Tank 2 is similar to tank 1 only the yield rate is `Q_yield,2`. The two yield streams are mixed in tank 3 where another process takes place with yield `Q_yield,3`. The entire process is schematically illustrated below

<!-- Fixes width ssue for some characters in ascii drawing -->
<style>
code {
  font-family: "var(--md-code-font-family,_)",SFMono-Regular,Consolas,Menlo,monospace;
}
</style>

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


For simplicity, the yields are determined from a predefined yield fraction parameter i.e. `Q_yield = yield_fraction * Q_in`. 

Imagine the three tanks represent a production line on a production site. If we consider only one production site with only one production line, the input for the model could look like this

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

The fields `prod_sites[0].prod_lines[0].tanks[0:2].Q_transfer: 0` and `prod_sites[0].prod_lines[0].tanks[2].Q_in: 0` are boundary conditions that have been added to allow the implementation of the calculation code to be the same for all tanks. In this example we will use explicit indexing to direct the yield from tank 1 `Q_yield,1` into tank 3. For tank 1, the model component could look like this

```yaml
# Tank 1
- path: ./components/mod1.py 
  provides_results:
    - name: Q_yield
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_yield
  consumes_input:
    - name: yield_fraction
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].yield_fraction
    - name: Q_in
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_in
    - name: Q_transfer
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_transfer
```

We see that, for a given production site (`IDX_SITE`) and a given production line (`IDX_LINE`) on that site, tank 1 consumes input (`yield_fraction`, `Q_in` and `Q_transfer`) from element zero in the list of tanks in the input data (`tanks[0@IDX_TANK]`). Similarly, the resulting yield (`Q_yield`) is stored on element zero in the tanks list in the results data.

For tank 2, the model component is similar to tank 1 except all index specifiers point to tank index 1 (`1@IDX_TANK`) and is omitted here. For tank 3 the model component could look like this

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
    # use outlet flow from tank 0
    - name: Q_transfer_1
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_yield
    # use outlet flow from tank 1
    - name: Q_transfer_2
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[1@IDX_TANK].Q_yield
```

The nodes `provides_results` and `consumes_input` look a lot like the equivalent nodes for tanks 1 and 2 except that all index specifiers now refer to tank index 2 (`2@IDX_TANK`). One other important difference is that tank 3 consumes the outlet flows `Q_yield` from tanks 1 and 2. The complete model definition can be seen in `examples/tanks/model_1.yml` in the repository.

With the model in place we can explore some queries and responses. The final yield (from tank 3) from the first production line at the first production site can be obtained from the query.

```
['prod_sites[0].prod_lines[0].tanks[2].Q_yield']
```

and the response is

```
{'prod_sites[0].prod_lines[0].tanks[2].Q_yield': 4.0}
```

From `examples/tanks/input.yml` we can reconstruct how the result 4.0 was calculated

```
Q_yield,3 = 
yield_fraction_3 * (yield_fraction_1 * Q_in,1 + yield_fraction_2 * Q_in,2) = 
0.25 * (0.5 * 20 + 0.6 * 10) = 
4.0
```

The query spawns three workers i.e. one for each tank. Notice that no explicit looping over tanks is required once the subscriptions are configured in the `Hubit` model. This allow the developers of the tank model to work isolated on the tank model with less attention to the context in which it will be used.

If we query the yield from tank 3 from all production lines at all production sites using

```
['prod_sites[:].prod_lines[:].tanks[2].Q_yield']
```

we again get the result 4.0 back (since there is actually only one production site and one production line), but the result is now a double nested list.

```
{'prod_sites[:].prod_lines[:].tanks[2].Q_yield': [[4.0]]}
```

The outer list represents the production sites while the inner list represent the production lines.

Explicit indexing provides nice flexibility, but it may quickly become tiresome to configure. Further, the model presented above would need to be changed when the number of tanks changes. Of course, this could be done programmatically based on the tank connectivities (mesh of cells/compartments/elements) generated elsewhere.

### Protip 1 (`model_1a.yml`)

Using _index scope_ the model components for tanks 1 and 2 can be refactored to one component with no explicit indexes in the binding paths

```yaml
- path: ./components/mod1.py 
  index_scope:
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

In this case the scope `index_scope.IDX_TANK: "0:2"` assures that `IDX_TANK` equals 0 or 1 in all instances of this component. This version of the model is shown in `examples/tanks/model_1a.yml`.

### Protip 2 (`model_1b.yml`)

Using _index scope_ tank 3 can alternatively be configured as 

```yaml
- path: ./components/mod1.py 
  index scope:
    IDX_TANK: 2
  provides_results:
    - name: Q_yield
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[IDX_TANK].Q_yield
  consumes_input:
    - name: yield_fraction
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[IDX_TANK].yield_fraction
    - name: Q_in
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[IDX_TANK].Q_in
  consumes_results:
    # use outlet flow from previous tank 0
    - name: Q_transfer_1
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[0@IDX_TANK].Q_yield
    # use outlet flow from previous tank 1
    - name: Q_transfer_2
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[1@IDX_TANK].Q_yield
```

In this case the index scope `index_scope.IDX_TANK: 2` assures that the identifier `IDX_TANK` equals 2 in all instances of this component. The explicit indices in `consumes_results` i.e. `0@IDX_TANK` and `1@IDX_TANK` are still used as is. This version of the model is shown in `examples/tanks/model_1b.yml`.

## Structured compartments - component scope and index offsets (`model2.yml`)
In structured cases, such as the tank example schematically illustrated below, `Hubit`'s _index scope_ and _index offset_ come in handy.

```
           ║  Q_in,1                          
           ║              
        ┌──║───────┐           
        │  ˅       │             
        │          │          
        │~~~~~~~~~~│          
        │  Tank 1  │            ║ Q_in,2               
        └───╥──────┘            ║ 
            ║   Q_yield,1 ┌─────║──┐
          ╔═╩═════════════|═╗   ˅  | 
Q_spill,1 ║               | ˅      |
          ˅               |~~~~~~~~|
                          | Tank 2 |              ║ Q_in,3
                          └───╥────┘              ║
                              ║   Q_yield,2 ┌─────║──┐
                  Q_spill,2 ╔═╩═════════════|═╗   ˅  | 
                            ║               | ˅      |                            
                            ˅               |~~~~~~~~|                               
                                            | Tank 3 |
                                            └──╥─────┘
                                               ║  
                                   Q_spill,3 ╔═╩════╗                                     
                                             ║      ˅ Q_yield,3
                                             ˅      
                                                                                 
```

The input is the same as in the previous section, but the component for the first tank may be defined as shown below

```yaml
- path: ./components/mod1.py 
  index_scope: 
    IDX_TANK: 0
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

At first sight the component looks as if its binding paths can refer to any combination of `IDX_SITE`, `IDX_LINE` and `IDX_TANK`. The `index_scope` filed, however, assures that `IDX_TANK` is 0 in all instances of this component. The second component is shown below

```yaml
- path: ./components/mod1.py
  index_scope: 
    IDX_TANK: "1:"
  provides_results:
    - name: Q_yield
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[IDX_TANK].Q_yield
  consumes_input:
    - name: yield_fraction
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[IDX_TANK].yield_fraction
    - name: Q_in
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[IDX_TANK].Q_in
  consumes_results:
    - name: Q_transfer
      path: prod_sites[IDX_SITE].prod_lines[IDX_LINE].tanks[IDX_TANK-1].Q_yield
```

There are two important details. First, the `index_scope` field limits the scope to tanks after the first tank in all instances of this component. Second, the component consumes the yield rate `Q_yield` from the previous tank pointing to the index identifier `IDX_TANK` offset by 1 i.e `IDX_TANK-1`. To avoid going out of bounds it is important to exclude the first tank from the index scope as explained above.