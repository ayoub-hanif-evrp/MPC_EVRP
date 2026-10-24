"""Resume exact development evidence, then the corrected conditional MP holdout."""

from time import perf_counter

from evrp.experiments import load_config
from scripts import run_targeted_service as development
from scripts import run_targeted_mp_holdout as holdout
from scripts.analyze_targeted_service import analyze,finalize
from scripts.audit_targeted_inventory import audit
from scripts.report_targeted_losses import report
from scripts.render_targeted_supplement import render


def main():
    deadline=perf_counter()+load_config(development.CONFIG)["maximum_campaign_hours"]*3600
    protocol=development.frozen("development")
    if not development.run("development",protocol,deadline):
        return print("Development paused at scenario boundary; resume this same command")
    selection=analyze("development")
    if selection["selected_variant"] is not None:
        protocol=holdout.freeze()
        if not holdout.run(protocol,deadline):
            return print("Holdout paused at scenario boundary; resume this same command")
        analyze("holdout")
    audit()
    finalize(selection)
    report()
    render()
    print("Targeted study, independent audits and publication reporting complete",flush=True)


if __name__=="__main__":
    main()
