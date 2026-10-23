# publication_stable_alns_balanced_development_v1

Design role: **balanced_development_screen**.
Completed and independently audited: 36/36 runs on 18 matched
scenarios from 18 base instances. All decisions meet five seconds.

Customer-weighted service: 98.38% original versus 98.29% enhanced. Paired change -0.10 percentage points, base-instance bootstrap 95% CI [-0.29, +0.00].

Complete service: 66.67% versus 66.67%; paired 95% CI [+0.00, +0.00] percentage points.

Scenario service wins/ties/losses: 0/17/1. Median whole-worker time ratio: 0.99x. Equal-service best-update guard rejections: 1524.

Intervals resample complete base-instance clusters, retaining all associated seeds
and dynamicity levels. Development intervals are exploratory and do not justify
claims on unseen instances. Raw traces, negative cases and manifests are retained.

Underlying-parent sensitivity: 6 parent cases, service 95% CI [-0.29, +0.00] and complete-service CI [+0.00, +0.00] percentage points. This groups size variants of the same parent case together. The original file-clustered selection rule remains the predeclared rule.

Paper tables are Markdown; figures are PNG at 300 dpi under `paper/`.

Predeclared promotion rule satisfied: **False**.

| Selection check | Passed |
| --- | --- |
| service_interval | False |
| complete_service | True |
| hundred_customer_service | False |
| physical_and_information_audits | True |
| decision_budget | True |
