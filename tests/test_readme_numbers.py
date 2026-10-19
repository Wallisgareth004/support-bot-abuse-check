"""The README's headline is the measured result: re-run it and compare."""

import re

from abusecheck import corpus, runner
from abusecheck.bots.gated import GatedBot
from abusecheck.bots.naive import NaiveBot

HEADLINE = re.compile(
    r"naive bot: \*\*(\d+) of (\d+)\*\* attacks broke a rule.*?gated bot: \*\*(\d+) of (\d+)\*\*"
    r".*?served (\d+) of (\d+) controls", re.S)


def test_the_readme_headline_matches_a_fresh_run(root, world, policy):
    m = HEADLINE.search((root / "README.md").read_text())
    assert m, "headline not found in README"
    cases = corpus.load(root / "attacks")
    naive = runner.summary(runner.run_all(NaiveBot(policy), cases, world, policy))
    gated = runner.summary(runner.run_all(GatedBot(policy), cases, world, policy))
    got = tuple(int(x) for x in m.groups())
    assert got == (naive["broken"], naive["attacks"], gated["broken"], gated["attacks"],
                   gated["served"], gated["controls"])


def test_the_example_reports_match_a_fresh_run(root, world, policy):
    cases = corpus.load(root / "attacks")
    for bot in (NaiveBot(policy), GatedBot(policy)):
        s = runner.summary(runner.run_all(bot, cases, world, policy))
        text = (root / "examples" / f"report-{bot.name}.md").read_text()
        assert f"**Attacks that broke a rule: {s['broken']} of {s['attacks']}.**" in text, bot.name


def test_the_readme_test_count_is_current(root):
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
                         cwd=root, capture_output=True, text=True).stdout
    collected = int(re.search(r"(\d+) tests? collected", out).group(1))
    assert f"There are {collected} tests" in (root / "README.md").read_text()
