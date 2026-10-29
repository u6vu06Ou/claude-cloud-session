"""Unit tests for scripts/send.py — standard library + pytest only."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import send  # noqa: E402


# ---------- environment scrubbing ----------

def test_clean_env_strips_proxy_and_key_vars():
    env = {
        "ANTHROPIC_BASE_URL": "http://example.invalid",
        "ANTHROPIC_API_KEY": "dummy",
        "ANTHROPIC_AUTH_TOKEN": "dummy",
        "PATH": "/usr/bin",
        "HOME": "/home/x",
    }
    out = send.clean_env(env)
    for var in send.STRIP_VARS:
        assert var not in out
    assert out["PATH"] == "/usr/bin"
    assert out["HOME"] == "/home/x"
    # input dict untouched
    assert "ANTHROPIC_BASE_URL" in env


# ---------- session id validation ----------

@pytest.mark.parametrize("sid", ["session_01AbCxyz", "session_01a-b_c"])
def test_valid_session_ids(sid):
    assert send.valid_session_id(sid)


@pytest.mark.parametrize("sid", ["", None, "sess_123", "session_", "session_01 abc", "x; rm -rf /"])
def test_invalid_session_ids(sid):
    assert not send.valid_session_id(sid)


# ---------- argv and result parsing ----------

def test_build_argv():
    argv = send.build_argv("session_01A", "hello cloud")
    assert argv == ["claude", "-p", "--cloud", "session_01A", "hello cloud",
                    "--output-format", "json"]
    assert "<" not in argv  # no shell redirection; stdin is detached by subprocess


def test_parse_result_ok():
    out = send.parse_result(json.dumps({
        "ok": True,
        "session_id": "session_01A",
        "url": "https://claude.ai/code/session_01A",
    }))
    assert out == {
        "ok": True,
        "session_id": "session_01A",
        "url": "https://claude.ai/code/session_01A",
    }


def test_parse_result_bad_json():
    with pytest.raises(json.JSONDecodeError):
        send.parse_result("not json")


def test_main_rejects_bad_session_id(capsys):
    rc = send.main(["bogus", "hi"])
    assert rc == 2
    assert "does not look like a session id" in capsys.readouterr().err
