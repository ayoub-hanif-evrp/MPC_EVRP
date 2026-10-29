"""Preview a future study without creating data or running an experiment."""

import argparse
import json
from pathlib import Path
from yaml import YAMLError

from evrp.experiments import load_config
from evrp.storage import ROOT

from .paths import OUTPUT_KINDS, output_dir, resolve_config, validate_study_id


BASELINE_METHODS = frozenset({"MPC_COMPLETION", "MPC_MCTS", "MPC_ALNS", "MPC_HGS", "MPC_ACS"})
SETTING_KEYS = ("charging_policy", "charging_mode", "fleet_mode", "sizes", "families",
                "instances", "dynamicities", "scenario_seeds", "total_planning_time_limit",
                "engineering_watchdog_seconds", "whole_worker_timeout_seconds")


def inspect(study: str, config: str | Path, method: str, repo_root: Path = ROOT) -> dict:
    validate_study_id(study)
    if method not in BASELINE_METHODS:
        raise ValueError(f"Not one of the five baseline methods: {method!r}")
    root = Path(repo_root).resolve()
    config_file = resolve_config(config, root)
    selected = load_config(config_file)
    configured_methods = selected.get("methods")
    if configured_methods is not None:
        if not isinstance(configured_methods, list) or not all(isinstance(name, str) for name in configured_methods):
            raise ValueError("Configuration methods must be a list of names")
        if method not in configured_methods:
            raise ValueError(f"Method {method} is not listed in the selected configuration")
    base = {}
    base_file = selected.get("base_controller")
    if base_file is not None:
        if not isinstance(base_file, str):
            raise ValueError("base_controller must name a YAML configuration")
        base = load_config(resolve_config(base_file, root))

    settings = {}
    for key in SETTING_KEYS:
        if key in selected:
            settings[key] = {"value": selected[key], "source": "study_config"}
        elif key in base:
            settings[key] = {"value": base[key], "source": "base_controller"}
        else:
            settings[key] = {"value": None, "source": "not_specified"}

    return {
        "study": study,
        "config": str(config_file),
        "base_controller": str(resolve_config(base_file, root)) if base_file is not None else None,
        "benchmark": str(root / "data" / "opre.2016.1535-sm-data" / "instances" / "instances_format_1"),
        "algorithm": {"value": method, "source": "command_line"},
        "outputs": {kind: str(output_dir(study, kind, root)) for kind in sorted(OUTPUT_KINDS)},
        "settings": settings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--method", required=True)
    args = parser.parse_args()
    try:
        summary = inspect(args.study, args.config, args.method)
    except (ValueError, FileNotFoundError, OSError, YAMLError) as error:
        parser.error(str(error))
    print(json.dumps(summary, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
