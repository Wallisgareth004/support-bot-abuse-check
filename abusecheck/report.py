"""The Markdown report: the headline, a table per family, the controls, then one
finding per attack that broke a rule (conversation, the call, the rule, the fix)."""

import datetime
import html

from .policy import Policy
from .runner import Result, summary


def _quote(text: str) -> str:
    """Customer and bot text as a one-line, HTML-escaped quote: it can't open a
    heading, a code block or a tag in the report."""
    return html.escape(" ".join(text.split()), quote=False).replace("`", "&#96;")


def _call(c) -> str:
    def fmt(v):
        return f'"{v}"' if isinstance(v, str) else repr(v)

    args = ", ".join(f"{k}={fmt(v)}" for k, v in c.args.items())
    return f"`{c.tool}({args})`".replace("\n", " ")


def markdown(bot_name: str, results: list[Result], policy: Policy, date: str | None = None) -> str:
    s = summary(results)
    date = date or datetime.date.today().isoformat()
    out = [
        f"# Support-bot abuse check: {_quote(bot_name)}",
        "",
        f"Run on {date} · {s['attacks']} attacks · {s['controls']} controls · rules: policy.toml",
        "",
        f"**Attacks that broke a rule: {s['broken']} of {s['attacks']}.** "
        f"Controls served: {s['served']} of {s['controls']}.",
        "",
        "A verdict comes from the tool calls that actually ran, never from what the bot said.",
        "",
        "| Family | Attacks | Held | Broke a rule |",
        "|---|---|---|---|",
    ]
    for fam, f in s["families"].items():
        out.append(f"| {fam} | {f['attacks']} | {f['held']} | {f['broken']} |")
    controls = [r for r in results if r.case.family == "control"]
    if controls:
        out += ["", "## Controls (ordinary requests that must still work)", "",
                "| Case | Expected call | Result |", "|---|---|---|"]
        for r in controls:
            out.append(f"| {r.case.id} · {_quote(r.case.title)} | `{r.case.expect_call['tool']}` | {r.verdict} |")
    broken = [r for r in results if r.case.family != "control" and r.verdict == "broken"]
    out += ["", "## Findings", ""]
    if not broken:
        out.append("No attack broke a rule.")
    for r in broken:
        out += ["", f"### {r.case.id} · {_quote(r.case.title)} · broke: {', '.join(r.broke)}", "",
                f"Family: {r.case.family}", ""]
        planted = [f"- Order {oid} note: {_quote(t)}" for oid, t in r.case.setup.get("order_notes", {}).items()]
        planted += [f"- Help article '{slug}': {_quote(t)}" for slug, t in r.case.setup.get("articles", {}).items()]
        if planted:
            out += ["**Planted before the conversation**", "", *planted, ""]
        out += ["**Conversation**", ""]
        for said, reply in r.transcript:
            out += [f"> **Customer:** {_quote(said)}", ">", f"> **Bot:** {_quote(reply)}", ">"]
        out[-1] = ""
        out += ["**Tool calls that ran and broke a rule**", ""]
        for c in r.breaking_calls:
            out.append(f"- {_call(c)} → {', '.join(c.broke)}")
        if r.blocked:
            out += ["", "**Blocked before they ran**", ""]
            out += [f"- {_call(c)} → {', '.join(c.broke)}" for c in r.blocked]
        for rule in r.broke:
            out += ["", f"**Rule `{rule}`:** {policy.rules[rule]['text']}", "",
                    f"**Fix:** {policy.rules[rule]['fix']}"]
    return "\n".join(out) + "\n"
