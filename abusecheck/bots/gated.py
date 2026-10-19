"""The gated demo bot: the same naive conversation, with every tool call checked
against policy.toml in code before it runs. A blocked call returns an error to the
bot, which passes the request to a person. This is the fix pattern, not a smarter
model: the bot is just as easy to talk round; the tools refuse."""

from .naive import NaiveBot


class GatedBot(NaiveBot):
    name = "gated"
    gated = True
