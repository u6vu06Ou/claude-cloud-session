---
name: cloud-session
description: Start a new claude.ai/code cloud session (pre-filled launch URL opened in the user's own logged-in browser) or send a message into a session that is already running, all on the user's own claude.ai account quota. Triggers - "start a cloud session", "open a cloud session", "message the cloud session", "cloud Claude Code", "claude.ai/code", "cloud session", "/cloud-session".
---

# Cloud sessions: start new ones, steer running ones

Everything here runs on the **user's own claude.ai account** (web cloud quota) — not on any local proxy or API key. The user asking to operate a cloud session is the authorization for that spend; if the intent is ambiguous, confirm first.

## A. Send a message to a RUNNING cloud session (works from any folder)

1. Find the `session_id` (`session_01...`). Three ways:
   - the session URL the user gave you: `claude.ai/code/session_...`
   - the cloud session's pushed commits: `git log --all --format=%b | grep Claude-Session`
   - the tail of a PR body it opened: the `claude.ai/code/session_...` link
2. Send the message:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/send.py" session_01... "Continue with step 3, stop after the migration file" 
   ```
   `send.py` strips `ANTHROPIC_BASE_URL` / `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` from the child process so the CLI authenticates through the local **claude.ai login**, then runs `claude -p --cloud <session_id> "<msg>" --output-format json` and prints the parsed `{ok, session_id, url}` summary.
3. The reply is only visible on the web. For results, watch the branch / PR / progress file the session pushes.
4. Prerequisite: `claude auth status` must show the claude.ai auth method. If it shows an API key instead, ask the user to run `claude auth login`.

## B. Start a NEW cloud session

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/cloudcode.py" \
  --env <environment-name> --branch <branch> --worker self \
  --prompt-file opener.md
```

This opens a pre-filled URL (`claude.ai/code?prompt=…&repositories=owner/repo&environment=NAME`) in the user's already-logged-in browser; the user glances at the branch and presses Enter.

- `--repo` defaults to the owner/repo derived from the current folder's git remote `origin`; pass it explicitly when working outside a clone.
- `--print` prints the URL instead of opening a browser. URLs longer than ~12000 characters trigger a warning — move long briefs into the repo instead.
- **The branch must be pushed first.** Put long task briefs in a file on that branch (e.g. `CLOUD_TASK.md`) and let the opening prompt say "read CLOUD_TASK.md first". The pre-fill URL has no branch parameter, so the script writes the branch into the opening prompt's header — and the user should still eyeball the branch selector before pressing Enter.
- Do NOT use the official `claude --cloud "description"` to start sessions: it cannot pick a web-created environment or a branch, and it stops in interactive mode.

## Who does the work: `--worker self|relay|ask`

Every launched session gets a worker directive prepended to its opening prompt.

### `self` (default)

The cloud claude.ai agent does the hands-on work itself, on its own paid quota. The directive tells it to first verify `printenv ANTHROPIC_BASE_URL` prints nothing, i.e. it is really running on this cloud session's own account and not being redirected elsewhere.

### `relay`

The cloud agent is **forbidden from doing hands-on implementation**. It acts purely as the orchestrator; the actual work is delegated to **the user's own model** through a relay. This plugin deliberately does NOT hard-code how that relay is wired — it depends on what the user has. When the user asks for relay mode, first do this locally:

1. **Inventory what the user already runs**: a local OpenAI- or Anthropic-compatible proxy, Ollama, LiteLLM, a self-hosted gateway, ... Ask the user which backend should do the work, then decide the wiring for them.
2. **Give it a public address**: the cloud sandbox cannot reach the user's LAN or `localhost`. The user needs a publicly reachable hop — e.g. a tunnel (cloudflared, Tailscale Funnel, ngrok) pointed at the local endpoint, or a tiny forwarder function running on a VPS/serverless host that proxies to their backend. HTTPS only.
3. **Agree on a shared secret** and put BOTH values into the cloud environment's variables on the web app (environment settings → secrets):
   - `RELAY_URL` — the FULL public HTTPS endpoint of the hop (path included, e.g. `.../v1/chat/completions`)
   - `RELAY_TOKEN` — the shared secret
4. **Secrets live only in the cloud environment's variables. Never write them into the repo, the prompt, or a commit.**

`examples/relay.sh` in this repo is a ready-to-adapt helper skeleton — it reads `$RELAY_URL` / `$RELAY_TOKEN` from the environment, refuses plain-http URLs, and POSTs a task to the relay; it contains no real URLs or keys. Adapt it, ship it on the working branch... and tell the cloud agent to **review the helper before running it** — it will see `RELAY_TOKEN`.

### `ask`

The script stops and asks the user interactively to pick `self` or `relay` for that launch, then proceeds. In a non-interactive context it falls back to `self` with a stderr note. Useful until the relay wiring is settled.

## Rules

- One cloud session per task. If a duplicate appears, keep the one that is further along and tell the other to stop (method A).
- Messages must state: what to do, the done-criteria, what NOT to touch, and which branch to open the PR back to.

## Known limits of the official surface

- The pre-fill URL supports `prompt`, `repositories`, `environment` only — no branch, no model picker.
- `claude --cloud` cannot select a web-created environment or a branch and drops into interactive mode.
- This project is **not affiliated with or endorsed by Anthropic**.
