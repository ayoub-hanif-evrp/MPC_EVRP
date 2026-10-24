"""Render supplemental figures from saved audited aggregates, without optimization."""

from hashlib import sha256

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

from evrp.storage import ROOT, load_json, save_json, writable_path

OUTPUT=ROOT/"results/desaulniers/targeted_service_v1"


def render():
    diagnosis=load_json(OUTPUT/"diagnosis/aggregate.json")
    diagnostic_manifest=load_json(OUTPUT/"diagnosis/manifest.json")
    labels={
        ("insertion_screen","time_window"):"Time-window screen rejection",
        ("insertion_screen","capacity"):"Capacity screen rejection",
        ("insertion_screen","feasible"):"Screen passed (not feasibility proof)",
        ("route_decode","feasible"):"Route reconstruction succeeded",
        ("route_decode","bounded_decoder_failure"):"Bounded reconstruction failed",
        ("charging_connection_failure",""):"Charging connection attempt failed",
    }
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    counts=diagnosis["event_counts"]
    axes[0].barh([labels.get((r["kind"],r["reason"]),r["kind"]) for r in counts],
                  [r["events"] for r in counts],color="#4d7d99")
    axes[0].tick_params(labelsize=8)
    axes[0].set(xlabel="Heuristic events, not missed customers")
    statuses=diagnosis["candidate_statuses"]
    axes[1].bar(["Bounded\nreconstruction\nfailure","Validated\ncontinuation","Canonical\nimprovement"],
                [statuses["bounded_route_reconstruction_failure"],statuses["physically_validated"],
                 sum(r["improved"] for r in diagnostic_manifest["records"])],
                color=["#b44345","#267a66","#4d7d99"])
    axes[1].tick_params(axis="x",labelsize=9)
    axes[1].set(ylabel="Counterfactual alternatives")
    fig.tight_layout()
    fig.savefig(writable_path(OUTPUT/"diagnosis/paper/diagnosis.png"),dpi=300)
    plt.close(fig)
    for stage in ("development","holdout"):
        path=OUTPUT/stage/"analysis.json"
        if not path.exists():
            continue
        data=load_json(path)
        paper=OUTPUT/stage/"paper"
        methods=list(dict.fromkeys(s["method"] for s in data["summaries"]))
        for name,field,ylabel in (("complete_service","complete","Complete-service change (pp)"),
                                 ("hundred_customer_service","hundred","100-customer service change (pp)")):
            fig,axes=plt.subplots(1,len(methods),figsize=(5*len(methods),4),squeeze=False)
            for ax,method in zip(axes[0],methods):
                summaries=[s for s in data["summaries"] if s["method"]==method]
                values=[]
                for summary in summaries:
                    if field=="complete":
                        values.append(100*(summary["enhanced_complete"]-summary["original_complete"]))
                    else:
                        rows=[r for r in data["pairs"] if r["method"]==method and
                              r["variant"]==summary["variant"] and r["size"]==100]
                        values.append(100*sum(r["delta"] for r in rows)/sum(r["size"] for r in rows))
                ax.bar([s["variant"] for s in summaries],values,
                       color=["#267a66" if v>=0 else "#b44345" for v in values])
                ax.axhline(0,color="#30363d",linewidth=.8)
                ax.set(title=method,ylabel=ylabel)
                ax.tick_params(axis="x",labelrotation=25,labelsize=8)
            fig.tight_layout()
            fig.savefig(writable_path(paper/f"{name}.png"),dpi=300)
            plt.close(fig)
    artifacts=[]
    for path in sorted(OUTPUT.rglob("*.md"))+sorted(OUTPUT.rglob("*.png")):
        if path.suffix==".png":
            with Image.open(path) as image:
                if min(image.info.get("dpi",(0,0)))<299.9:
                    raise ValueError("Every publication figure must be at least 300 dpi")
                if all(low==high for low,high in image.convert("RGB").getextrema()):
                    raise ValueError("Blank publication figure")
        artifacts.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha256(path.read_bytes()).hexdigest()))
    save_json(OUTPUT/"paper_inventory.json",dict(artifacts=artifacts))
    print(f"Verified publication artifacts: {len(artifacts)} Markdown/PNG files",flush=True)


if __name__=="__main__":
    render()
