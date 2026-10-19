
This package contains the problem instances and solutions as described in the
paper:

Exact algorithms for electric vehicle-routing problems with time windows (2015),
submitted to Operations Research, G. Desaulniers, F. Errico, S. Irnich,
M. Schneider.

Here is a brief description of the package content.

-- Directory 'Instances':

   It contains the complete set of instances used in the paper. They are
   obtained as described in Section 5.1.
   However, the algorithm adopts an explicit representation of the time and
   time-equivalent battery consumption (see Section 3 of the paper).
   Furthermore, a precision of two decimal digit has been kept, with rounding
   up of the values. Because the implementation of the algorithm works with
   integer resource consumption, we used the following function to convert a
   generic decimal data x to integer values (see below for more details):

   transform(x, pr, eps)
   if (x*pr -floor(x) * pr) < eps)
     return floor(x*pr);
   else
    return ceil(x*pr);

   where the precision pr was set to 100 (second decimal digit precision) and
   eps=10^-9

   ** Travel Times:

   In the paper the speed is considered unitary, consequently it has no
   influence in the computation of the travel times.
   Supposing that the Euclidean distance between nodes i and j is d_ij, the
   corresponding travel time was obtained as follows:

   travelTime_ij = transform(d_ij, pr, eps);


   ** Time-equivalent Battery Consumption:

   In the paper the battery consumption rate is unitary with respect to the
   Euclidean distance between two points. Hence, by denoting b_ij the battery
   consumption when traveling between nodes i and j, b_ij=d_ij.
   To express the battery consumption in terms of time-equivalent battery
   consumption, we consider an inverse battery refueling rate (alpha) and
   obtain alpha*b_ij. Hence, the numerical values adopted in the algorithm are

   time-equivalent-battery-consumption_ij = transform(alpha*b_ij, pr, eps)

   Similarly, if B represents the value of the battery capacity:

   time-equivalent-battery-capacity = transform(alpha*B, pr, eps).

-- Directory 'Solutions'

   It contains four subdirectories, each corresponding to a given problem
   variant (MF MP SF SP). The solution files can be described as follows:

   The first three lines provide the total cost, the number of vehicles
   used, and the number of recharges performed.

   Then each route is described by its route number and its cost, followed by
   the sequence of locations visited. In this sequence,

   ** _D0o and _D0d indicate the depot at the beginning and the end of the
      route;
   ** _Cxn represents customer x;
   ** _Sxn represents recharging station x.

   The customers are numbered between 1 and 100, while the recharging stations
   are numbered between 0 and 20.

   Note that all costs are multiplied by 100.



