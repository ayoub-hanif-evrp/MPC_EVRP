# Observable-state service-loss evidence

Each row is a retrospectively selected root/customer, not an independent experiment.
Release/deadline values come from archived scenarios for postmortem reporting only.
The online candidates never access unreleased customer attributes.
Screen passes are necessary conditions; decode success need not be a feasible insertion
preserving every other planned customer. Root charging failures are not target-specific
or proof of battery infeasibility. Busy counts indicate fixed irreversible commitments,
not proof they caused a miss. No bounded probe in this diagnosis found a better canonical plan.

| Instance | Customer | Root time | Selection | Release / ready / due | Ready / busy EVs | Constructor / selected planned | Optimizer replacement | Suffix invalid | Optimizer deadline | TW rejects / screen passes | Decodes feasible / failed | Post-commit screen options | Root charge failures |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: |
| r101_21_25 | C67 | 0.000 | first_visible | 0.000 / 143.000 / 153.000 | 9 / 0 | True / True | False | False | False | 14 / 20 | 147 / 0 | None | 0 |
| r101_21_25 | C8 | 21.232 | first_visible | 21.232 / 27.000 / 37.000 | 3 / 6 | False / False | False | False | False | 154 / 0 | 0 / 0 | 0 | 5 |
| r101_21_25 | C67 | 86.843 | last_planned | 0.000 / 143.000 / 153.000 | 1 / 8 | True / True | False | False | False | 17 / 1 | 1 / 0 | None | 5 |
| r101_21_25 | C67 | 94.630 | subsequent_plan_loss | 0.000 / 143.000 / 153.000 | 0 / 9 | True / False | True | False | False | 43 / 2 | 0 / 0 | 0 | 6 |
| r101_21_100 | C65 | 8.391 | first_visible | 8.391 / 68.000 / 78.000 | 9 / 11 | True / True | False | False | False | 183 / 30 | 216 / 0 | None | 14 |
| r101_21_100 | C61 | 18.258 | first_visible | 18.258 / 29.000 / 39.000 | 6 / 14 | False / False | False | False | False | 529 / 0 | 0 / 0 | 0 | 25 |
| r101_21_100 | C19 | 36.408 | first_visible | 36.408 / 48.000 / 58.000 | 2 / 18 | False / False | False | False | False | 1178 / 0 | 0 / 0 | 0 | 78 |
| r101_21_100 | C65 | 38.382 | last_planned | 8.391 / 68.000 / 78.000 | 3 / 17 | True / True | False | False | False | 254 / 1 | 27 / 0 | None | 87 |
| r101_21_100 | C65 | 38.736 | subsequent_plan_loss | 8.391 / 68.000 / 78.000 | 2 / 18 | True / False | True | False | False | 737 / 2 | 0 / 0 | 0 | 40 |
| r101_21_100 | C72 | 64.905 | first_visible | 64.905 / 111.000 / 121.000 | 0 / 20 | False / True | False | False | False | 585 / 19 | 77 / 1 | None | 97 |
| r101_21_100 | C78 | 81.324 | first_visible | 81.324 / 94.000 / 104.000 | 0 / 20 | False / False | False | False | False | 979 / 24 | 0 / 758 | 2 | 72 |
| r101_21_100 | C72 | 103.546 | last_planned | 64.905 / 111.000 / 121.000 | 0 / 20 | True / True | False | False | False | 96 / 2 | 15 / 25 | None | 23 |
| r101_21_100 | C72 | 104.778 | subsequent_plan_loss | 64.905 / 111.000 / 121.000 | 0 / 20 | True / False | True | False | False | 351 / 3 | 20 / 28 | 0 | 42 |
| r101_21_100 | C25 | 126.006 | first_visible | 126.006 / 137.000 / 147.000 | 0 / 20 | False / False | False | False | False | 287 / 0 | 0 / 0 | 0 | 12 |
| c101_21_100 | C18 | 0.000 | first_visible | 0.000 / 557.000 / 601.000 | 12 / 0 | True / True | False | False | True | 664 / 93 | 179 / 89 | None | 480 |
| c101_21_100 | C18 | 387.780 | last_planned | 0.000 / 557.000 / 601.000 | 1 / 11 | True / True | False | False | False | 191 / 15 | 49 / 434 | None | 230 |
| c101_21_100 | C18 | 388.353 | subsequent_plan_loss | 0.000 / 557.000 / 601.000 | 1 / 11 | True / False | True | False | False | 555 / 35 | 3 / 735 | 2 | 179 |
| c101_21_100 | C45 | 394.780 | first_visible | 394.780 / 421.000 / 475.000 | 0 / 12 | False / True | False | False | False | 314 / 6 | 22 / 428 | None | 280 |
| c101_21_100 | C45 | 409.050 | last_planned | 394.780 / 421.000 / 475.000 | 0 / 12 | True / True | False | False | False | 272 / 4 | 42 / 429 | None | 373 |
| c101_21_100 | C45 | 421.240 | subsequent_plan_loss | 394.780 / 421.000 / 475.000 | 1 / 11 | True / False | True | False | False | 773 / 4 | 12 / 105 | 0 | 265 |
