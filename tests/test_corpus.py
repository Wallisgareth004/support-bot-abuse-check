"""The shipped attack corpus, and the loader's refusals."""

import pytest

from abusecheck import corpus

FAMILIES = {"direct", "fake-authority", "injection", "tampering", "escalation", "encoding"}


@pytest.fixture
def cases(root):
    return corpus.load(root / "attacks")


def test_forty_attacks_in_six_families(cases):
    attacks = [c for c in cases if c.family != "control"]
    assert len(attacks) == 40
    assert {c.family for c in attacks} == FAMILIES


def test_six_controls_each_expect_a_call(cases):
    controls = [c for c in cases if c.family == "control"]
    assert len(controls) == 6
    assert all(c.expect_call and c.expect_call["tool"] for c in controls)


def test_ids_are_unique_and_every_case_targets_known_rules(cases, policy, world):
    assert len({c.id for c in cases}) == len(cases)
    for c in cases:
        assert c.turns, c.id
        assert c.customer in world.customers, c.id
        assert set(c.targets) <= set(policy.rules), c.id
        if c.family != "control":
            assert c.targets, c.id


def test_every_case_setup_applies_to_the_world(cases, world):
    from abusecheck import world as world_mod
    for c in cases:
        world_mod.with_setup(world, c.setup)


def write(tmp_path, body):
    (tmp_path / "x.toml").write_text(body)
    return tmp_path


def test_a_case_without_turns_is_refused(tmp_path):
    d = write(tmp_path, 'family = "direct"\n[[case]]\nid = "x1"\ntitle = "t"\ncustomer = "C100"\ntargets = ["own_order_only"]\n')
    with pytest.raises(ValueError, match="x1.*turns"):
        corpus.load(d)


def test_a_duplicate_id_is_refused(tmp_path):
    case = '[[case]]\nid = "x1"\ntitle = "t"\ncustomer = "C100"\nturns = ["hi"]\ntargets = ["own_order_only"]\n'
    d = write(tmp_path, 'family = "direct"\n' + case + case)
    with pytest.raises(ValueError, match="duplicate.*x1"):
        corpus.load(d)


def test_a_file_without_a_family_is_refused(tmp_path):
    d = write(tmp_path, '[[case]]\nid = "x1"\ntitle = "t"\ncustomer = "C100"\nturns = ["hi"]\n')
    with pytest.raises(ValueError, match="family"):
        corpus.load(d)


def test_a_control_without_an_expected_call_is_refused(tmp_path):
    d = write(tmp_path, 'family = "control"\n[[case]]\nid = "c1"\ntitle = "t"\ncustomer = "C100"\nturns = ["hi"]\n')
    with pytest.raises(ValueError, match="c1.*expect_call"):
        corpus.load(d)
