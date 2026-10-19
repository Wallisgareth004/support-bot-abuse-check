"""The support bot's tools, owned by the harness. Every call is logged with the rules
it broke. With gate=True a rule-breaking call is blocked instead of run: that is the
fix pattern the gated demo bot shows (the check in code, not in the prompt)."""

from dataclasses import dataclass, field

from .policy import Policy, amount_of
from .world import World

TOOLS = ("lookup_order", "create_refund", "create_ticket", "escalate_to_human", "get_article")


@dataclass
class Call:
    tool: str
    args: dict
    executed: bool
    broke: list[str] = field(default_factory=list)
    result: dict = field(default_factory=dict)
    reported: bool = False


class ToolBox:
    def __init__(self, world: World, customer: str, policy: Policy, gate: bool = False):
        self.world, self.customer, self.policy, self.gate = world, customer, policy, gate
        self.log: list[Call] = []

    def call(self, tool: str, **args) -> dict:
        if tool not in TOOLS:
            return self._record(tool, args, True, [], {"error": f"no tool called {tool}"}).result
        broke = self.policy.check(tool, args, self.world, self.customer)
        if broke and self.gate:
            result = {"error": f"blocked by policy: {', '.join(broke)}"}
            return self._record(tool, args, False, broke, result).result
        return self._record(tool, args, True, broke, self._run(tool, args)).result

    def report(self, tool: str, args: dict) -> None:
        """A call an outside bot says it made: checked and applied, never gated."""
        broke = self.policy.check(tool, args, self.world, self.customer) if tool in TOOLS else []
        result = self._run(tool, args) if tool in TOOLS else {"error": f"no tool called {tool}"}
        self._record(tool, args, True, broke, result).reported = True

    def _record(self, tool, args, executed, broke, result) -> Call:
        self.log.append(Call(tool, dict(args), executed, list(broke), result))
        return self.log[-1]

    def _run(self, tool: str, args: dict) -> dict:
        w = self.world
        order = w.orders.get(str(args.get("order_id", "")).strip().upper())
        if tool == "lookup_order":
            if not order:
                return {"error": "no such order"}
            who = w.customers.get(order.customer, {})
            return {
                "order_id": order.id, "customer": order.customer, "name": who.get("name", ""),
                "email": who.get("email", ""), "total": order.total, "refunded": order.refunded,
                "status": order.status, "notes": order.notes,
            }
        if tool == "create_refund":
            amount = amount_of(args)
            if not order or amount is None:
                return {"error": "refund needs a known order_id and a numeric amount"}
            order.refunded += amount
            return {"refunded": amount, "order_id": order.id}
        if tool == "create_ticket":
            ticket = {"ticket": f"T{len(w.tickets) + 1}", **args}
            w.tickets.append(ticket)
            return {"ticket": ticket["ticket"]}
        if tool == "escalate_to_human":
            return {"queued": True}
        text = w.articles.get(str(args.get("slug", "")))
        return {"text": text} if text is not None else {"error": "no such article"}
