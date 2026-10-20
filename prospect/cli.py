"""Command line entry point: prospect priors --list-placeholders."""

import argparse
import sys

from prospect.priors import config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prospect")
    commands = parser.add_subparsers(dest="command", required=True)
    priors = commands.add_parser("priors", help="check model inputs in config/")
    priors.add_argument(
        "--list-placeholders",
        action="store_true",
        help="list every value that is not from a cited source",
    )
    scorer = commands.add_parser(
        "score", help="score sites by value per battery block (make score)"
    )
    scorer.add_argument("--installed-cost", type=float, help="per block, dollars")
    scorer.add_argument(
        "--min-host-benefit", type=float, help="per block, dollars a year"
    )
    scorer.add_argument("--itc", action="store_true", help="apply the ITC")
    args = parser.parse_args(argv)
    if args.command == "score":
        from prospect.model import run

        return run.main(args.installed_cost, args.min_host_benefit, args.itc)

    try:
        configs = config.load()
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    if args.list_placeholders:
        rows = config.placeholders(configs)
        print(f"{len(rows)} placeholders in config/:")
        for name, path, value, note in rows:
            print(f"\n{name}.yaml {path}" + (f" = {value}" if value else ""))
            print(f"  {note}")
    else:
        print("config/ is clean: every value is sourced or a noted placeholder.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
