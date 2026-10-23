"""Assemble audited original findings and completed enhancement development."""

from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle
from PIL import Image

from evrp.storage import ROOT, load_json, save_json, writable_path


OUTPUT = ROOT / "results/desaulniers/publication_package_v1"
DEVELOPMENT = ROOT / "results/desaulniers/publication_development"


def write(name, text):
    writable_path(OUTPUT / name).write_text(text.strip() + "\n", encoding="utf-8")


def copy_artifacts(source, destination):
    for path in sorted(source.glob("*")):
        if path.is_file() and path.suffix in {".md", ".png"} and path.name != "RESULTS.md":
            shutil.copyfile(path, writable_path(OUTPUT / destination / path.name))


def architecture():
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set(xlim=(0, 12), ylim=(0, 6))
    ax.axis("off")
    boxes = {
        "requests": (.25, 3.25, 2, 1, "Released requests\nand measured EV states"),
        "trigger": (3, 3.25, 2, 1, "Event-triggered\nMPC decision"),
        "constructor": (5.75, 3.25, 2, 1, "Common feasible\nfleet constructor"),
        "search": (8.6, 3.05, 3, 1.4, "Completion / MCTS\nALNS / HGS / ACS"),
        "validate": (8.6, .65, 3, 1.1, "Plant replay and\nnext-action validation"),
        "plant": (3, .65, 4.75, 1.1, "Execute one noninterruptible physical action"),
        "reference": (.25, 5, 7.5, .6, "Offline feasible reference: fixed fleet and reference-preserving releases"),
    }
    for key, (x, y, width, height, label) in boxes.items():
        ax.add_patch(Rectangle((x, y), width, height, facecolor="#edf5f2" if key == "reference"
                               else "#f3f5f7", edgecolor="#52606d", linewidth=1))
        ax.text(x + width / 2, y + height / 2, label, ha="center", va="center", fontsize=10)
    for start, end in (((2.25, 3.75), (3, 3.75)), ((5, 3.75), (5.75, 3.75)),
                       ((7.75, 3.75), (8.6, 3.75)), ((10.1, 3.05), (10.1, 1.75)),
                       ((8.6, 1.2), (7.75, 1.2)), ((3, 1.2), (1.25, 1.2)),
                       ((1.25, 1.2), (1.25, 3.25)), ((1.25, 5), (1.25, 4.25))):
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=12,
                                    color="#52606d", linewidth=1.2))
    ax.text(6, .15, "Online optimizers receive currently observable requests and immutable action after-states.",
            ha="center", va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(writable_path(OUTPUT / "architecture.png"), dpi=350)
    plt.close(fig)


def render():
    audits = load_json(DEVELOPMENT / "audits/historical_integrity.json")
    enhancement_audits = load_json(DEVELOPMENT / "audits/enhancement_integrity.json")
    screen_manifest = load_json(DEVELOPMENT / "stable_screen_v1/manifest.json")
    screen = load_json(DEVELOPMENT / "stable_screen_v1/analysis.json")["summary"]
    reference = load_json(DEVELOPMENT / "reference_extension_v1/manifest.json")
    if (not all(r["all_independent_audits_passed"] for r in audits["studies"].values()) or
            screen_manifest["status"] != "complete" or
            reference["completed_instances"] != reference["planned_instances"]):
        raise ValueError("Publication package requires complete independent audits and development studies")
    if screen["promotion_eligible"]:
        raise ValueError("Promoted variant requires a new independent final evaluation before final packaging")
    junit = ET.parse(DEVELOPMENT / "audits/tests.xml").getroot()
    suites = [junit] if junit.tag == "testsuite" else list(junit.iter("testsuite"))
    test_count = sum(int(s.get("tests", "0")) for s in suites)
    if any(int(s.get("failures", "0")) or int(s.get("errors", "0")) for s in suites):
        raise ValueError("Publication package cannot claim a passing regression suite")
    copy_artifacts(ROOT / "results/desaulniers/paper_v2", "original_final")
    copy_artifacts(ROOT / "results/desaulniers/robustness_v3", "robustness_v3")
    copy_artifacts(DEVELOPMENT / "stable_screen_v1/paper", "development/paper")
    copy_artifacts(DEVELOPMENT / "instrumented_v1", "diagnosis")
    shutil.copyfile(DEVELOPMENT / "stable_screen_v1/RESULTS.md",
                    writable_path(OUTPUT / "development/RESULTS.md"))
    shutil.copyfile(DEVELOPMENT / "reference_extension_v1/RESULTS.md",
                    writable_path(OUTPUT / "reference_coverage.md"))
    shutil.copyfile(DEVELOPMENT / "audits/HISTORICAL_INTEGRITY.md",
                    writable_path(OUTPUT / "validation.md"))
    shutil.copyfile(DEVELOPMENT / "audits/ENHANCEMENT_INTEGRITY.md",
                    writable_path(OUTPUT / "enhancement_validation.md"))
    architecture()
    source_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                   text=True, check=True).stdout.strip()
    improved_references = sum(r["status"] == "feasible_reference_found" for r in reference["records"])
    methods = audits["studies"]["corrected_final"]["methods"]
    primary = ["# Original corrected final holdout", "",
               "270 independently audited runs on 54 matched scenarios from 18 benchmark files.",
               "Some size variants share an underlying parent case; see the sensitivity analysis.", "",
               "| Method | Customer service % | Gap to full-service offline reference (pp) | Complete scenarios % | Maximum decision s |",
               "| --- | ---: | ---: | ---: | ---: |"]
    primary.extend(f"| {name} | {100*r['service']:.2f} | "
                   f"{100*(1-r['service']):.2f} | "
                   f"{100*r['complete_scenarios']/r['scenarios']:.2f} | {r['max_decision_seconds']:.4f} |"
                   for name, r in methods.items())
    write("primary_results.md", "\n".join(primary))
    write("original_final/RESULTS.md", """
# Original corrected final study

These tables and figures reproduce the completed 270-run corrected holdout.
The original immutable source artifacts remain under `results/desaulniers/paper_v2/`.

- [Overall service and complete-service results](table3_overall.md)
- [Results by customer size](table4_size.md)
- [Results by DoD](table5_dod.md)
- [Paired comparisons and clustered intervals](table6_paired.md)
- [Results by family](table7_family.md)
- [Protocol](table2_protocol.md)
- [Benchmark](table1_benchmark.md)

The corresponding PNG figures are in this directory. The separate robustness
study is reported in [its own section](../robustness_v3/RESULTS.md).
""")
    robustness = audits["studies"]["robustness_v3"]["methods"]
    robust_lines = ["# Separate multi-seed robustness study", "",
                    "450 audited runs on 90 scenarios from six base instances, three DoD levels",
                    "and release seeds 1-5. This cohort is not pooled with the original final study.", "",
                    "| Method | Customer service % | Complete scenarios % |", "| --- | ---: | ---: |"]
    robust_lines.extend(f"| {name} | {100*r['service']:.2f} | "
                        f"{100*r['complete_scenarios']/r['scenarios']:.2f} |" for name, r in robustness.items())
    robust_lines += ["", "[Full original summary](SUMMARY.md). The descriptive ALNS-HGS",
                     "base-instance interval crosses zero; the observed ranking does not",
                     "establish general superiority. Only six independent base instances",
                     "contribute to this robustness cohort."]
    write("robustness_v3/RESULTS.md", "\n".join(robust_lines))
    write("METHODS.md", """
# Framework and unchanged mathematical problem

The static input is the Desaulniers et al. (2016) dataset with multiple partial
recharging (MP). The loader validates all format-2 arc costs, travel times and
energy against format-1 input. Existing distance, time, energy conversion and
rounding functions are used throughout. The plant enforces battery bounds,
remaining payload, service-start time windows, safe depot return, one route per
fixed-fleet EV, and the published station-to-station restriction. Linear charging
adds time in proportion to energy. No fleet enlargement, window relaxation or
nonlinear charging is used in online comparisons.

Dynamic requests become visible only on release. The common event-triggered
controller plans from measured idle-vehicle states and the after-states of
immutable busy actions. It coordinates unique customer ownership, constructs
feasible suffixes, runs the selected optimizer, independently replays the chosen
routes, and executes the next physical action. Five seconds is the shared
decision budget, including construction, search and final validation.

## Canonical objective

The implementation uses lexicographic minimization. With uncovered observable
customers, its tuple is `(unserved, zero_options, one_option, control_risk,
time_window_risk, battery_risk, capacity_risk, normalized_distance)`.
`zero_options` and `one_option` count screened insertion options; they are
heuristic opportunity indicators, not certificates of physical infeasibility.

With complete currently observable coverage, the tuple is `(0, control_risk,
flexibility_risk, activated_vehicles, operational_cost, distance,
route_instability)`. Flexibility averages time-window, battery, payload and
time-reserve risk. Operational cost averages the original seven normalized
distance, duration, charge, waiting, time-window, battery and balance measures.
The definitions in `evrp/optimizers/objective.py` are unchanged across methods.

## Algorithms and explicit development variants

Completion retains the common feasible constructor; MCTS, ALNS, HGS and ACS
search the same observable fleet problem with the common objective and plant.
Original implementations and historical source commits remain available.

ALNS Stable V3 restricts best-incumbent replacement during equal-service moves
to plans covering the same customer set. It allows route reassignment and
strict coverage increases, and scores candidates with the canonical objective.
This is an explicit search-policy change. It does not guarantee improved
closed-loop service and is governed by the frozen development selection rule.

Other evaluated variants are depot-window waiting, generic continuous-charge
fallback, ALNS Recovery V2, and bounded one-EV depot reserve. They remain
experimental because measured gains were mixed, negligible or negative.
""")
    write("EXPERIMENTS.md", f"""
# Experimental evidence and interpretation

The original corrected final study has 270 runs on 54 scenarios from 18 benchmark
files. Size variants can share a parent case. Robustness-v3 separately has 450 runs on 90 scenarios from six
different instances, three DoD levels and five release seeds. Their results
are not pooled. All 990 original development, corrected-final and robustness
records were independently replayed by the new historical-source auditor.

Stable V3 was tested first on three selected development loss cases, then on a
predeclared balanced development screen crossing six families and three sizes
at DoD 0.75, seed 0. The balanced screen has 36 runs and 18 matched scenarios.
Customer service changed by {100*screen['service_delta']:+.2f} percentage points,
with base-instance bootstrap 95% interval
[{100*screen['service_ci'][0]:+.2f}, {100*screen['service_ci'][1]:+.2f}]. Complete
service was {100*screen['original_complete']:.2f}% versus
{100*screen['enhanced_complete']:.2f}%. Scenario service wins/ties/losses were
{screen['wins']}/{screen['ties']}/{screen['losses']}.

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
The development screen has {screen['parent_instances']} such parent cases;
its parent-clustered service interval is
[{100*screen['parent_service_ci'][0]:+.2f}, {100*screen['parent_service_ci'][1]:+.2f}]
percentage points. This dependence limits claims based on the 18 file-level
clusters. The predeclared file-clustered selection rule is reported unchanged.

Offline witness coverage increases separately by {improved_references} cases.
These schedules are heuristic fleet upper bounds and are never substituted
into the frozen online fleet or release policy. Search failure and timeout
are recorded explicitly without calling an instance physically infeasible.
""")
    write("ABLATIONS.md", f"""
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
| ALNS Stable V3 screen | 36 runs, 18 files, six families x three sizes | {100*screen['service_delta']:+.2f} pp service; {screen['wins']}/{screen['ties']}/{screen['losses']} wins/ties/losses | Promotion rule not met |

Selective station-skeleton charging and small-route reordering were also
probed at five recorded plan-drop roots. Neither produced an additional
service-preserving witness under the recorded limits. Those are diagnostic
neighborhood results, not global infeasibility certificates.

Combined unsuccessful components were not run blindly. No enhanced search
configuration is reported as superior without an independent evaluation.
""")
    write("LITERATURE.md", """
# Methodological references consulted

- [Desaulniers et al. (2016)](https://doi.org/10.1287/opre.2016.1535)
  defines the static benchmark and charging variants used as the physical source.
- [Keskin and Catay (2016), author manuscript](https://research.sabanciuniv.edu/26033/1/WP_EVRPTW-Partial_Recharge_KeskinCatay.pdf)
  studies partial charging with ALNS. Its charging-aware repair ideas motivate
  feasibility probes; its reported gains are not evidence for this implementation.
- [Ropke and Pisinger (2006)](https://doi.org/10.1287/trsc.1050.0135)
  provides the adaptive removal/insertion framework underlying ALNS.
- [Bent and Van Hentenryck (2007)](https://www.ijcai.org/Abstract/07/293)
  studies waiting and relocation with online stochastic requests. The repository's
  bounded depot-wait policies do not reproduce that stochastic algorithm.
- [Wang, Sun and Huang (2024)](https://www.sciencedirect.com/science/article/pii/S0360835224002432)
  motivates time-window compatibility and efficient insertion in dynamic routing.
  Its multi-depot model is different from the fixed physical benchmark here.
- [Erdelic et al. (2026)](https://doi.org/10.1016/j.cie.2025.111758)
  combines ALNS with charging-station placement and caching in a time-dependent
  setting. Its travel and charging assumptions are not imported into this study.

These works guide mechanisms to investigate; they do not imply that any tested
repository enhancement is beneficial. All empirical claims in this package
come from the recorded, audited experiments.
""")
    write("FAILURE_ANALYSIS.md", """
# Service-loss evidence and failed enhancements

The first-visible development ALNS probe examined 33 missed customers: 18 had
no ready EV, six were selected in a soft plan, one had a validated top-three
insertion, and eight had no bounded insertion witness. Full decision timelines
record 11 later losses of soft-plan ownership. These observations do not prove
the preceding action caused eventual service loss.

Three instrumented development runs recorded complete root states, executing
actions, retained and discarded suffixes, insertion-screen results, decoding
outcomes, fully scored candidates and selected fleet routes. Over two million
events were captured without truncation. No recorded fully scored ALNS
candidate dominated the selected objective at these roots.

Five missed-customer plan drops occurred during optimization; four exchanged
one planned customer for another at equal immediate coverage. Two-second
original-decoder insertion/ejection probes, selective charge-amount LP probes
along existing station orders, and five-second small-route reordering probes
found no additional service-preserving witness at those five final roots.
Failure under these bounded neighborhoods is not a global infeasibility proof.

The bounded reserve pilot regressed ALNS by four customers over its three
selected cases. Stable V3's initial pilot gained one customer on one
100-customer case and lost one on another. The broader screen determines its
acceptance. These failures support reporting a limit of the tested mechanisms,
not claiming that every missed customer is physically impossible online.

A separate synthetic reproducer confirmed optimizer-initialization timeout
crashes in ALNS, HGS and ACS. Runtime corrections and their tests are documented
with the source changes; they are reliability fixes, not evidence of improved
customer service in the completed historical campaigns.
""")
    write("REPRODUCTION.md", f"""
# Reproduction and artifact provenance

Package-generation source commit: `{source_commit}`. Dependencies are in
`requirements.txt`; the validated regression suite contains {test_count} tests.
The evidence inventory binds copied artifacts to file SHA-256 digests.

```powershell
python -m pytest tests -q --basetemp results/.pytest_publication
python -m scripts.audit_frozen_studies
python -m scripts.analyze_planning_losses
python -m scripts.analyze_publication_pair --config configs/publication_stable_screen_v1.yaml
python -m scripts.render_publication_package
```

The historical-source auditor checks Git blobs at the exact executed source
revisions instead of requiring the current development tree to be identical.
The old study-specific runners still enforce their own original fingerprints;
use the archived commits when reproducing their optimization, rather than
editing their protocols. Raw evidence remains in the original result paths.

New runner: `python -m scripts.run_publication_campaign --config <config>`.
Offline extension: `python -m scripts.extend_mp_reference_coverage`.
Both reuse validated saved artifacts, reject provenance drift, and preserve
failures. Do not rerun optimization to regenerate paper tables.

All paper tables are Markdown and figures are PNG at 300 dpi or higher.
Internal JSON, CSV and XML are retained outside this paper directory.
""")
    write("RESULTS.md", f"""
# Event-triggered MPC for dynamic MP EVRPTW

This package combines the independently audited original comparison with
completed, explicitly separate enhancement development. The strongest
supported customer-service result remains the original framework. The tested
Stable V3 enhancement did not satisfy its frozen promotion rule.

- [Primary original final results](primary_results.md)
- [Original final tables and figures](original_final/RESULTS.md)
- [Separate multi-seed robustness study](robustness_v3/RESULTS.md)
- [Matched enhancement development results](development/RESULTS.md)
- [Methods and unchanged objective](METHODS.md)
- [Experimental design and statistical limits](EXPERIMENTS.md)
- [Failure analysis](FAILURE_ANALYSIS.md)
- [Component ablations and unsuccessful experiments](ABLATIONS.md)
- [Offline reference coverage](reference_coverage.md)
- [Independent historical evidence audit](validation.md)
- [Enhancement evidence audit](enhancement_validation.md)
- [Methodological references](LITERATURE.md)
- [Reproduction commands](REPRODUCTION.md)

The primary paper contribution is a common event-triggered MPC comparison of
five optimization engines with a fixed physical model and dynamic information
boundary. The enhancement evidence is a mechanism study with unsuccessful
and mixed results. A claim of superior enhanced service is not supported.

The package is suitable for manuscript preparation of those measured findings.
Generalization remains limited by the original sample sizes, the single-seed
development screen, and the absence of a promoted enhancement evaluated on
new independent instances. No optimality or universal superiority is claimed.
""")
    inventory = []
    for path in sorted(OUTPUT.rglob("*")):
        if not path.is_file() or path.name == "artifact_inventory.json":
            continue
        entry = dict(path=path.relative_to(OUTPUT).as_posix(), sha256=sha256(path.read_bytes()).hexdigest())
        if path.suffix == ".png":
            with Image.open(path) as image:
                dpi = image.info.get("dpi", (0, 0))
                if min(dpi) < 299.5:
                    raise ValueError(f"Paper figure below 300 dpi: {path}")
                entry.update(width=image.width, height=image.height, dpi=dpi)
        inventory.append(entry)
    save_json(OUTPUT / "artifact_inventory.json", dict(source_commit=source_commit,
              original_study_audits=audits, enhancement_audits=enhancement_audits, artifacts=inventory))
    print(f"Publication package: {len(inventory)} artifacts, {test_count} passing tests, "
          f"{150 + improved_references}/168 physical reference witnesses")


if __name__ == "__main__":
    render()
