"""Command-line entrypoint for the active Desaulniers MP development track."""

import argparse
import json

from .instance import discover_instances


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("instances", help="List active benchmark instances")
    listing.add_argument("--size", type=int, choices=(25, 50, 100))
    pilot = commands.add_parser("pilot", help="Run the fixed-method development pilot")
    pilot.add_argument("--sizes", type=int, nargs="+", choices=(25, 50, 100))
    commands.add_parser("analyze-pilot", help="Audit and summarize the completed pilot")
    args = parser.parse_args(argv)
    if args.command == "instances":
        print(json.dumps([path.stem for path in discover_instances(args.size)], indent=2))
    elif args.command == "pilot":
        from scripts.run_desaulniers_pilot import run
        run(sizes=args.sizes)
    else:
        from scripts.analyze_desaulniers_pilot import analyze
        analyze()


if __name__ == "__main__":
    main()
