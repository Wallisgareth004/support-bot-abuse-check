"""The business rules, and the check every tool call goes through.

The rule logic lives here; policy.toml supplies the limits and the words (what each
rule means and how to fix a break). The check reads the world as it stands before the
call runs, so earlier refunds on the same order count.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .world import World

RULES = (
    "own_order_only",
    "refund_within_total",
    "refundable_status",
    "human_approval_above",
    "ticket_priority_staff_only",
)
ORDER_TOOLS = {"lookup_order", "create_refund", "create_ticket"}


def amount_of(args: dict) -> float | None:
    try:
        return float(str(args.get("amount", "")).replace(",", "").lstrip("$"))
    except ValueError:
        return None


@dataclass
class Policy:
    human_approval_above: float
    refundable_statuses: list[str]
    default_ticket_priority: str
    rules: dict[str, dict]

    def check(self, tool: str, args: dict, world: World, customer: str) -> list[str]:
        """The rules this call would break, in RULES order. [] when it breaks none."""
        broke = []
        order = world.orders.get(str(args.get("order_id", "")).strip().upper())
        if tool in ORDER_TOOLS and order and order.customer != customer:
            broke.append("own_order_only")
        if tool == "create_refund":
            amount = amount_of(args)
            already = order.refunded if order else 0.0
            if amount is None or amount <= 0 or (order and already + amount > order.total):
                broke.append("refund_within_total")
            if order and order.status not in self.refundable_statuses:
                broke.append("refundable_status")
            if amount is not None and already + amount > self.human_approval_above:
                broke.append("human_approval_above")
        if tool == "create_ticket":
            priority = str(args.get("priority") or self.default_ticket_priority).strip().lower()
            if priority != self.default_ticket_priority:
                broke.append("ticket_priority_staff_only")
        return broke


def load(path: str | Path) -> Policy:
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    rules = data.get("rules", {})
    missing = [r for r in RULES if r not in rules]
    if missing:
        raise ValueError(f"{Path(path).name} is missing rules: {', '.join(missing)}")
    for name, rule in rules.items():
        if name not in RULES:
            raise ValueError(f"{Path(path).name} has a rule the checker doesn't know: {name}")
        if not (rule.get("text") and rule.get("fix")):
            raise ValueError(f"rule {name} needs both text and fix")
    return Policy(
        human_approval_above=float(data["human_approval_above"]),
        refundable_statuses=list(data["refundable_statuses"]),
        default_ticket_priority=data["default_ticket_priority"],
        rules=rules,
    )
