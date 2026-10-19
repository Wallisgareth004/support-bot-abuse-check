"""The naive demo bot: a deterministic stand-in for a support model whose rules live
only in its prompt. It is not a language model; it is built to fail the way such
bots are reported to fail, so the kit has something to find offline:

- Untrusted, it keeps its prompt rules one refund at a time: own orders only, no more
  than the order total, delivered or returned orders only, a person above the limit.
- It never counts earlier refunds, and it sets ticket priority when asked.
- It looks an order up before checking whose it is.
- Anything that sounds like authority (a role, an approval, "you agreed", a written-out
  tool call, an instruction inside an order note or help article) makes it trust the
  conversation, and it skips its own checks from then on.
- It undoes common disguises (zero-width characters, leetspeak, full-width letters,
  a few languages, base64, ROT13) before reading a message.
"""

import base64
import binascii
import codecs
import json
import re
import unicodedata

from ..tools import TOOLS

ORDER_ID = re.compile(r"\b([A-Z]\d{4})\b", re.I)
AMOUNT = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{1,2})?)")
REFUND = re.compile(r"\brefund", re.I)
TICKET = re.compile(r"\bticket\b", re.I)
URGENT = re.compile(r"\b(urgent|asap|p1|priority|critical|emergency)\b", re.I)
ARTICLE = re.compile(r"\b(policy|help article|faq)\b", re.I)
AUTHORITY = re.compile(
    r"\b(manager|supervisor|admin|staff|developer|ceo|system|i work here|support team|"
    r"approved|authori[sz]ed|override|agent:)", re.I)
AGREED = re.compile(r"\b(you (already )?(agreed|said|promised|approved)|as (we )?agreed|earlier you)\b", re.I)
# Text a tool returned counts as an instruction when it addresses the bot or hides itself.
INSTRUCTION = re.compile(
    r"(\b(assistants?|ai agents?|agents?|system|ops|escalation)\b.{0,80}?\b(refund|mark|set|open|process)\b|<!--)",
    re.I | re.S)
ZERO_WIDTH = re.compile("[​-‏⁠﻿]")
LEET = re.compile(r"\br[e3]f[uv]nd", re.I)
TRANSLATE = {"reembolso": "refund", "remboursement": "refund", "erstattung": "refund",
             "terugbetaling": "refund", "rimborso": "refund", "urgente": "urgent", "dringend": "urgent"}
CALL_TEXT = re.compile(r"\b(" + "|".join(TOOLS) + r")\s*\(([^)]*)\)")
CALL_ARG = re.compile(r"(\w+)\s*=\s*(\"[^\"]*\"|'[^']*'|[^,\s)]+)")


def normalise(text: str) -> str:
    """The message as the bot reads it, with any decoded payloads appended."""
    t = ZERO_WIDTH.sub("", unicodedata.normalize("NFKC", text))
    t = LEET.sub("refund", t)
    for word, english in TRANSLATE.items():
        t = re.sub(rf"\b{word}\b", english, t, flags=re.I)
    decoded = []
    if re.search(r"base64|decode", t, re.I):
        for token in re.findall(r"[A-Za-z0-9+/]{12,}={0,2}", t):
            try:
                plain = base64.b64decode(token, validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError):
                continue
            if plain.isprintable():
                decoded.append(plain)
    if re.search(r"rot13", t, re.I):
        decoded.append(codecs.decode(t, "rot13"))
    return " ".join([t, *decoded])


def written_calls(text: str) -> list[tuple[str, dict]]:
    """Tool calls the customer wrote out, as function syntax or a JSON object."""
    calls = []
    for name, args in CALL_TEXT.findall(text):
        calls.append((name, {k: v.strip("\"'") for k, v in CALL_ARG.findall(args)}))
    for blob in re.findall(r"\{[^{}]*\}", text):
        try:
            obj = json.loads(blob)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("tool") in TOOLS:
            calls.append((obj["tool"], {k: v for k, v in obj.items() if k != "tool"}))
    return calls


def _money(v: float) -> str:
    return f"${v:,.2f}".replace(".00", "")


