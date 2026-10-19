"""A stand-in for a buyer's bot, for the adapter tests. It refunds whatever order it's
told to and reports the call, the way a real bot behind the HTTP contract would."""

import re


def respond(conversation_id, customer_id, message):
    m = re.search(r"\b([A-Z]\d{4})\b", message)
    if "refund" in message.lower() and m:
        return {"reply": f"Refunded {m.group(1)}.",
                "tool_calls": [{"tool": "create_refund", "args": {"order_id": m.group(1), "amount": 50}}]}
    return {"reply": "How can I help?", "tool_calls": []}


def broken_shape(conversation_id, customer_id, message):
    return {"reply": "ok", "tool_calls": "create_refund"}
