## Advection example?!?

constant flow in x v_x
du/dt + v_x*du/dx = 0

backward Euler in space and time

( u(n, k) - u(n-1, k) ) / delta t + v*( u(n, k) - u(n, k-1) ) / delta x = 0

u(n, k) - u(n-1, k)   + v *( u(n, k) - u(n, k-1) )* delta t / delta x = 0

u(n, k)*(1 + v* delta t / delta x) = u(n-1, k) +  v *u(n, k-1)* delta t / delta x

u(n, k) = (u(n-1, k) +  v *u(n, k-1)* delta t / delta x) / (1 + v* delta t / delta x)

beta = v * delta t / delta x

u(n, k) = (u(n-1, k) +  beta * u(n, k-1) ) / (1 + beta)
