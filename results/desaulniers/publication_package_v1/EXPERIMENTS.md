# Experimental evidence and interpretation

The original corrected final study has 270 runs on 54 scenarios from 18 benchmark
files. Size variants can share a parent case. Robustness-v3 separately has 450 runs on 90 scenarios from six
different instances, three DoD levels and five release seeds. Their results
are not pooled. All 990 original development, corrected-final and robustness
records were independently replayed by the new historical-source auditor.

Stable V3 was tested first on three selected development loss cases, then on a
predeclared balanced development screen crossing six families and three sizes
at DoD 0.75, seed 0. The balanced screen has 36 runs and 18 matched scenarios.
Customer service changed by -0.10 percentage points,
with base-instance bootstrap 95% interval
[-0.29, +0.00]. Complete
service was 66.67% versus
66.67%. Scenario service wins/ties/losses were
0/17/1.

The frozen promotion rule was not satisfied. The original implementation is
retained; no independent enhanced-method holdout was opened. The development
tables are not a final original-versus-enhanced performance claim. No enhanced
final table is fabricated from historical rates on different instances.

Confidence intervals resample complete base-instance clusters. Seeds and DoD
repeats within an instance are retained together. Development intervals are
exploratory. Historical ALNS-HGS intervals cross zero and do not establish
general superiority. Conditional distance, EV and charging comparisons use
only common fully served scenarios.

An additional sensitivity groups size variants sharing a parent instance.
The development screen has 6 such parent cases;
its parent-clustered service interval is
[-0.29, +0.00]
percentage points. This dependence limits claims based on the 18 file-level
clusters. The predeclared file-clustered selection rule is reported unchanged.

Offline witness coverage increases separately by 16 cases.
These schedules are heuristic fleet upper bounds and are never substituted
into the frozen online fleet or release policy. Search failure and timeout
are recorded explicitly without calling an instance physically infeasible.
