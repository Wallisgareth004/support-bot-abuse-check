from abusecheck import world as world_mod


def test_the_shipped_world_loads(world):
    assert world.orders["A1001"].customer == "C100"
    assert world.orders["A1004"].refunded == 45.0
    assert world.orders["A2002"].total == 900.0
    assert set(world.articles) == {"returns", "shipping"}


def test_setup_works_on_a_copy(world):
    case_world = world_mod.with_setup(world, {"order_notes": {"A1001": "hello"}, "articles": {"returns": "new"}})
    assert case_world.orders["A1001"].notes == "hello"
    assert case_world.articles["returns"] == "new"
    assert world.orders["A1001"].notes == ""
    assert world.articles["returns"].startswith("Refunds go back")


def test_setup_naming_an_unknown_order_is_refused(world):
    import pytest
    with pytest.raises(ValueError, match="Z9999"):
        world_mod.with_setup(world, {"order_notes": {"Z9999": "x"}})


def test_latest_order_is_the_last_one_listed_for_the_customer(world):
    assert world.latest_order("C100") == "A1004"
    assert world.latest_order("C999") is None
