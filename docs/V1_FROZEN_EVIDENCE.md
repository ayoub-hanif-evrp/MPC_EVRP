# V1 frozen evidence

The historical paper-track baseline is commit
`d5e3c28847b3842ad7bd10a7d89456235e5911e4`, tagged
`paper-v1-d5e3c28`. Its MPC-MCTS source fingerprint is
`4cdead8ab9956362ba9921c0818b7bcc9690487ab11ba001d087abebe43176b6`.

The complete `results/paper/` tree at that commit is the immutable V1 record:
raw simulation results, manifests, tables, protocols and reports. The V1
MPC-MCTS method served 5295/5400 customers versus 5142/5400 for the
completion-only controller in the inspected paired campaign. These are
historical results, not evidence for any new optimizer or portfolio.

The previous holdout has been inspected and is development data for all new
work. It must never again be described as unseen. New methods must not alter
or overwrite V1 raw JSON, tables, or manifests. To reproduce the exact V1
source, check out the tag in a separate worktree and follow
`results/paper/PAPER_PROTOCOL.md`. New comparisons belong in
`results/portfolio/` and require a new preregistered holdout only after the
development gates and user review.
