# Completed development ablations

The cohorts below are separate matched comparisons. Their outcomes are not
pooled or compared as though they used an identical scenario distribution.
All original method code paths and all unsuccessful results are retained.

| Variant | Design | Paired service finding | Decision |
| --- | --- | --- | --- |
| Depot-window waiting V1 | 12 runs, three selected cases, Completion and ALNS | ALNS +1 customer total; Completion ties | Mixed, disabled |
| Generic LP charging fallback V1 | 12 runs, three selected cases, Completion and ALNS | ALNS -3; Completion ties; slower | Disabled |
| ALNS Recovery V2 pilot | 12 runs, six selected cases | +3 customers with one regression | Balanced screen required |
| ALNS Recovery V2 screen | 36 runs, 18 files, six families x three sizes | +1/1050 customers; 12/18 complete for both; CI spans zero | Experimental |
| Bounded depot reserve V2 | 12 runs, three selected cases, Completion and ALNS | ALNS -4; Completion -1 | Disabled |
| ALNS Stable V3 pilot | Six runs, three selected cases | One win, one tie, one loss; net zero | Balanced screen required |
| ALNS Stable V3 screen | 36 runs, 18 files, six families x three sizes | -0.10 pp service; 0/17/1 wins/ties/losses | Promotion rule not met |

Selective station-skeleton charging and small-route reordering were also
probed at five recorded plan-drop roots. Neither produced an additional
service-preserving witness under the recorded limits. Those are diagnostic
neighborhood results, not global infeasibility certificates.

Combined unsuccessful components were not run blindly. No enhanced search
configuration is reported as superior without an independent evaluation.
