# Active and preserved repository contents

The active publication workflow is CPU-only. The original five MPC modes and
the Desaulniers MP model remain the supported scientific configuration.

| Class | Contents | Treatment |
| --- | --- | --- |
| Active | evrp core, Desaulniers data, paper_controller.yaml, robustness v3 analyzer, final CPU replication runner and paper renderer | Retain and test |
| Scientifically archived in tree | Original final holdout, robustness v3, targeted-service, reliability, performance-engineering and fast-framework protocols, raw traces, reports and referenced scripts | Preserve unchanged; do not pool cohorts |
| Recoverable negative archive | GPU/hybrid launchers, config, raw records and reports at Git tag archive/hybrid-gpu-negative-v1 | Removed only from active tree after remote tag verification |
| Opt-in research code | compiled_screen.py and quality_policy.py | Retain because they are CPU-capable and tested, but not publication defaults after service regressions |
| Regenerable | Derived paper tables and figures | Rebuild from immutable raw and manifests with render_final_cpu_paper.py |
| Obsolete or temporary | CUDA/CuPy launchers from the archived experiment and local pytest caches | No active dependency; GPU launchers removed; local caches are ignored |

Many old experiment scripts look superseded but their frozen protocols,
reports, tests, and reproduction commands still refer to them. They are
historical scientific evidence, not dead code to delete casually. The
stopped Reliability V2 study stays stopped and does not enter the paper
package. Dataset files, offline references and audit raw traces are retained.

The active dependency files contain no CUDA or CuPy requirement. No GPU
execution path is part of the maintained project. The negative GPU findings
and exact archived revision are documented in [CPU_BACKEND_DECISION.md](CPU_BACKEND_DECISION.md).
