| instance | solver | feature | our_model | external_model | source_exact | instance_equivalent | evidence |
|---|---|---|---|---|---|---|---|
| c101_21 | RoutingBlocks | coordinates/distances | Euclidean floating-point | Euclidean floating-point | True | True | official examples/evrptw source at pinned SHA |
| c101_21 | RoutingBlocks | travel-time model | distance/1.0 | distance*1.0 in example | True | True | official examples/evrptw source at pinned SHA |
| c101_21 | RoutingBlocks | customer service times | Schneider service | Schneider service | True | True | official examples/evrptw source at pinned SHA |
| c101_21 | RoutingBlocks | demands | Schneider demands | Schneider demands | True | True | official examples/evrptw source at pinned SHA |
| c101_21 | RoutingBlocks | vehicle capacity | 200.0 | Schneider C | True | True | official examples/evrptw source at pinned SHA |
| c101_21 | RoutingBlocks | customer time windows | hard ready/due | hard ready/due | True | True | official examples/evrptw source at pinned SHA |
| c101_21 | RoutingBlocks | depot horizon | hard depot due | depot vertex due | True | True | official examples/evrptw source at pinned SHA |
| c101_21 | RoutingBlocks | battery capacity | 79.69 | Q converted to charge-time resource | True | True | official examples/evrptw source at pinned SHA |
| c101_21 | RoutingBlocks | linear distance-based energy consumption | distance*1.0 | r*distance/g in charge-time units | True | True | official examples/evrptw source at pinned SHA |
| c101_21 | RoutingBlocks | charging rate | energy*3.39 | g parameter converted to energy/time | True | True | official examples/evrptw source at pinned SHA |
| c101_21 | RoutingBlocks | partial recharge | continuous partial | ADPTW partial recharge | True | True | official examples/evrptw source at pinned SHA |
| c101_21 | RoutingBlocks | multiple station visits | repeat station allowed | intermediate station visits | True | True | official examples/evrptw source at pinned SHA |
| c101_21 | RoutingBlocks | same K_ref fleet upper bound | 13 | example defaults to customer count; adapter must override | n/a | True | official examples/evrptw source at pinned SHA |
| c101_21 | RoutingBlocks | safe depot return | every activated EV returns | depot-ended routes | True | True | official examples/evrptw source at pinned SHA |
| c101_21 | pyevrp 0.2.1 | coordinates/distances | Euclidean floating-point | Model uses Euclidean | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c101_21 | pyevrp 0.2.1 | travel-time model | distance/1.0 | vehicle speed can be set on Model | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c101_21 | pyevrp 0.2.1 | customer service times | Schneider service | Model supports service time | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c101_21 | pyevrp 0.2.1 | demands | Schneider demands | Model supports demand | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c101_21 | pyevrp 0.2.1 | vehicle capacity | 200.0 | Model capacity can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c101_21 | pyevrp 0.2.1 | customer time windows | hard ready/due | Model supports windows | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c101_21 | pyevrp 0.2.1 | depot horizon | hard depot due | Model depot window; bundled validator checks arrival | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c101_21 | pyevrp 0.2.1 | battery capacity | 79.69 | Model battery capacity can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c101_21 | pyevrp 0.2.1 | linear distance-based energy consumption | distance*1.0 | Model consumption rate can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c101_21 | pyevrp 0.2.1 | charging rate | energy*3.39 | station rate can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c101_21 | pyevrp 0.2.1 | partial recharge | continuous partial | bundled GreedyInsertion charges to full | False | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c101_21 | pyevrp 0.2.1 | multiple station visits | repeat station allowed | not established for bundled greedy | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c101_21 | pyevrp 0.2.1 | same K_ref fleet upper bound | 13 | Model num_available; bundled greedy does not enforce | False | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c101_21 | pyevrp 0.2.1 | safe depot return | every activated EV returns | greedy appends depot; validator checks | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c201_21 | RoutingBlocks | coordinates/distances | Euclidean floating-point | Euclidean floating-point | True | True | official examples/evrptw source at pinned SHA |
| c201_21 | RoutingBlocks | travel-time model | distance/1.0 | distance*1.0 in example | True | True | official examples/evrptw source at pinned SHA |
| c201_21 | RoutingBlocks | customer service times | Schneider service | Schneider service | True | True | official examples/evrptw source at pinned SHA |
| c201_21 | RoutingBlocks | demands | Schneider demands | Schneider demands | True | True | official examples/evrptw source at pinned SHA |
| c201_21 | RoutingBlocks | vehicle capacity | 700.0 | Schneider C | True | True | official examples/evrptw source at pinned SHA |
| c201_21 | RoutingBlocks | customer time windows | hard ready/due | hard ready/due | True | True | official examples/evrptw source at pinned SHA |
| c201_21 | RoutingBlocks | depot horizon | hard depot due | depot vertex due | True | True | official examples/evrptw source at pinned SHA |
| c201_21 | RoutingBlocks | battery capacity | 118.31 | Q converted to charge-time resource | True | True | official examples/evrptw source at pinned SHA |
| c201_21 | RoutingBlocks | linear distance-based energy consumption | distance*1.0 | r*distance/g in charge-time units | True | True | official examples/evrptw source at pinned SHA |
| c201_21 | RoutingBlocks | charging rate | energy*2.28 | g parameter converted to energy/time | True | True | official examples/evrptw source at pinned SHA |
| c201_21 | RoutingBlocks | partial recharge | continuous partial | ADPTW partial recharge | True | True | official examples/evrptw source at pinned SHA |
| c201_21 | RoutingBlocks | multiple station visits | repeat station allowed | intermediate station visits | True | True | official examples/evrptw source at pinned SHA |
| c201_21 | RoutingBlocks | same K_ref fleet upper bound | 5 | example defaults to customer count; adapter must override | n/a | True | official examples/evrptw source at pinned SHA |
| c201_21 | RoutingBlocks | safe depot return | every activated EV returns | depot-ended routes | True | True | official examples/evrptw source at pinned SHA |
| c201_21 | pyevrp 0.2.1 | coordinates/distances | Euclidean floating-point | Model uses Euclidean | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c201_21 | pyevrp 0.2.1 | travel-time model | distance/1.0 | vehicle speed can be set on Model | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c201_21 | pyevrp 0.2.1 | customer service times | Schneider service | Model supports service time | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c201_21 | pyevrp 0.2.1 | demands | Schneider demands | Model supports demand | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c201_21 | pyevrp 0.2.1 | vehicle capacity | 700.0 | Model capacity can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c201_21 | pyevrp 0.2.1 | customer time windows | hard ready/due | Model supports windows | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c201_21 | pyevrp 0.2.1 | depot horizon | hard depot due | Model depot window; bundled validator checks arrival | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c201_21 | pyevrp 0.2.1 | battery capacity | 118.31 | Model battery capacity can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c201_21 | pyevrp 0.2.1 | linear distance-based energy consumption | distance*1.0 | Model consumption rate can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c201_21 | pyevrp 0.2.1 | charging rate | energy*2.28 | station rate can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c201_21 | pyevrp 0.2.1 | partial recharge | continuous partial | bundled GreedyInsertion charges to full | False | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c201_21 | pyevrp 0.2.1 | multiple station visits | repeat station allowed | not established for bundled greedy | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c201_21 | pyevrp 0.2.1 | same K_ref fleet upper bound | 5 | Model num_available; bundled greedy does not enforce | False | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| c201_21 | pyevrp 0.2.1 | safe depot return | every activated EV returns | greedy appends depot; validator checks | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r101_21 | RoutingBlocks | coordinates/distances | Euclidean floating-point | Euclidean floating-point | True | True | official examples/evrptw source at pinned SHA |
| r101_21 | RoutingBlocks | travel-time model | distance/1.0 | distance*1.0 in example | True | True | official examples/evrptw source at pinned SHA |
| r101_21 | RoutingBlocks | customer service times | Schneider service | Schneider service | True | True | official examples/evrptw source at pinned SHA |
| r101_21 | RoutingBlocks | demands | Schneider demands | Schneider demands | True | True | official examples/evrptw source at pinned SHA |
| r101_21 | RoutingBlocks | vehicle capacity | 200.0 | Schneider C | True | True | official examples/evrptw source at pinned SHA |
| r101_21 | RoutingBlocks | customer time windows | hard ready/due | hard ready/due | True | True | official examples/evrptw source at pinned SHA |
| r101_21 | RoutingBlocks | depot horizon | hard depot due | depot vertex due | True | True | official examples/evrptw source at pinned SHA |
| r101_21 | RoutingBlocks | battery capacity | 62.14 | Q converted to charge-time resource | True | True | official examples/evrptw source at pinned SHA |
| r101_21 | RoutingBlocks | linear distance-based energy consumption | distance*1.0 | r*distance/g in charge-time units | True | True | official examples/evrptw source at pinned SHA |
| r101_21 | RoutingBlocks | charging rate | energy*0.48 | g parameter converted to energy/time | True | True | official examples/evrptw source at pinned SHA |
| r101_21 | RoutingBlocks | partial recharge | continuous partial | ADPTW partial recharge | True | True | official examples/evrptw source at pinned SHA |
| r101_21 | RoutingBlocks | multiple station visits | repeat station allowed | intermediate station visits | True | True | official examples/evrptw source at pinned SHA |
| r101_21 | RoutingBlocks | same K_ref fleet upper bound | 20 | example defaults to customer count; adapter must override | n/a | True | official examples/evrptw source at pinned SHA |
| r101_21 | RoutingBlocks | safe depot return | every activated EV returns | depot-ended routes | True | True | official examples/evrptw source at pinned SHA |
| r101_21 | pyevrp 0.2.1 | coordinates/distances | Euclidean floating-point | Model uses Euclidean | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r101_21 | pyevrp 0.2.1 | travel-time model | distance/1.0 | vehicle speed can be set on Model | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r101_21 | pyevrp 0.2.1 | customer service times | Schneider service | Model supports service time | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r101_21 | pyevrp 0.2.1 | demands | Schneider demands | Model supports demand | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r101_21 | pyevrp 0.2.1 | vehicle capacity | 200.0 | Model capacity can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r101_21 | pyevrp 0.2.1 | customer time windows | hard ready/due | Model supports windows | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r101_21 | pyevrp 0.2.1 | depot horizon | hard depot due | Model depot window; bundled validator checks arrival | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r101_21 | pyevrp 0.2.1 | battery capacity | 62.14 | Model battery capacity can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r101_21 | pyevrp 0.2.1 | linear distance-based energy consumption | distance*1.0 | Model consumption rate can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r101_21 | pyevrp 0.2.1 | charging rate | energy*0.48 | station rate can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r101_21 | pyevrp 0.2.1 | partial recharge | continuous partial | bundled GreedyInsertion charges to full | False | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r101_21 | pyevrp 0.2.1 | multiple station visits | repeat station allowed | not established for bundled greedy | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r101_21 | pyevrp 0.2.1 | same K_ref fleet upper bound | 20 | Model num_available; bundled greedy does not enforce | False | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r101_21 | pyevrp 0.2.1 | safe depot return | every activated EV returns | greedy appends depot; validator checks | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r201_21 | RoutingBlocks | coordinates/distances | Euclidean floating-point | Euclidean floating-point | True | True | official examples/evrptw source at pinned SHA |
| r201_21 | RoutingBlocks | travel-time model | distance/1.0 | distance*1.0 in example | True | True | official examples/evrptw source at pinned SHA |
| r201_21 | RoutingBlocks | customer service times | Schneider service | Schneider service | True | True | official examples/evrptw source at pinned SHA |
| r201_21 | RoutingBlocks | demands | Schneider demands | Schneider demands | True | True | official examples/evrptw source at pinned SHA |
| r201_21 | RoutingBlocks | vehicle capacity | 1000.0 | Schneider C | True | True | official examples/evrptw source at pinned SHA |
| r201_21 | RoutingBlocks | customer time windows | hard ready/due | hard ready/due | True | True | official examples/evrptw source at pinned SHA |
| r201_21 | RoutingBlocks | depot horizon | hard depot due | depot vertex due | True | True | official examples/evrptw source at pinned SHA |
| r201_21 | RoutingBlocks | battery capacity | 187.86 | Q converted to charge-time resource | True | True | official examples/evrptw source at pinned SHA |
| r201_21 | RoutingBlocks | linear distance-based energy consumption | distance*1.0 | r*distance/g in charge-time units | True | True | official examples/evrptw source at pinned SHA |
| r201_21 | RoutingBlocks | charging rate | energy*0.16 | g parameter converted to energy/time | True | True | official examples/evrptw source at pinned SHA |
| r201_21 | RoutingBlocks | partial recharge | continuous partial | ADPTW partial recharge | True | True | official examples/evrptw source at pinned SHA |
| r201_21 | RoutingBlocks | multiple station visits | repeat station allowed | intermediate station visits | True | True | official examples/evrptw source at pinned SHA |
| r201_21 | RoutingBlocks | same K_ref fleet upper bound | 4 | example defaults to customer count; adapter must override | n/a | True | official examples/evrptw source at pinned SHA |
| r201_21 | RoutingBlocks | safe depot return | every activated EV returns | depot-ended routes | True | True | official examples/evrptw source at pinned SHA |
| r201_21 | pyevrp 0.2.1 | coordinates/distances | Euclidean floating-point | Model uses Euclidean | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r201_21 | pyevrp 0.2.1 | travel-time model | distance/1.0 | vehicle speed can be set on Model | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r201_21 | pyevrp 0.2.1 | customer service times | Schneider service | Model supports service time | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r201_21 | pyevrp 0.2.1 | demands | Schneider demands | Model supports demand | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r201_21 | pyevrp 0.2.1 | vehicle capacity | 1000.0 | Model capacity can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r201_21 | pyevrp 0.2.1 | customer time windows | hard ready/due | Model supports windows | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r201_21 | pyevrp 0.2.1 | depot horizon | hard depot due | Model depot window; bundled validator checks arrival | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r201_21 | pyevrp 0.2.1 | battery capacity | 187.86 | Model battery capacity can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r201_21 | pyevrp 0.2.1 | linear distance-based energy consumption | distance*1.0 | Model consumption rate can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r201_21 | pyevrp 0.2.1 | charging rate | energy*0.16 | station rate can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r201_21 | pyevrp 0.2.1 | partial recharge | continuous partial | bundled GreedyInsertion charges to full | False | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r201_21 | pyevrp 0.2.1 | multiple station visits | repeat station allowed | not established for bundled greedy | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r201_21 | pyevrp 0.2.1 | same K_ref fleet upper bound | 4 | Model num_available; bundled greedy does not enforce | False | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| r201_21 | pyevrp 0.2.1 | safe depot return | every activated EV returns | greedy appends depot; validator checks | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc101_21 | RoutingBlocks | coordinates/distances | Euclidean floating-point | Euclidean floating-point | True | True | official examples/evrptw source at pinned SHA |
| rc101_21 | RoutingBlocks | travel-time model | distance/1.0 | distance*1.0 in example | True | True | official examples/evrptw source at pinned SHA |
| rc101_21 | RoutingBlocks | customer service times | Schneider service | Schneider service | True | True | official examples/evrptw source at pinned SHA |
| rc101_21 | RoutingBlocks | demands | Schneider demands | Schneider demands | True | True | official examples/evrptw source at pinned SHA |
| rc101_21 | RoutingBlocks | vehicle capacity | 200.0 | Schneider C | True | True | official examples/evrptw source at pinned SHA |
| rc101_21 | RoutingBlocks | customer time windows | hard ready/due | hard ready/due | True | True | official examples/evrptw source at pinned SHA |
| rc101_21 | RoutingBlocks | depot horizon | hard depot due | depot vertex due | True | True | official examples/evrptw source at pinned SHA |
| rc101_21 | RoutingBlocks | battery capacity | 79.69 | Q converted to charge-time resource | True | True | official examples/evrptw source at pinned SHA |
| rc101_21 | RoutingBlocks | linear distance-based energy consumption | distance*1.0 | r*distance/g in charge-time units | True | True | official examples/evrptw source at pinned SHA |
| rc101_21 | RoutingBlocks | charging rate | energy*0.38 | g parameter converted to energy/time | True | True | official examples/evrptw source at pinned SHA |
| rc101_21 | RoutingBlocks | partial recharge | continuous partial | ADPTW partial recharge | True | True | official examples/evrptw source at pinned SHA |
| rc101_21 | RoutingBlocks | multiple station visits | repeat station allowed | intermediate station visits | True | True | official examples/evrptw source at pinned SHA |
| rc101_21 | RoutingBlocks | same K_ref fleet upper bound | 21 | example defaults to customer count; adapter must override | n/a | True | official examples/evrptw source at pinned SHA |
| rc101_21 | RoutingBlocks | safe depot return | every activated EV returns | depot-ended routes | True | True | official examples/evrptw source at pinned SHA |
| rc101_21 | pyevrp 0.2.1 | coordinates/distances | Euclidean floating-point | Model uses Euclidean | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc101_21 | pyevrp 0.2.1 | travel-time model | distance/1.0 | vehicle speed can be set on Model | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc101_21 | pyevrp 0.2.1 | customer service times | Schneider service | Model supports service time | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc101_21 | pyevrp 0.2.1 | demands | Schneider demands | Model supports demand | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc101_21 | pyevrp 0.2.1 | vehicle capacity | 200.0 | Model capacity can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc101_21 | pyevrp 0.2.1 | customer time windows | hard ready/due | Model supports windows | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc101_21 | pyevrp 0.2.1 | depot horizon | hard depot due | Model depot window; bundled validator checks arrival | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc101_21 | pyevrp 0.2.1 | battery capacity | 79.69 | Model battery capacity can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc101_21 | pyevrp 0.2.1 | linear distance-based energy consumption | distance*1.0 | Model consumption rate can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc101_21 | pyevrp 0.2.1 | charging rate | energy*0.38 | station rate can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc101_21 | pyevrp 0.2.1 | partial recharge | continuous partial | bundled GreedyInsertion charges to full | False | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc101_21 | pyevrp 0.2.1 | multiple station visits | repeat station allowed | not established for bundled greedy | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc101_21 | pyevrp 0.2.1 | same K_ref fleet upper bound | 21 | Model num_available; bundled greedy does not enforce | False | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc101_21 | pyevrp 0.2.1 | safe depot return | every activated EV returns | greedy appends depot; validator checks | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc201_21 | RoutingBlocks | coordinates/distances | Euclidean floating-point | Euclidean floating-point | True | True | official examples/evrptw source at pinned SHA |
| rc201_21 | RoutingBlocks | travel-time model | distance/1.0 | distance*1.0 in example | True | True | official examples/evrptw source at pinned SHA |
| rc201_21 | RoutingBlocks | customer service times | Schneider service | Schneider service | True | True | official examples/evrptw source at pinned SHA |
| rc201_21 | RoutingBlocks | demands | Schneider demands | Schneider demands | True | True | official examples/evrptw source at pinned SHA |
| rc201_21 | RoutingBlocks | vehicle capacity | 1000.0 | Schneider C | True | True | official examples/evrptw source at pinned SHA |
| rc201_21 | RoutingBlocks | customer time windows | hard ready/due | hard ready/due | True | True | official examples/evrptw source at pinned SHA |
| rc201_21 | RoutingBlocks | depot horizon | hard depot due | depot vertex due | True | True | official examples/evrptw source at pinned SHA |
| rc201_21 | RoutingBlocks | battery capacity | 211.04 | Q converted to charge-time resource | True | True | official examples/evrptw source at pinned SHA |
| rc201_21 | RoutingBlocks | linear distance-based energy consumption | distance*1.0 | r*distance/g in charge-time units | True | True | official examples/evrptw source at pinned SHA |
| rc201_21 | RoutingBlocks | charging rate | energy*0.14 | g parameter converted to energy/time | True | True | official examples/evrptw source at pinned SHA |
| rc201_21 | RoutingBlocks | partial recharge | continuous partial | ADPTW partial recharge | True | True | official examples/evrptw source at pinned SHA |
| rc201_21 | RoutingBlocks | multiple station visits | repeat station allowed | intermediate station visits | True | True | official examples/evrptw source at pinned SHA |
| rc201_21 | RoutingBlocks | same K_ref fleet upper bound | 5 | example defaults to customer count; adapter must override | n/a | True | official examples/evrptw source at pinned SHA |
| rc201_21 | RoutingBlocks | safe depot return | every activated EV returns | depot-ended routes | True | True | official examples/evrptw source at pinned SHA |
| rc201_21 | pyevrp 0.2.1 | coordinates/distances | Euclidean floating-point | Model uses Euclidean | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc201_21 | pyevrp 0.2.1 | travel-time model | distance/1.0 | vehicle speed can be set on Model | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc201_21 | pyevrp 0.2.1 | customer service times | Schneider service | Model supports service time | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc201_21 | pyevrp 0.2.1 | demands | Schneider demands | Model supports demand | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc201_21 | pyevrp 0.2.1 | vehicle capacity | 1000.0 | Model capacity can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc201_21 | pyevrp 0.2.1 | customer time windows | hard ready/due | Model supports windows | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc201_21 | pyevrp 0.2.1 | depot horizon | hard depot due | Model depot window; bundled validator checks arrival | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc201_21 | pyevrp 0.2.1 | battery capacity | 211.04 | Model battery capacity can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc201_21 | pyevrp 0.2.1 | linear distance-based energy consumption | distance*1.0 | Model consumption rate can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc201_21 | pyevrp 0.2.1 | charging rate | energy*0.14 | station rate can be set | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc201_21 | pyevrp 0.2.1 | partial recharge | continuous partial | bundled GreedyInsertion charges to full | False | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc201_21 | pyevrp 0.2.1 | multiple station visits | repeat station allowed | not established for bundled greedy | n/a | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc201_21 | pyevrp 0.2.1 | same K_ref fleet upper bound | 5 | Model num_available; bundled greedy does not enforce | False | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
| rc201_21 | pyevrp 0.2.1 | safe depot return | every activated EV returns | greedy appends depot; validator checks | True | True | PyPI wheel SHA256 020d1d9fb21f799fc8292c91ba824eb224efadd64debbcfc3fed55d97871f377 |
