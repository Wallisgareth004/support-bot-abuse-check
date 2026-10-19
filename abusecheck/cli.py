"""python -m abusecheck run --bot naive|gated|<http url>|py:module:function [options]

Exit codes: 0 every attack held and every control was served; 1 an attack broke a
rule or a control wasn't served; 2 the check couldn't run.
"""

import argparse
import json
import sys
from pathlib import Path

from . import adapters, corpus, policy, report, runner, world
from .bots.gated import GatedBot
from .bots.naive import NaiveBot

ROOT = Path(__file__).resolve().parent.parent


def make_bot(spec: str, pol, authorised: bool):
    if spec == "naive":
        return NaiveBot(pol)
    if spec == "gated":
        return GatedBot(pol)
    if spec.startswith(("http://", "https://")):
        return adapters.HttpBot(spec, authorised=authorised)
    if spec.startswith("py:"):
        return adapters.PythonBot(spec[3:])
    raise ValueError(f"unknown bot {spec!r}: use naive, gated, an http(s) URL or py:module:function")


def to_json(bot_name, results):
    return {
        "bot": bot_name,
        "summary": runner.summary(results),
        "cases": [
            {
                "id": r.case.id, "family": r.case.family, "title": r.case.title,
                "verdict": r.verdict, "broke": r.broke,
                "transcript": [list(t) for t in r.transcript],
                "calls": [{"tool": c.tool, "args": c.args, "executed": c.executed,
                           "broke": c.broke, "reported": c.reported} for c in r.calls],
            }
            for r in results
        ],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m abusecheck")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run the corpus against a bot")
    run.add_argument("--bot", required=True, help="naive, gated, an http(s) URL, or py:module:function")
    run.add_argument("--authorised", action="store_true",
                     help="the URL is not this machine and you have written permission to test it")
    run.add_argument("--cases", default=str(ROOT / "attacks"))
    run.add_argument("--policy", default=str(ROOT / "policy.toml"))
    run.add_argument("--world", default=str(ROOT / "world.toml"))
    run.add_argument("--only", default="", help="run only cases whose id starts with this")
    run.add_argument("--report", help="write the Markdown report here")
    run.add_argument("--json", help="write every case, call and verdict here as JSON")
    a = ap.parse_args(argv)
    try:
        pol = policy.load(a.policy)
        shop = world.load(a.world)
        cases = [c for c in corpus.load(a.cases) if c.id.startswith(a.only)]
        if not cases:
            raise ValueError(f"no case id starts with {a.only!r}")
        bot = make_bot(a.bot, pol, a.authorised)
        results = runner.run_all(bot, cases, shop, pol)
    except (OSError, ValueError, adapters.BotError) as e:
        print(f"abusecheck: {e}", file=sys.stderr)
        return 2
    s = runner.summary(results)
    print(f"{bot.name}: {s['broken']} of {s['attacks']} attacks broke a rule · "
          f"controls served {s['served']} of {s['controls']}")
    for fam, f in s["families"].items():
        print(f"  {fam:15} {f['broken']} of {f['attacks']} broke a rule")
    if a.report:
        Path(a.report).write_text(report.markdown(bot.name, results, pol), encoding="utf-8")
        print(f"report: {a.report}")
    if a.json:
        Path(a.json).write_text(json.dumps(to_json(bot.name, results), indent=2), encoding="utf-8")
        print(f"json: {a.json}")
    clean = s["broken"] == 0 and s["served"] == s["controls"]
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
