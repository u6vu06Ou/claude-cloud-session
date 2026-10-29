#!/usr/bin/env python3
"""Send a message into a RUNNING claude.ai/code cloud session.

Wraps:
    claude -p --cloud <session_id> "<message>" --output-format json

The child process gets ANTHROPIC_BASE_URL, ANTHROPIC_API_KEY and
ANTHROPIC_AUTH_TOKEN removed from its environment, so the CLI authenticates
through the local claude.ai account login instead of any proxy or API key.
A successful send answers a JSON object like {"ok": true, "session_id": ...,
"url": ...}; the session's written reply is only visible on the web — watch its
branch / PR / progress file for results.

Prerequisite: `claude auth status` must report the claude.ai auth method
(not an API key). Run `claude auth login` first if needed.

Python 3 standard library only; works on Windows, macOS and Linux.

Usage:
    send.py session_01AbC... "please stop and report what is left"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

STRIP_VARS = ("ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
SESSION_RE = re.compile(r"^session_[A-Za-z0-9_-]+$")


def clean_env(env: dict | None = None) -> dict:
    """Return a copy of *env* (default: os.environ) without the proxy/API vars."""
    out = dict(os.environ if env is None else env)
    for var in STRIP_VARS:
        out.pop(var, None)
    return out


def valid_session_id(s: str | None) -> bool:
    return bool(SESSION_RE.match(s or ""))


def build_argv(session_id: str, message: str) -> list[str]:
    return ["claude", "-p", "--cloud", session_id, message, "--output-format", "json"]


def parse_result(stdout: str) -> dict:
    """Parse the CLI's JSON answer into a small summary dict."""
    data = json.loads(stdout)
    if not isinstance(data, dict):
        raise ValueError("unexpected non-object JSON reply")
    return {
        "ok": bool(data.get("ok")),
        "session_id": data.get("session_id"),
        "url": data.get("url"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Send a message to a running claude.ai/code cloud session."
    )
    ap.add_argument("session_id", help="session_01... (from the session URL, "
                    "a Claude-Session commit trailer, or a PR body)")
    ap.add_argument("message", help="the message to send")
    ap.add_argument("--timeout", type=int, default=180,
                    help="seconds to wait for the CLI (default 180)")
    a = ap.parse_args(argv)

    if not valid_session_id(a.session_id):
        print(f"error: '{a.session_id}' does not look like a session id "
              "(expected session_...)", file=sys.stderr)
        return 2

    try:
        r = subprocess.run(
            build_argv(a.session_id, a.message),
            env=clean_env(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=a.timeout,
        )
    except FileNotFoundError:
        print("error: `claude` CLI not found on PATH", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print(f"error: claude CLI did not answer within {a.timeout}s", file=sys.stderr)
        return 1

    if r.returncode != 0:
        print(f"error: claude CLI exited {r.returncode}:\n{r.stderr.strip()}",
              file=sys.stderr)
        return 1

    try:
        summary = parse_result(r.stdout)
    except (ValueError, json.JSONDecodeError):
        print("error: reply was not the expected JSON; raw output follows",
              file=sys.stderr)
        print(r.stdout)
        return 1

    print(json.dumps(summary, ensure_ascii=False))
    if summary["ok"]:
        print("delivered. The session's reply is only visible on the web; "
              "watch its branch / PR / progress file for results.")
        return 0
    print("warning: reply did not confirm delivery (ok != true)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
