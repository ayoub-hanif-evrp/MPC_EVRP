# Pre-Registered Final Holdout

This protocol must be committed before any final-holdout result is opened.
No tuning after the first final result is opened.

Selection rule: `MPC_EVRPTW_SHA256_UNUSED_21_V1`. For each family, take the candidate with the
lexicographically smallest SHA-256 of
`RULE|FAMILY|instance_stem|benchmark_file_sha256`.

Frozen development commit: `70469d4737bdfc4bee40388a7388b8f7a5414050`
Optimizer source fingerprint: `3c6ffdfb5ab86190ff6c45e7eaf063dcdb6c80508bf46c6849269342e718628b`
Controller config: `configs/paper_controller.yaml`
Controller SHA-256: `a28ef410ebed72331815b49f954f907809637266d24e47043810dd96779a9817`
Development protocol SHA-256: `e586fd8ce95453209fa8ad9ca2fb81eebdadbd32dfd5b78f14f64c48acfbd475`
Holdout runner SHA-256: `00b085318a23953e7045554175afdad152f577534e851a07166dbd1c57068538`
Shadow selection SHA-256: `cd7ed8f5e28169270e337e390a1e209f160bdeb38411f09123f76674469bf063`
Shadow gate SHA-256: `d7a4fc07f9232e0ca38252fc731352bf4da78c02348815a9c99366e5815271c2`
Portfolio gate: `PASS`. Selector deployment: `YES`.

Previously referenced/used _21 instances are excluded:
`c101_21`, `c103_21`, `c109_21`, `c201_21`, `c203_21`, `c208_21`, `r101_21`, `r103_21`, `r112_21`, `r201_21`, `r203_21`, `r211_21`, `rc101_21`, `rc103_21`, `rc108_21`, `rc201_21`, `rc203_21`, `rc208_21`

| Family | Selected unused instance | Source SHA-256 | Eligible pool |
| --- | --- | --- | ---: |
| C1 | `c102_21` | `c63f00c8fe479e2c94dc1bb0675dd3bde20a992668b4b9302dc8f0023eb57c7a` | 6 |
| C2 | `c206_21` | `ac0871bbee80d3df5e9c8fa8634b0cd26ed0af7f4fb52e090f548d313a0f7744` | 5 |
| R1 | `r109_21` | `3b5daa4b35e310f961f84ecb074db0205997245a4879920308aee3e8446f3478` | 9 |
| R2 | `r207_21` | `c8a1d5e6977912971c72ea7371a98c9db52a60456275bedbc315a6cf8660fec7` | 8 |
| RC1 | `rc104_21` | `09b795b522387813ece99cd898ac3b43749173a1ff8c78c3cb6915fc17be19e3` | 5 |
| RC2 | `rc204_21` | `947224b4eaa54dab358f0ad7e598ad6b570889aff3c560ec829cff57800b7625` | 5 |

Dynamicity targets: `{0.25, 0.50, 0.75}`. Scenario seeds: `{0, 1, 2}`.
The grid has 54 scenarios per method and 324 isolated simulations.
Methods: `MPC_COMPLETION`, `MPC_MCTS`, `MPC_ALNS`, `MPC_HGS`, `MPC_ACS`, `MPC_PORTFOLIO`.

Every simulation starts in a fresh interpreter, runs one method/scenario,
passes independent physical and information-boundary audit, and records
compressed raw evidence. Primary ranking is customers served, then
complete-service rate, EV count only at equal service, and distance only
at equal service and EV count. VBS is analysis-only and is not deployed.

Selector source SHA-256: `50e9afbf5ac2d60a3a83fa15fdc0c07a88e20a5b18cb14d12aabd6275e3a2ceb`
Selector model SHA-256: `6e6d26857ab006ab2f3eba25c74886217da5ca38a6a6d584e783ecc9fea32017`
Selector grouped-CV SHA-256: `edcc8ef5d6790c943362ba569361bf0db9151fffa6e4131c2045ebd6e1a4dfae`.
Held-out-scenario planned-service gain over SBS: 33.
Held-out-instance planned-service gain over SBS: 35.
