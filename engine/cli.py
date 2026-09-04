"""Command-line front end for the program engine.

    python -m engine.cli --goal hypertrophy --level intermediate \
        --days 4 --equipment home_dumbbell --minutes 60 --lang tr

Prints a readable plan by default, or the full JSON with ``--json``.
"""

from __future__ import annotations

import argparse
import json
import sys

from .catalog import EQUIPMENT_PROFILES
from .prescription import GOALS, LEVELS
from .programs import Profile, generate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="engine.cli",
                                     description="Generate a training block.")
    parser.add_argument("--goal", choices=GOALS, default="hypertrophy")
    parser.add_argument("--level", choices=LEVELS, default="beginner")
    parser.add_argument("--days", type=int, default=3, dest="days_per_week",
                        help="training days per week (2-6)")
    parser.add_argument("--equipment", default="full_gym",
                        choices=sorted(EQUIPMENT_PROFILES))
    parser.add_argument("--minutes", type=int, default=60,
                        dest="session_minutes", help="minutes per session")
    parser.add_argument("--weeks", type=int, default=4)
    parser.add_argument("--lang", default="en", dest="language")
    parser.add_argument("--seed", type=int, default=None,
                        help="fix the seed to reproduce a plan")
    parser.add_argument("--exclude", nargs="*", default=[],
                        dest="exclude_patterns",
                        help="movement patterns to leave out, e.g. hinge")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def render(program: dict) -> str:
    lines = [
        f"{program['split']}  ·  {program['profile']['goal']}  ·  "
        f"{program['profile']['level']}  ·  {program['profile']['weeks']} weeks",
        f"progression: {program['progression_model']}",
    ]
    for week in program["weeks"]:
        tag = "  (deload)" if week["is_deload"] else ""
        lines.append(f"\n=== Week {week['week']}{tag} ===")
        lines.append(f"    {week['guidance']}")
        for day in week["days"]:
            lines.append(f"\n  {day['name']}  (~{day['estimated_minutes']} min)")
            for entry in day["exercises"]:
                rx = entry["prescription"]
                lines.append(
                    f"    {entry['exercise']['name'][:44]:46}"
                    f"{rx['sets']}x{rx['rep_min']}-{rx['rep_max']}  "
                    f"rest {rx['rest_seconds']}s  RIR {rx['rir']}"
                )
        volume = ", ".join(f"{part} {sets}"
                           for part, sets in week["weekly_set_volume"].items())
        lines.append(f"\n  weekly sets: {volume}")
    lines.append(f"\n{program['attribution']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    profile = Profile(
        goal=args.goal, level=args.level, days_per_week=args.days_per_week,
        equipment=args.equipment, session_minutes=args.session_minutes,
        weeks=args.weeks, language=args.language, seed=args.seed,
        exclude_patterns=tuple(args.exclude_patterns),
    )
    try:
        program = generate(profile)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(program, ensure_ascii=False, indent=2)
          if args.as_json else render(program))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
