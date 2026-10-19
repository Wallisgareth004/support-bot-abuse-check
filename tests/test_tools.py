"""The toolbox the harness owns: every call is logged with the rules it broke."""

from abusecheck.tools import ToolBox


def test_a_lookup_returns_the_order_with_its_notes(world, policy):
    world.orders["A1001"].notes = "leave at the door"
    tb = ToolBox(world, "C100", policy)
    out = tb.call("lookup_order", order_id="A1001")
    assert out["status"] == "delivered" and out["notes"] == "leave at the door"
    assert out["email"] == "ana@example.com"
    assert tb.log[0].executed and tb.log[0].broke == []


def test_a_refund_is_applied_and_counted(world, policy):
    tb = ToolBox(world, "C100", policy)
    tb.call("create_refund", order_id="A1001", amount="50")
    tb.call("create_refund", order_id="A1001", amount=40)
    assert world.orders["A1001"].refunded == 90
    assert tb.log[1].broke == ["refund_within_total"]


def test_without_a_gate_a_rule_breaking_call_runs_and_is_marked(world, policy):
    tb = ToolBox(world, "C100", policy)
    out = tb.call("lookup_order", order_id="A2001")
    assert "error" not in out
    assert tb.log[0].executed and tb.log[0].broke == ["own_order_only"]


def test_with_a_gate_a_rule_breaking_call_is_blocked_and_not_applied(world, policy):
    tb = ToolBox(world, "C100", policy, gate=True)
    out = tb.call("create_refund", order_id="A2001", amount=120)
    assert "blocked" in out["error"]
    assert world.orders["A2001"].refunded == 0
    assert not tb.log[0].executed and tb.log[0].broke == ["own_order_only"]


def test_with_a_gate_a_clean_call_still_runs(world, policy):
    tb = ToolBox(world, "C100", policy, gate=True)
    tb.call("create_refund", order_id="A1001", amount=80)
    assert tb.log[0].executed and world.orders["A1001"].refunded == 80


def test_an_unknown_tool_or_order_is_an_error_not_a_break(world, policy):
    tb = ToolBox(world, "C100", policy)
    assert "error" in tb.call("delete_customer", customer="C200")
    assert "error" in tb.call("lookup_order", order_id="Z9999")
    assert all(c.broke == [] for c in tb.log)


def test_reported_calls_from_an_outside_bot_are_checked_and_applied(world, policy):
    tb = ToolBox(world, "C100", policy)
    tb.report("create_refund", {"order_id": "A2002", "amount": 900})
    assert tb.log[0].executed and tb.log[0].reported
    assert tb.log[0].broke == ["own_order_only", "human_approval_above"]
    assert world.orders["A2002"].refunded == 900


def test_tickets_and_escalations_get_ids(world, policy):
    tb = ToolBox(world, "C100", policy)
    assert tb.call("create_ticket", subject="late", order_id="A1001")["ticket"] == "T1"
    assert tb.call("escalate_to_human", reason="big refund")["queued"] is True
    assert tb.call("get_article", slug="returns")["text"].startswith("Refunds")
