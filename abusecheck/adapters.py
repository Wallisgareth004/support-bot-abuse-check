"""Check a bot you run: over HTTP, or as a Python function in your own code.

Each customer turn is sent as
    {"conversation_id": "...", "customer_id": "C100", "message": "..."}
and the bot answers with its reply and the tool calls it made on its side:
    {"reply": "...", "tool_calls": [{"tool": "create_refund", "args": {"order_id": "A1001", "amount": 80}}]}
The calls are checked against policy.toml and applied to the world file, which must
mirror the bot's test data (customers, orders, articles).

Only point this at a bot you own, or one you have written permission to test. A URL
other than this machine is refused unless authorised=True (--authorised).
"""

import importlib
import json
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlparse

LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class BotError(RuntimeError):
    """The bot didn't answer, or answered in the wrong shape. Never counted as a pass."""


def _apply(answer, tools) -> str:
    if not isinstance(answer, dict) or not isinstance(answer.get("reply", ""), str):
        raise BotError("the bot's answer must be an object with a string reply")
    calls = answer.get("tool_calls", [])
    if not isinstance(calls, list) or not all(
        isinstance(c, dict) and isinstance(c.get("tool"), str) and isinstance(c.get("args", {}), dict)
        for c in calls
    ):
        raise BotError("tool_calls must be a list of {tool, args} objects")
    for c in calls:
        tools.report(c["tool"], c.get("args", {}))
    return answer.get("reply", "")


class HttpBot:
    gated = False

    def __init__(self, url: str, authorised: bool = False, timeout: float = 30.0):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError(f"not an http(s) URL: {url}")
        if parsed.hostname not in LOOPBACK and not authorised:
            raise ValueError(
                f"{parsed.hostname} is not this machine. Only check a bot you own or have written "
                "permission to test, then pass --authorised."
            )
        self.url, self.timeout, self.name = url, timeout, f"http bot at {url}"

    def start(self, customer, tools):
        bot, conversation_id = self, uuid.uuid4().hex

        class Conversation:
            def send(self, message):
                body = json.dumps({"conversation_id": conversation_id, "customer_id": customer,
                                   "message": message}).encode()
                req = urllib.request.Request(bot.url, data=body, method="POST",
                                             headers={"Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(req, timeout=bot.timeout) as resp:  # noqa: S310 (scheme checked)
                        answer = json.loads(resp.read().decode("utf-8"))
                except (urllib.error.URLError, TimeoutError, ValueError) as e:
                    raise BotError(f"{bot.url}: {e}") from e
                return _apply(answer, tools)

        return Conversation()


class PythonBot:
    """'module:function', where function(conversation_id, customer_id, message) returns
    the same answer object as the HTTP contract."""

    gated = False

    def __init__(self, spec: str):
        module, _, func = spec.partition(":")
        if not module or not func:
            raise ValueError(f"expected module:function, got {spec!r}")
        self.fn = getattr(importlib.import_module(module), func)
        self.name = f"python bot {spec}"

    def start(self, customer, tools):
        bot, conversation_id = self, uuid.uuid4().hex

        class Conversation:
            def send(self, message):
                return _apply(bot.fn(conversation_id, customer, message), tools)

        return Conversation()
