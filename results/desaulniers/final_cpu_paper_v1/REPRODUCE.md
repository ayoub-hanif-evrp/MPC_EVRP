# Reproduce and verify

From the repository root, install requirements.txt in a CPU-only Python environment. The original five methods require no CUDA stack.

1. Verify the existing frozen primary cohort:
   python -m scripts.analyze_desaulniers_robustness --v3
2. Inspect the new replication's frozen protocol and progress:
   python -m scripts.run_final_cpu_replication --freeze
   python -c "from evrp.storage import ROOT,load_json; m=load_json(ROOT/'results/desaulniers/final_cpu_paper_v1/manifest.json'); print(m['status'],m['completed_runs'],m['planned_runs'])"
3. To resume an interrupted, partial study, run the frozen launcher. It verifies and reuses existing raw files byte-for-byte:
   python -u -m scripts.run_final_cpu_replication
4. Rebuild this paper package from saved raw evidence without running an optimizer:
   python -m scripts.run_final_cpu_development --freeze
   python -m scripts.complete_final_cpu_development --freeze
   python -m scripts.analyze_final_cpu_development
   python -m scripts.render_final_cpu_paper
5. Run the complete CPU test suite:
   New-Item -ItemType Directory -Force results/desaulniers/final_cpu_paper_v1/tmp_tests_reproduce
   python -m pytest -q --basetemp results/desaulniers/final_cpu_paper_v1/tmp_tests_reproduce

Do not delete or overwrite a saved raw record to force a rerun. The command in step 3 is the prospective experiment launcher, not required for paper rendering. Every saved record has a manifest SHA-256; audit/verification.json lists the verified protocols and generated outputs. The negative hybrid study is recoverable at Git tag archive/hybrid-gpu-negative-v1.
