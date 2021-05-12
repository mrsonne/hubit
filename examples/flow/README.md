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

For each tank we can "precompute"

A*c \sqrt(2*g)

```
                    ║                  ║
                    ║  Q_in,1          ║ Q_in,2 
                    ˅                  ║
                 │          │          ║   
Q_overflow,1  ╔══│    h_1   │          ║
              ║  │~~~~~~~~~~│ Q_out,1  ║
              ˅  │  Tank 1  │══════╗   ║                
                 └──────────┘      ║   ║ 
                                   ˅   ˅
                                 |       | 
             Q_overflow,2  ╔═════|  h_2  |
                           ║     |~~~~~~~|
                           ˅     |       |  Q_out,2
                                 |       |════╗
                                 |       |    ║
                                 |Tank 2 |    ˅
                                 └───────┘
```