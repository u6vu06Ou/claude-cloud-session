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
    # PR goes back to the branch as base; never main
    assert any("base `feat/x` (draft)" in ln and "Never target `main`" in ln for ln in lines)
    # branch line comes before the user's prompt body
    assert out.index("git fetch origin") < out.index("the real task")


def test_branch_not_duplicated_when_prompt_already_leads_with_it():
    out = cloudcode.build_prompt("Work on feat/x first please", "feat/x", "self")
    assert out.count("git checkout feat/x") == 0
    # compact PR-base note is still added so the merge target is never lost
    assert "PR base: `feat/x` (draft). Never target `main`." in out
    assert "Work on feat/x first please" in out


def test_branch_substring_coincidence_still_inserts():
    # prompt mentions "Fix" — branch "x" must NOT count as mentioned
    out = cloudcode.build_prompt("Fix the parser", "x", "self")
    assert "git checkout x" in out


def test_empty_prompt_does_not_crash_build_prompt():
    out = cloudcode.build_prompt("", "feat/x", "self")
    assert "git checkout feat/x" in out


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


def test_resolve_worker_ask_noninteractive_falls_back_to_self():
    def _eof(_q):
        raise EOFError
    assert cloudcode.resolve_worker("ask", ask_fn=_eof) == "self"


def test_resolve_worker_ctrl_c_propagates():
    def _sigint(_q):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        cloudcode.resolve_worker("ask", ask_fn=_sigint)


# ---------- input validation ----------

@pytest.mark.parametrize(
    "repo,ok",
    [
        ("octo/proj", True),
        ("octo-name/my.proj_2", True),
        ("group/sub/proj", False),   # claude.ai/code takes GitHub owner/repo only
        ("noplash", False),
        ("", False),
        (None, False),
    ],
)
def test_valid_repo(repo, ok):
    assert cloudcode.valid_repo(repo) is ok


@pytest.mark.parametrize(
    "branch,ok",
    [
        ("main", True),          # name itself is legal; main as target is
        ("feat/x-2.0_rc", True),  # rejected separately in main()
        ("bad branch", False),
        ("a..b", False),
        ("a//b", False),
        ("feat/", False),
        ("x.lock", False),
        ("main\n", False),
        ("feat/$(touch x)", False),
        ("", False),
    ],
)
def test_valid_branch(branch, ok):
    assert cloudcode.valid_branch(branch) is ok


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
