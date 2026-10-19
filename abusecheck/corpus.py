"""Load the attack corpus: one TOML file per family, one [[case]] per conversation.

Attack cases name the rules an unsafe bot would break (`targets`, for the report);
the verdict itself comes from the tool-call log, whichever rule breaks. Control
cases are ordinary requests that a safe bot must still serve: they name the call
they expect (`expect_call`), which is how over-blocking shows up.
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Case:
    id: str
    family: str
    title: str
    customer: str
    turns: list[str]
    targets: list[str] = field(default_factory=list)
    setup: dict = field(default_factory=dict)
    expect_call: dict | None = None
    file: str = ""


def load(folder: str | Path) -> list[Case]:
    cases, seen = [], set()
    files = sorted(Path(folder).glob("*.toml"))
    if not files:
        raise ValueError(f"no .toml case files in {folder}")
    for path in files:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
        family = data.get("family")
        if not family:
            raise ValueError(f"{path.name}: needs a top-level family")
        for raw in data.get("case", []):
            cid = raw.get("id", "")
            if not cid:
                raise ValueError(f"{path.name}: a case has no id")
            if cid in seen:
                raise ValueError(f"{path.name}: duplicate case id {cid}")
            seen.add(cid)
            turns = raw.get("turns") or []
            if not turns or not all(isinstance(t, str) and t for t in turns):
                raise ValueError(f"{path.name}: case {cid} needs turns (a list of messages)")
            for key in ("title", "customer"):
                if not raw.get(key):
                    raise ValueError(f"{path.name}: case {cid} needs {key}")
            expect = raw.get("expect_call")
            if family == "control" and not (expect and expect.get("tool")):
                raise ValueError(f"{path.name}: control case {cid} needs expect_call with a tool")
            cases.append(
                Case(
                    id=cid, family=family, title=raw["title"], customer=raw["customer"],
                    turns=list(turns), targets=list(raw.get("targets", [])),
                    setup=dict(raw.get("setup", {})), expect_call=expect, file=path.name,
                )
            )
    return cases
