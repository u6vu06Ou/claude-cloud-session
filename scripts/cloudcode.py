#!/usr/bin/env python3
"""Open a NEW claude.ai/code cloud session through the official pre-filled URL.

The URL format is the documented pre-fill form:
    https://claude.ai/code?prompt=...&repositories=owner/repo&environment=NAME
(see https://code.claude.com/docs/en/web-quickstart#pre-fill-sessions)

The URL has NO branch parameter, so the script writes the branch into the
opening prompt itself. The URL opens in the user's default browser, which is
expected to already be logged in to claude.ai — the session runs on the user's
own claude.ai account quota, not on any API key.

Python 3 standard library only; works on Windows, macOS and Linux.

Usage:
    cloudcode.py --env my-env --branch feat/x --prompt-file opener.md
    cloudcode.py --repo owner/repo "Write the opener text directly"
    cloudcode.py --print ...          # only print the URL, do not open a browser

--repo defaults to the owner/repo derived from the current folder's
`git remote get-url origin`. claude.ai/code works with GitHub repos, so only
two-segment owner/repo names are accepted.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import urllib.parse
import webbrowser

BASE_URL = "https://claude.ai/code"
MAX_URL_LEN = 12000  # browsers and the web app get unreliable beyond ~16K; warn earlier

WORKER_CHOICES = ("self", "relay", "ask")

SEGMENT_RE = r"[A-Za-z0-9_](?:[A-Za-z0-9_.-]{0,99})?"
REPO_RE = re.compile(SEGMENT_RE + "/" + SEGMENT_RE)
BRANCH_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._/-]*[A-Za-z0-9_])?")
RESERVED_TARGETS = ("main", "master")

WORKER_INSTRUCTIONS = {
    "self": (
        "[Worker mode: self]\n"
        "You are this cloud session's agent and you do the hands-on work yourself.\n"
        "Before starting, run `test -z \"$ANTHROPIC_BASE_URL\"` and confirm it "
        "succeeds (exit 0): this session must run on its own claude.ai account "
        "quota, not through a redirected backend. If the variable is set to "
        "anything, stop and report back instead of working."
    ),
    "relay": (
        "[Worker mode: relay]\n"
        "You are the ORCHESTRATOR ONLY. Do not implement, edit, or refactor code "
        "yourself in this session, and do not spend this cloud session's paid "
        "quota on hands-on work.\n"
        "Delegate every implementation item to the user's own model through the "
        "relay configured for this cloud environment:\n"
        "- RELAY_URL (the full public HTTPS endpoint of the relay) and "
        "RELAY_TOKEN (a shared secret) are set as environment variables. Verify "
        "both exist before delegating anything; if either is missing, stop and "
        "ask instead of doing the work yourself.\n"
        "- If the repo ships a relay helper such as relay.sh, REVIEW it first — "
        "it will see RELAY_TOKEN — and only then call it. Otherwise call the "
        "relay with curl: POST the task to $RELAY_URL with an Authorization "
        "header that carries $RELAY_TOKEN; the payload shape is up to the relay "
        "(see examples/relay.sh for a reference).\n"
        "You stay in charge of planning, splitting work, reviewing the returned "
        "diffs, committing, and opening the PR."
    ),
}


def parse_remote(url: str) -> str | None:
    """Extract ``owner/repo`` from a git remote URL (https, ssh or scp form).

    Returns None for anything that is not exactly two path segments, which is
    what claude.ai/code's ``repositories`` parameter accepts (GitHub).
    """
    url = (url or "").strip()
    m = re.match(
        r"^(?:https?|ssh|git)://(?:[^@/]+@)?[^/]+/([^/]+)/([^/]+?)(?:\.git)?/?$",
        url,
    )
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    m = re.match(r"^[^@/]+@[^:]+:([^/]+)/([^/]+?)(?:\.git)?/?$", url)  # git@host:owner/repo
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None


def valid_repo(repo: str | None) -> bool:
    return bool(repo and REPO_RE.fullmatch(repo) and ".." not in repo)


def valid_branch(branch: str | None) -> bool:
    """Accept only names git itself would take as a refname (simplified)."""
    if not branch or not BRANCH_RE.fullmatch(branch):
        return False
    return (".." not in branch and "//" not in branch
            and not branch.endswith(".lock"))


def default_repo(cwd: str | None = None) -> str | None:
    """owner/repo from the current folder's ``git remote get-url origin``."""
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return parse_remote(r.stdout)


def _branch_mentioned(first_line: str, branch: str) -> bool:
    """Whole-token match so `fix` does not count as mentioning branch `x`."""
    return bool(re.search(
        r"(?<![A-Za-z0-9._/-])" + re.escape(branch) + r"(?![A-Za-z0-9._/-])",
        first_line,
    ))


