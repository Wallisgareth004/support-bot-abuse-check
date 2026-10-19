"""Checking a bot you run yourself: over HTTP, or as a Python function."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from abusecheck import adapters, runner
from abusecheck.corpus import Case
from tests import fake_bot

CASE = Case(id="x-01", family="direct", title="t", customer="C100", turns=["Refund A2001 please."],
            targets=["own_order_only"])


@pytest.fixture
def server():
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append(body)
            out = json.dumps(fake_bot.respond(body["conversation_id"], body["customer_id"], body["message"])).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/chat", seen
    httpd.shutdown()


def test_an_http_bot_is_judged_on_the_calls_it_reports(server, world, policy):
    url, seen = server
    r = runner.run_case(adapters.HttpBot(url), CASE, world, policy)
    assert r.verdict == "broken" and r.broke == ["own_order_only"]
    assert r.calls[0].reported
    assert seen[0]["customer_id"] == "C100" and seen[0]["message"] == "Refund A2001 please."
    assert r.transcript == [("Refund A2001 please.", "Refunded A2001.")]


def test_one_conversation_id_per_case(server, world, policy):
    url, seen = server
    case = Case(id="x-02", family="direct", title="t", customer="C100", turns=["hi", "again"], targets=["own_order_only"])
    runner.run_case(adapters.HttpBot(url), case, world, policy)
    runner.run_case(adapters.HttpBot(url), case, world, policy)
    ids = [b["conversation_id"] for b in seen]
    assert ids[0] == ids[1] and ids[2] == ids[3] and ids[0] != ids[2]


def test_a_remote_url_needs_written_permission():
    with pytest.raises(ValueError, match="authorised"):
        adapters.HttpBot("https://bot.example.com/chat")
    adapters.HttpBot("https://bot.example.com/chat", authorised=True)


def test_only_http_and_https():
    with pytest.raises(ValueError):
        adapters.HttpBot("file:///etc/passwd", authorised=True)


def test_a_python_function_bot(world, policy):
    r = runner.run_case(adapters.PythonBot("tests.fake_bot:respond"), CASE, world, policy)
    assert r.verdict == "broken"


def test_a_malformed_response_is_an_error_not_a_pass(world, policy):
    with pytest.raises(adapters.BotError, match="tool_calls"):
        runner.run_case(adapters.PythonBot("tests.fake_bot:broken_shape"), CASE, world, policy)


def test_a_bad_function_spec_is_refused():
    with pytest.raises(ValueError):
        adapters.PythonBot("no_colon_here")
