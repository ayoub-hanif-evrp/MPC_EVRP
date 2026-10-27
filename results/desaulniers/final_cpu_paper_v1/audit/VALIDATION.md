# Final validation record

Validation was run after the CPU study completed. No command below launched
new routing experiments.

| Check | Outcome |
| --- | --- |
| Frozen CPU replication | 60/60 planned method runs, 12 matched scenarios, no failed worker |
| Paper renderer disk replay | 510/510 raw records (450 primary, 60 replication), all protocol/hash and physical/information audits passed |
| Balanced development ablation | 120/120 saved raw records independently replayed; six parents, five methods, six variants on the fixed three-parent ablation subset |
| Technical correction | Original RC2 ALNS whole-worker timeout retained; eight pending jobs completed under frozen 900 s correction; total 2.051 charged wall h and 1.944 worker CPU h |
| Two-worker technical probe | 4/4 original-method trajectories independently replayed; same service in sequential/two-worker modes; 1.50x small-case throughput on shared machine |
| Decision budget | Maximum recorded latency 4.796 s, below 5 s |
| Full CPU test suite | 402/402 passed |
| Historical frozen-study audit | 990/990 replayed (270 development, 270 corrected final, 450 robustness v3) |
| Enhancement-study audit | 159/159 replayed across nine saved studies |
| General MP reference inventory | 166/168 witnesses in that inventory; separate targeted follow-up supplies the other 2 |
| Paper outputs | 14 PNG at 300 dpi, 14 SVG, 13 Markdown tables with CSV and LaTeX exports |

The first local pytest attempt could not access its Windows sandbox temporary
directory; the same full suite then passed outside that filesystem restriction.
This was an execution-environment permission issue, not a test assertion.

Commands:

- python -m pytest -q --basetemp results/desaulniers/final_cpu_paper_v1/tmp_tests_final_confirm
- python -m scripts.audit_frozen_studies
- python -m scripts.audit_enhancement_studies
- python -m scripts.audit_reference_inventory
- python -m scripts.analyze_final_cpu_development
- python -m scripts.render_final_cpu_paper

The first three historical audit commands regenerate only their derived audit
summaries. The reference inventory's 166 count and the separate two-witness
follow-up use distinct inventories; neither changes the new cohort's frozen
inputs or the historical K_ref values.