def build_prompt(prompt: str, branch: str | None, worker: str) -> str:
    """Compose the opening prompt: worker directive first, then branch, then body."""
    parts = [WORKER_INSTRUCTIONS[worker]]
    first_line = prompt.splitlines()[0] if prompt else ""
    if branch and not _branch_mentioned(first_line, branch):
        parts.append(
            f"Branch: the merge target is `{branch}`. Run "
            f"`git fetch origin && git checkout {branch}` to see the starting "
            f"state, then commit to your own working branch and open the pull "
            f"request with base `{branch}` (draft). Never target `main`."
        )
    elif branch and "base" not in first_line:
        parts.append(f"PR base: `{branch}` (draft). Never target `main`.")
    parts.append(prompt)
    return "\n\n".join(parts)


def resolve_worker(worker: str, ask_fn=input) -> str:
    """Turn ``ask`` into a concrete mode; non-interactive sessions fall back to self."""
    if worker != "ask":
        return worker
    while True:
        try:
            ans = ask_fn(
                "Who does the hands-on work? "
                "[self = the cloud agent itself / relay = your own model via relay] "
            ).strip().lower()
        except EOFError:  # non-interactive stdin; Ctrl-C must NOT be swallowed
            print("non-interactive session: defaulting worker to 'self'",
                  file=sys.stderr)
            return "self"
        if ans in ("self", "relay"):
            return ans
        print("Please answer 'self' or 'relay'.", file=sys.stderr)


def build_url(prompt: str, repo: str, env: str | None) -> str:
    q = {"prompt": prompt, "repositories": repo}
    if env:
        q["environment"] = env
    return BASE_URL + "?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Open a new claude.ai/code cloud session via a pre-filled URL."
    )
    ap.add_argument("prompt", nargs="?", help="opening prompt (or use --prompt-file)")
    ap.add_argument("--prompt-file", help="file holding the opening prompt (UTF-8)")
    ap.add_argument("--env", help="cloud environment name as created on the web app")
    ap.add_argument(
        "--repo",
        default=None,
        help="owner/repo; default: derived from this folder's git remote origin",
    )
    ap.add_argument("--branch", help="merge-target branch (written into the prompt)")
    ap.add_argument(
        "--worker",
        choices=WORKER_CHOICES,
        default="self",
        help="who does the hands-on work: 'self' = the cloud agent (default), "
        "'relay' = delegate to your own model, 'ask' = choose interactively "
        "(falls back to 'self' when non-interactive)",
    )
    ap.add_argument("--print", action="store_true", help="only print the URL")
    a = ap.parse_args(argv)

    if a.prompt_file:
        try:
            with open(a.prompt_file, encoding="utf-8-sig") as f:
                prompt = f.read().strip()
        except OSError as e:
            ap.error(f"cannot read --prompt-file {a.prompt_file}: {e}")
    elif a.prompt:
        prompt = a.prompt.strip()
    else:
        ap.error("give an opening prompt or --prompt-file")
    if not prompt:
        ap.error("opening prompt is empty")

    repo = a.repo or default_repo()
    if not repo:
        ap.error(
            "could not derive owner/repo from `git remote get-url origin`; "
            "pass --repo owner/repo"
        )
    if not valid_repo(repo):
        if a.repo:
            ap.error(f"--repo must look like owner/repo (got '{repo}')")
        ap.error(f"git remote origin did not yield a valid owner/repo "
                 f"(got '{repo}'); pass --repo explicitly")
    if a.branch:
        if not valid_branch(a.branch):
            ap.error(f"--branch contains characters a branch name should not "
                     f"have (got '{a.branch}')")
        if a.branch.lower() in RESERVED_TARGETS:
            ap.error(f"--branch '{a.branch}' makes no sense here: it is the "
                     "merge TARGET, and targeting main/master defeats the "
                     "never-touch-main guardrail")

    worker = resolve_worker(a.worker)
    full_prompt = build_prompt(prompt, a.branch, worker)

    url = build_url(full_prompt, repo, a.env)
    if len(url) > MAX_URL_LEN:
        print(
            f"warning: URL is {len(url)} characters; shorten the prompt or move "
            "the brief into a file on the repo and tell the agent to read it",
            file=sys.stderr,
        )
    if a.print:
        print(url)
    else:
        if not webbrowser.open(url):
            print("could not ask a browser to open this; copy it yourself:",
                  file=sys.stderr)
            print(url, file=sys.stderr)
            return 1
        print(f"asked your default browser to open the session URL: "
              f"env={a.env or '(default)'} repo={repo} "
              f"branch={a.branch or '(per prompt)'} worker={worker}")
        print("Check the environment/branch under the input box, then press Enter.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
