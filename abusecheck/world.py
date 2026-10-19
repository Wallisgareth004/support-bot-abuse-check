"""The made-up shop a check runs against: customers, orders and help articles."""

import copy
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Order:
    id: str
    customer: str
    total: float
    status: str
    refunded: float = 0.0
    notes: str = ""


@dataclass
class World:
    customers: dict[str, dict]
    orders: dict[str, Order]
    articles: dict[str, str]
    currency: str = "USD"
    tickets: list[dict] = field(default_factory=list)

    def latest_order(self, customer: str) -> str | None:
        mine = [o.id for o in self.orders.values() if o.customer == customer]
        return mine[-1] if mine else None


def load(path: str | Path) -> World:
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    orders = {
        oid: Order(
            id=oid,
            customer=o["customer"],
            total=float(o["total"]),
            status=o["status"],
            refunded=float(o.get("refunded", 0.0)),
            notes=o.get("notes", ""),
        )
        for oid, o in data.get("orders", {}).items()
    }
    for o in orders.values():
        if o.customer not in data.get("customers", {}):
            raise ValueError(f"order {o.id} names unknown customer {o.customer}")
    return World(
        customers=dict(data.get("customers", {})),
        orders=orders,
        articles=dict(data.get("articles", {})),
        currency=data.get("currency", "USD"),
    )


def with_setup(world: World, setup: dict) -> World:
    """A fresh copy of the world with a case's changes (order notes, article text)."""
    w = copy.deepcopy(world)
    for oid, note in (setup or {}).get("order_notes", {}).items():
        if oid not in w.orders:
            raise ValueError(f"setup names unknown order {oid}")
        w.orders[oid].notes = note
    for slug, text in (setup or {}).get("articles", {}).items():
        w.articles[slug] = text
    return w
