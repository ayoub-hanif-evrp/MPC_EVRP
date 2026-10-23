# Forced retained-route coordination probe

A retained route is forced by maximum coverage when each ready EV has at
most one positive-coverage proposal and those proposals are mutually
disjoint and disjoint from immutable background routes. EVs without
coverage have exactly one fallback. There is then no remaining activation
or distance choice. Unsupported inputs return to general coordination.

The shortcut was compared with the unchanged three-stage MILP on recorded
observable development roots. Every selected action sequence must match.

| Instance | Time | Ready EVs | MILP median ms | Shortcut median ms | Equal routes |
| --- | ---: | ---: | ---: | ---: | --- |
| r101_21_25 | 0.573 | 7 | 2.8275 | 0.0132 | True |
| r101_21_25 | 5.476 | 6 | 2.6992 | 0.0117 | True |
| r101_21_25 | 9.866 | 6 | 2.7803 | 0.0125 | True |
| r101_21_100 | 1.859 | 12 | 5.5137 | 0.0325 | True |
| r101_21_100 | 2.001 | 12 | 5.5655 | 0.0312 | True |
| r101_21_100 | 3.782 | 12 | 5.4487 | 0.0315 | True |
| c101_21_100 | 23.116 | 2 | 8.3057 | 0.0244 | True |
| c101_21_100 | 24.645 | 1 | 8.2245 | 0.0189 | True |
| c101_21_100 | 42.927 | 1 | 7.3943 | 0.0177 | True |

Each root was repeated 20 times on one machine. This microbenchmark
establishes exact route agreement on these inputs; it does not establish
closed-loop service gains or general hardware speedups.

