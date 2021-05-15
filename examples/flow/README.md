# Cascading tanks

Birs Steward and Lightfoot probably has this example as well
https://www.lmnoeng.com/Tank/TankTime.php

*N* cascading tanks with overflow.

Tank parameters

- Inlet flows, Q_in
- Outlet flows, Q_out
- Outlet levels, h_o
- Water level, h_w
- Tank diameter, d
- Discharge coefficient, C  
- Orifice area, A

With no accumulation and no chemical reactions the mass balance for each tank reads

```math
IN = OUT
```

The volumetric inlet flow for tank <i>i</i> <i>Q</i><sub>in,<i>i</i></sub> is specified and constant for all tanks. The volumetric outlet flow for tank <i>i</i> <i>Q</i><sub>out,<i>i</i></sub> depends on the water level <i>h</i><sub>w,<i>i</i></sub> and various tank design parameters namely the tank diameter <i>d</i>, the discharge coefficient <i>C</i> and the orifice area <i>A</i>. 

Out flow given by 

XXXXX

Further, each tank is fitted with an overflow outlet at height <i>h</i><sub>o,<i>i</i></sub>. This assures that the water level cannot rise higher than this level. Thus, in the case where the overflow outlet is reached, the water level is fixed and known, but the the overflow volumetric flow is unknown. In the case where the overflow outlet is not reached, the water is unknown and the overflow volumetric flow is zero.

---------------------


```
                                       
                    ║  Q_in,1          ║ Q_in,2 
                 ┌──║───────┐          ║ 
                 │  ˅       │          ║   
       h_o,1  ╔══│  h_w,1   │          ║
              ║  │~~~~~~~~~~│ Q_out,1  ║
              ˅  │  Tank 1  │══════╗   ║                
                 └──────────┘      ║   ║ 
                                 ┌─║───║─┐
                                 | ˅   ˅ | 
                    h_o,2  ╔═════| h_w,2 |
                           ║     |~~~~~~~|
                           ˅     |       |
                                 |       |  Q_out,2
                                 |Tank 2 |════╗
                                 └───────┘    ˅
```

The mass balance for the first tank can be solved without any data from the remaining tanks. With the outflow from the first tank the mass balance for the second tank can be solved. Thus, to get the outflow from the N'th tank the mass balances for the N-1 preceding tanks must be solved sequentially.

```yaml
tanks:
    - orifice_area: 0.2
      discharge_coef: 0.9
      tank_diameter: 0.8
      overflow_height: 0.8
    - orifice_area: 0.4
      discharge_coef: 0.4
      tank_diameter: 0.4
      overflow_height: 0.6
```
or maybe

```yaml
tanks:
    - type: A
    - type: B
```

--------------------
For each tank we can "precompute"

A*c \sqrt(2*g)

# Ideas
* Add components and chemical reactions
