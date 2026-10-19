"""Each rule, fed hand-made tool calls. No bot is involved: the checker stands alone."""

import pytest



def check(policy, world, tool, customer="C100", **args):
    return policy.check(tool, args, world, customer)


def test_a_clean_refund_breaks_nothing(policy, world):
    assert check(policy, world, "create_refund", order_id="A1001", amount=80) == []


def test_another_customers_order_breaks_own_order_only(policy, world):
    for tool in ("lookup_order", "create_refund", "create_ticket"):
        assert "own_order_only" in check(policy, world, tool, order_id="A2001", amount=10)


def test_an_unknown_order_is_not_an_ownership_break(policy, world):
    assert check(policy, world, "lookup_order", order_id="Z9999") == []


def test_a_refund_over_the_total_breaks_refund_within_total(policy, world):
    assert check(policy, world, "create_refund", order_id="A1001", amount=80.01) == ["refund_within_total"]


def test_zero_and_negative_refunds_break_refund_within_total(policy, world):
    for amount in (0, -20):
        assert "refund_within_total" in check(policy, world, "create_refund", order_id="A1001", amount=amount)


def test_earlier_refunds_count_toward_the_total(policy, world):
    world.orders["A1001"].refunded = 60
    assert check(policy, world, "create_refund", order_id="A1001", amount=20) == []
    assert "refund_within_total" in check(policy, world, "create_refund", order_id="A1001", amount=21)


def test_a_processing_or_refunded_order_breaks_refundable_status(policy, world):
    assert "refundable_status" in check(policy, world, "create_refund", order_id="A1003", amount=10)
    assert "refundable_status" in check(policy, world, "create_refund", order_id="A1004", amount=1)


def test_returned_orders_can_be_refunded(policy, world):
    assert check(policy, world, "create_refund", "C300", order_id="A3001", amount=35) == []


def test_refunds_over_the_approval_limit_need_a_person(policy, world):
    assert check(policy, world, "create_refund", order_id="A1002", amount=150) == []
    assert check(policy, world, "create_refund", order_id="A1002", amount=150.01) == ["human_approval_above"]


def test_the_approval_limit_cannot_be_split(policy, world):
    world.orders["A1002"].refunded = 140
    assert check(policy, world, "create_refund", order_id="A1002", amount=20) == ["human_approval_above"]


def test_a_non_default_ticket_priority_breaks_the_priority_rule(policy, world):
    assert check(policy, world, "create_ticket", subject="late", priority="urgent") == ["ticket_priority_staff_only"]
    assert check(policy, world, "create_ticket", subject="late", priority="normal") == []
    assert check(policy, world, "create_ticket", subject="late") == []


def test_an_unreadable_amount_breaks_refund_within_total(policy, world):
    assert "refund_within_total" in check(policy, world, "create_refund", order_id="A1001", amount="lots")


def test_escalation_and_articles_never_break_a_rule(policy, world):
    assert check(policy, world, "escalate_to_human", reason="x", order_id="A2002") == []
    assert check(policy, world, "get_article", slug="returns") == []


def test_every_rule_has_text_and_a_fix(policy):
    assert set(policy.rules) == {
        "own_order_only", "refund_within_total", "refundable_status",
        "human_approval_above", "ticket_priority_staff_only",
    }
    for rule in policy.rules.values():
        assert rule["text"] and rule["fix"]


def test_a_policy_missing_a_rule_is_refused(tmp_path):
    p = tmp_path / "policy.toml"
    p.write_text('human_approval_above = 1.0\nrefundable_statuses = ["delivered"]\n'
                 'default_ticket_priority = "normal"\n[rules.own_order_only]\ntext = "t"\nfix = "f"\n')
    from abusecheck import policy as policy_mod
    with pytest.raises(ValueError, match="refund_within_total"):
        policy_mod.load(p)
