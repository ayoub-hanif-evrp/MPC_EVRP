# Immutable original-study audit

Frozen source fingerprints are reconstructed from historical Git blobs.
Current physical and scenario engines exactly match those historical files.
Every raw file was SHA-256 checked, independently replayed and matched
against its fixed scenario, fleet and five-second decision budget.

| Study | Runs | Paired scenarios | Benchmark files | Parent cases | Source commit |
| --- | ---: | ---: | ---: | ---: | --- |
| development | 270 | 54 | 18 | 6 | 59424520b7cba1d83e3627dde317addfa659cfd5 |
| corrected_final | 270 | 54 | 18 | 6 | 380099c280da6d4c7d751137aca68d40cb9b3e96 |
| robustness_v3 | 450 | 90 | 6 | 6 | 73e28a85d88390a0c142d965e483681db9ae7f1e |

Size variants can share customer records from an underlying parent
instance. The separate sensitivity below clusters those files together.
It retains the original equally weighted scenario-service contrast.
Exact parent sign-flip p-values assume clusterwise sign exchangeability;
Holm adjusts the five contrasts within each study. This is an exploratory
sensitivity analysis, not a retroactive change to the original protocol.

| Study | Contrast | Mean effect pp | Parent-clustered 95% CI pp | Holm p |
| --- | --- | ---: | --- | ---: |
| development | MPC_MCTS_vs_MPC_COMPLETION | +2.15 | [+0.30, +4.65] | 0.6250 |
| development | MPC_ALNS_vs_MPC_COMPLETION | +3.56 | [+0.85, +6.80] | 0.6250 |
| development | MPC_HGS_vs_MPC_COMPLETION | +3.63 | [+0.89, +7.31] | 0.6250 |
| development | MPC_ACS_vs_MPC_COMPLETION | +2.93 | [+0.78, +5.26] | 0.6250 |
| development | MPC_ALNS_vs_MPC_HGS | -0.07 | [-0.70, +0.56] | 0.8750 |
| corrected_final | MPC_MCTS_vs_MPC_COMPLETION | +4.70 | [+0.69, +9.56] | 0.4375 |
| corrected_final | MPC_ALNS_vs_MPC_COMPLETION | +7.83 | [+2.57, +13.69] | 0.1875 |
| corrected_final | MPC_HGS_vs_MPC_COMPLETION | +7.76 | [+2.96, +13.31] | 0.1562 |
| corrected_final | MPC_ACS_vs_MPC_COMPLETION | +6.57 | [+2.44, +11.13] | 0.1562 |
| corrected_final | MPC_ALNS_vs_MPC_HGS | +0.07 | [-0.72, +0.91] | 0.8125 |
| robustness_v3 | MPC_MCTS_vs_MPC_COMPLETION | +4.07 | [+1.18, +7.18] | 0.6250 |
| robustness_v3 | MPC_ALNS_vs_MPC_COMPLETION | +8.33 | [+2.16, +15.07] | 0.6250 |
| robustness_v3 | MPC_HGS_vs_MPC_COMPLETION | +7.70 | [+2.41, +13.60] | 0.6250 |
| robustness_v3 | MPC_ACS_vs_MPC_COMPLETION | +6.17 | [+1.58, +11.10] | 0.6250 |
| robustness_v3 | MPC_ALNS_vs_MPC_HGS | +0.63 | [-0.62, +1.94] | 0.6250 |
