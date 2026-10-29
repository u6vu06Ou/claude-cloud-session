"""Unit tests for scripts/cloudcode.py — standard library + pytest only."""
import sys
import urllib.parse
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import cloudcode  # noqa: E402


# ---------- URL assembly ----------

def _parse(url):
    assert url.startswith(cloudcode.BASE_URL + "?")
    return urllib.parse.parse_qs(url.split("?", 1)[1])


def test_build_url_full():
    url = cloudcode.build_url("do the thing", "octo/proj", "my-env")
    q = _parse(url)
    assert q["prompt"] == ["do the thing"]
    assert q["repositories"] == ["octo/proj"]
    assert q["environment"] == ["my-env"]


def test_build_url_no_env_omits_param():
    q = _parse(cloudcode.build_url("x", "o/r", None))
    assert "environment" not in q


def test_build_url_percent_encodes_spaces():
    url = cloudcode.build_url("a b", "o/r", None)
    assert "a%20b" in url
    assert "+" not in url.split("?", 1)[1]


def test_long_prompt_exceeds_warning_threshold():
    short = cloudcode.build_url("hi", "o/r", None)
    long = cloudcode.build_url("x" * 13000, "o/r", None)
    assert len(short) < cloudcode.MAX_URL_LEN < len(long)


# ---------- branch insertion ----------

def test_branch_prepended_to_prompt():
    out = cloudcode.build_prompt("the real task", "feat/x", "self")
    lines = out.splitlines()
    assert any("git fetch origin && git checkout feat/x" in ln for ln in lines)
    assert any("feat/x" in ln and "draft" in ln and "main" in ln for ln in lines)
    # branch line comes before the user's prompt body
    assert out.index("git fetch origin") < out.index("the real task")


def test_branch_not_duplicated_when_prompt_already_leads_with_it():
    out = cloudcode.build_prompt("Work on feat/x first please", "feat/x", "self")
    assert out.count("git checkout feat/x") == 0
    assert "Work on feat/x first please" in out


# ---------- worker modes ----------

def test_worker_default_is_self_in_prompt():
    out = cloudcode.build_prompt("task", None, "self")
    assert "[Worker mode: self]" in out
    assert "ANTHROPIC_BASE_URL" in out
    assert "own claude.ai account quota" in out


def test_worker_relay_forbids_hands_on():
    out = cloudcode.build_prompt("task", None, "relay")
    assert "[Worker mode: relay]" in out
    assert "ORCHESTRATOR ONLY" in out
    assert "RELAY_URL" in out and "RELAY_TOKEN" in out
    assert "Do not implement" in out


def test_worker_unknown_mode_raises():
    with pytest.raises(KeyError):
        cloudcode.build_prompt("task", None, "bogus")


def test_resolve_worker_passthrough():
    assert cloudcode.resolve_worker("self") == "self"
    assert cloudcode.resolve_worker("relay") == "relay"


def test_resolve_worker_ask_interactive():
    answers = iter(["nonsense", "relay"])
    picked = cloudcode.resolve_worker("ask", ask_fn=lambda _q: next(answers))
    assert picked == "relay"


# ---------- repo derivation ----------

@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/octo/proj", "octo/proj"),
        ("https://github.com/octo/proj.git", "octo/proj"),
        ("https://github.com/octo/proj/", "octo/proj"),
        ("https://user@github.com/octo/proj.git", "octo/proj"),
        ("git@github.com:octo/proj.git", "octo/proj"),
        ("git@github.com:octo/proj", "octo/proj"),
        ("ssh://git@github.com/octo/proj.git", "octo/proj"),
        ("https://gitlab.example.com/group/sub/proj", None),  # >2 segments: rejected
        ("not a url", None),
        ("", None),
    ],
)
def test_parse_remote(url, expected):
    assert cloudcode.parse_remote(url) == expected
