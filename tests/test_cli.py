import json
import os
import re
import subprocess
import sys

from tests.test_adapters import server  # noqa: F401  (fixture)


def run(root, *args):
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, "-m", "abusecheck", "run", *args], cwd=root,
                          capture_output=True, text=True, env=env, timeout=60)


def test_the_gated_bot_exits_clean_and_writes_both_files(root, tmp_path):
    p = run(root, "--bot", "gated", "--report", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json"))
    assert p.returncode == 0, p.stderr
    assert "gated: 0 of 40 attacks broke a rule" in p.stdout
    data = json.loads((tmp_path / "r.json").read_text())
    assert data["summary"]["attacks"] == 40 and len(data["cases"]) == 46
    assert (tmp_path / "r.md").read_text().startswith("# Support-bot abuse check: gated")


def test_any_break_exits_1(root):
    p = run(root, "--bot", "naive", "--only", "direct-01")
    assert p.returncode == 1
    assert "naive: 1 of 1 attacks broke a rule" in p.stdout


def test_only_filters_by_id_prefix(root):
    p = run(root, "--bot", "gated", "--only", "control")
    assert p.returncode == 0 and "controls served 6 of 6" in p.stdout


def test_a_missing_case_folder_exits_2(root, tmp_path):
    p = run(root, "--bot", "naive", "--cases", str(tmp_path / "nope"))
    assert p.returncode == 2 and "no .toml case files" in p.stderr


def test_an_unknown_bot_exits_2(root):
    p = run(root, "--bot", "clever")
    assert p.returncode == 2


def test_a_remote_url_without_permission_exits_2(root):
    p = run(root, "--bot", "https://bot.example.com/chat")
    assert p.returncode == 2 and "authorised" in p.stderr


def test_an_http_bot_from_the_command_line(root, server):  # noqa: F811
    url, _ = server
    p = run(root, "--bot", url, "--only", "control-03")
    assert p.returncode == 1  # the fake bot never looks the order up: over-blocked
    assert re.search(r"controls served 0 of 1", p.stdout)
