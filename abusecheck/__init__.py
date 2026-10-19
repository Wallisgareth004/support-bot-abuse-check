"""support-bot-abuse-check: can a customer talk a support bot into actions it shouldn't take?

Scripted customer conversations run against a bot; every tool call the bot makes is
checked against written business rules (policy.toml). Pass or fail comes from the
tool-call log, never from a model's opinion. Standard library only, Python 3.11+.
"""
