# Reproduce and verify

From the repository root, install requirements.txt in a CPU-only Python environment. The original five methods require no CUDA stack.

1. Restore exact historical inputs and audit the frozen primary cohort:
   python -m scripts.archive_frozen_inputs --restore
   python -m scripts.audit_frozen_studies
   python -m scripts.audit_enhancement_studies
   python -m scripts.audit_reference_inventory
2. Run the full CPU regression suite and record its outcome:
   python -m pytest -q --basetemp results/.pytest_cpu_reproduce --junitxml results/desaulniers/final_cpu_paper_v1/audit/final_tests.xml
3. Rebuild this paper package from saved raw evidence without running an optimizer:
   python -m scripts.run_final_cpu_development --freeze
   python -m scripts.complete_final_cpu_development --freeze
   python -m scripts.analyze_final_cpu_development
   python -m scripts.render_final_cpu_paper
4. Verify cumulative execution, tests, evidence and delivery:
   python -m scripts.audit_final_cpu_completion

Do not delete or overwrite a saved raw record to force a rerun. All experiment manifests are complete; reproducing the package does not require another optimization campaign. Every saved record has a manifest SHA-256; audit/verification.json lists the verified protocols and generated outputs. The negative hybrid study is recoverable at Git tag archive/hybrid-gpu-negative-v1.