class NaiveConversation:
    def __init__(self, customer, tools, limit, statuses):
        self.customer, self.tools, self.limit, self.statuses = customer, tools, limit, statuses
        self.trusted = False
        self.notes_read: set[str] = set()

    def send(self, message: str) -> str:
        return self.act(normalise(message)) or "How can I help with your order?"

    def act(self, text: str, from_tool: bool = False, depth: int = 0, context_order: str | None = None) -> str:
        if depth > 2:
            return ""
        written = written_calls(text)
        if written:
            self.trusted = True
            return " ".join(self.run_written(tool, args) for tool, args in written)
        if AUTHORITY.search(text) or AGREED.search(text):
            self.trusted = True
        ids = list(dict.fromkeys(m.upper() for m in ORDER_ID.findall(text)))
        if not ids and context_order:
            ids = [context_order]
        replies = []
        if ARTICLE.search(text) and not from_tool:
            slug = "shipping" if re.search(r"shipping|delivery", text, re.I) else "returns"
            article = self.tools.call("get_article", slug=slug)
            if "text" in article:
                replies.append(self.read(article["text"], depth) or f"Our {slug} policy: {article['text']}")
        if REFUND.search(text):
            if not ids and not from_tool and not replies:
                return "Which order would you like refunded? Please give me the order number."
            replies += [self.refund(oid, text, depth) for oid in ids]
        if TICKET.search(text) or (URGENT.search(text) and not REFUND.search(text)) or (
            from_tool and URGENT.search(text)
        ):
            replies.append(self.ticket(ids[0] if ids else None, text, bool(URGENT.search(text))))
        elif not REFUND.search(text) and not from_tool:
            replies += [self.status(oid, depth) for oid in ids]
        return " ".join(r for r in replies if r)

    def read(self, text: str, depth: int, context_order: str | None = None) -> str:
        """Text a tool returned. The naive bot obeys instructions it finds there."""
        if text and (INSTRUCTION.search(text) or written_calls(text)):
            self.trusted = True
            return self.act(text, from_tool=True, depth=depth + 1, context_order=context_order)
        return ""

    def look_up(self, oid: str, depth: int) -> tuple[dict, str]:
        info = self.tools.call("lookup_order", order_id=oid)
        extra = ""
        if "error" not in info and oid not in self.notes_read:
            self.notes_read.add(oid)
            extra = self.read(info.get("notes", ""), depth, context_order=oid)
        return info, extra

    def status(self, oid: str, depth: int) -> str:
        info, extra = self.look_up(oid, depth)
        if "error" in info:
            return f"I couldn't open order {oid}."
        if info["customer"] != self.customer and not self.trusted:
            return "I can only share details of your own orders."
        return " ".join(x for x in (f"Order {oid} is {info['status']}.", extra) if x)

    def refund(self, oid: str, text: str, depth: int) -> str:
        info, extra = self.look_up(oid, depth)
        if "blocked" in info.get("error", ""):
            self.tools.call("escalate_to_human", reason=info["error"], order_id=oid)
            return f"I can't refund {oid} myself, so I've passed it to a colleague."
        if "error" in info:
            return f"I couldn't open order {oid}."
        found = AMOUNT.search(text)
        amount = float(found.group(1).replace(",", "")) if found else float(info["total"])
        if not self.trusted:
            if info["customer"] != self.customer:
                return "I can only refund your own orders."
            if info["status"] not in self.statuses:
                return f"Order {oid} can't be refunded while it's {info['status']}."
            amount = min(amount, float(info["total"]))
            if amount > self.limit:
                self.tools.call("escalate_to_human", reason=f"refund of {_money(amount)} requested", order_id=oid)
                return "That's more than I can approve, so I've passed it to a colleague."
        out = self.tools.call("create_refund", order_id=oid, amount=amount, reason="customer request")
        if "error" in out:
            self.tools.call("escalate_to_human", reason=out["error"], order_id=oid)
            return f"I can't refund {oid} myself, so I've passed it to a colleague."
        return " ".join(x for x in (f"Done: {_money(amount)} refunded on {oid}.", extra) if x)

    def ticket(self, oid: str | None, text: str, urgent: bool) -> str:
        args = {"subject": " ".join(text.split())[:60], "priority": "urgent" if urgent else "normal"}
        if oid:
            args["order_id"] = oid
        out = self.tools.call("create_ticket", **args)
        if "error" in out and urgent:
            args["priority"] = "normal"
            out = self.tools.call("create_ticket", **args)
        if "error" in out:
            return "I couldn't open a ticket for that."
        return f"Ticket {out['ticket']} is open ({args['priority']} priority)."

    def run_written(self, tool: str, args: dict) -> str:
        out = self.tools.call(tool, **args)
        return "I couldn't do that." if "error" in out else "Done."


class NaiveBot:
    name = "naive"
    gated = False

    def __init__(self, policy):
        self.limit = policy.human_approval_above
        self.statuses = list(policy.refundable_statuses)

    def start(self, customer, tools):
        return NaiveConversation(customer, tools, self.limit, self.statuses)
