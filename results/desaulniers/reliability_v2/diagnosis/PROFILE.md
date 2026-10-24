# Whole-simulation diagnostic profiling

One already-seen c101_21_25 scenario; no reserved or new development parent.
cProfile perturbs timing. This is not latency certification or a representative speedup claim.
All profiled trajectories pass independent physical and information replay.

| Engine | Function | Calls | Own seconds | Cumulative seconds |
| --- | --- | ---: | ---: | ---: |
| MPC_COMPLETION | run | 1 | 0.009876 | 0.613003 |
| MPC_COMPLETION | construct_fleet_root | 18 | 0.000776 | 0.301666 |
| MPC_COMPLETION | transition | 8893 | 0.053761 | 0.223048 |
| MPC_COMPLETION | _decode | 30 | 0.000141 | 0.215637 |
| MPC_COMPLETION | build_route | 30 | 0.000495 | 0.209727 |
| MPC_COMPLETION | _build_route_original | 30 | 0.001668 | 0.208575 |
| MPC_COMPLETION | _decode_one_station | 10 | 0.010417 | 0.158906 |
| MPC_COMPLETION | predict | 3433 | 0.008289 | 0.133451 |
| MPC_COMPLETION | route_proposal | 545 | 0.001881 | 0.124993 |
| MPC_COMPLETION | _evaluate | 545 | 0.003440 | 0.122702 |
| MPC_COMPLETION | _predict | 2888 | 0.007712 | 0.100558 |
| MPC_COMPLETION | _score | 54 | 0.000216 | 0.065661 |
| MPC_MCTS | run | 1 | 0.011699 | 30.395721 |
| MPC_MCTS | optimize | 15 | 0.016835 | 29.929406 |
| MPC_MCTS | solve_fleet_mcts | 15 | 0.104878 | 29.876149 |
| MPC_MCTS | candidates | 724 | 0.089483 | 29.465277 |
| MPC_MCTS | change | 46092 | 0.350122 | 24.432428 |
| MPC_MCTS | _full_service_moves | 724 | 0.245072 | 21.574291 |
| MPC_MCTS | _decode | 71582 | 0.138890 | 20.232541 |
| MPC_MCTS | build_route | 4967 | 0.055482 | 19.469876 |
| MPC_MCTS | _build_route_original | 4937 | 0.187585 | 19.312942 |
| MPC_MCTS | keep | 35823 | 0.075064 | 17.813875 |
| MPC_MCTS | _decode_one_station | 752 | 1.053438 | 14.943457 |
| MPC_MCTS | transition | 529782 | 3.659034 | 13.579143 |
| MPC_ALNS | run | 1 | 0.015750 | 12.099770 |
| MPC_ALNS | optimize | 15 | 0.023362 | 11.567541 |
| MPC_ALNS | change | 7856 | 0.080448 | 11.330780 |
| MPC_ALNS | _repair | 900 | 0.003079 | 9.870907 |
| MPC_ALNS | _repair | 900 | 0.030956 | 9.867828 |
| MPC_ALNS | _decode | 7885 | 0.019099 | 9.493780 |
| MPC_ALNS | build_route | 1071 | 0.023894 | 9.230261 |
| MPC_ALNS | _build_route_original | 1001 | 0.065475 | 9.181267 |
| MPC_ALNS | _decode_one_station | 373 | 0.548803 | 7.325269 |
| MPC_ALNS | transition | 244802 | 1.730370 | 6.328277 |
| MPC_ALNS | add_goal | 90762 | 0.107945 | 1.943994 |
| MPC_ALNS | _score | 6419 | 0.019631 | 1.900076 |
| MPC_HGS | run | 1 | 0.028297 | 31.979827 |
| MPC_HGS | optimize | 19 | 0.006733 | 31.440620 |
| MPC_HGS | change | 8341 | 0.092541 | 30.656197 |
| MPC_HGS | _crossover | 275 | 0.037773 | 27.663962 |
| MPC_HGS | _decode | 11084 | 0.034264 | 25.825601 |
| MPC_HGS | build_route | 3992 | 0.077028 | 25.168617 |
| MPC_HGS | _build_route_original | 3847 | 0.223153 | 25.002297 |
| MPC_HGS | _decode_one_station | 1288 | 1.345319 | 18.675117 |
| MPC_HGS | transition | 669523 | 4.650567 | 16.857342 |
| MPC_HGS | add_goal | 232530 | 0.278128 | 4.953002 |
| MPC_HGS | _score | 5565 | 0.021857 | 4.839435 |
| MPC_HGS | evaluate | 5565 | 0.162885 | 4.801609 |
| MPC_ACS | run | 1 | 0.026307 | 12.444451 |
| MPC_ACS | optimize | 17 | 0.088375 | 11.933975 |
| MPC_ACS | change | 12077 | 0.126308 | 11.713196 |
| MPC_ACS | _decode | 12202 | 0.028451 | 6.162956 |
| MPC_ACS | build_route | 1115 | 0.019489 | 5.873952 |
| MPC_ACS | _build_route_original | 982 | 0.055269 | 5.826013 |
| MPC_ACS | _score | 10688 | 0.032987 | 5.503135 |
| MPC_ACS | evaluate | 10688 | 0.254935 | 5.445596 |
| MPC_ACS | _decode_one_station | 224 | 0.314756 | 4.415843 |
| MPC_ACS | transition | 155858 | 1.125775 | 4.091638 |
| MPC_ACS | _criticality | 11533 | 0.161174 | 3.925805 |
| MPC_ACS | screened_options | 37817 | 0.424363 | 3.477528 |
