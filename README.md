# claude-cloud-session

A small Claude Code plugin + two dependency-free Python scripts for driving [claude.ai/code](https://claude.ai/code) **cloud sessions** from your local Claude Code:

1. **Steer a running cloud session** — send it a message (continue / stop / change direction) from the terminal.
2. **Start a new cloud session** — open the official pre-filled launch URL (prompt + repository + environment) in your already-logged-in browser; you just press Enter.

Everything runs on **your own claude.ai account quota**. Python 3 standard library only; Windows, macOS and Linux.

## Install

As a plugin (the repo is its own marketplace):

```
/plugin marketplace add u6vu06Ou/claude-cloud-session
/plugin install cloud-session@cloud-session
```

Then the skill is available as `cloud-session` / `/cloud-session:cloud-session` and an agent can use it right away.

Manual install (no plugin machinery): copy `skills/cloud-session/SKILL.md` to `~/.claude/skills/cloud-session/SKILL.md`, copy `scripts/` next to it, and edit the two `${CLAUDE_PLUGIN_ROOT}` references in `SKILL.md` to that folder's absolute path.

Requires the Claude Code CLI logged in with the claude.ai auth method (`claude auth status`; run `claude auth login` otherwise).

## Usage A — message a running session

Find the `session_id` (`session_01...`) from the session URL, from a commit trailer (`git log --all --format=%b | grep Claude-Session`), or from the tail of a PR the session opened. Then:

```bash
python scripts/send.py session_01... "stop after the migration file and open a draft PR"
```

`send.py` strips `ANTHROPIC_BASE_URL` / `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` from the child process (so the call goes through your claude.ai login, not a proxy or API key) and wraps `claude -p --cloud <session_id> "<msg>" --output-format json`. It prints a parsed `{ok, session_id, url}` summary. The session's written reply is only visible on the web — watch its branch/PR for results.

## Usage B — start a new session

```bash
python scripts/cloudcode.py --env my-env --branch feat/x --worker self --prompt-file opener.md
```

- `--repo` defaults to `owner/repo` derived from the current folder's git remote `origin`.
- `--print` only prints the URL (each long URL shows a warning past ~12000 characters — put long briefs in a repo file and point the prompt at it).
- Push the branch first; the pre-fill URL has **no branch parameter**, so the script writes the branch into the opening prompt's header.

## Worker modes (`--worker self|relay|ask`)

- **`self`** (default): the cloud agent does the work itself. The opener tells it to first confirm `printenv ANTHROPIC_BASE_URL` prints nothing, i.e. it is really on this cloud session's own account quota.
- **`relay`**: the cloud agent becomes orchestrator-only — it may not touch code and must delegate implementation to *your own model* through a relay you set up: a publicly reachable HTTPS endpoint (a tunnel such as cloudflared/Tailscale Funnel/ngrok in front of your local OpenAI/Anthropic-compatible service, Ollama or LiteLLM, or a small forwarder on a VPS) plus a shared secret, both stored as the cloud environment's variables `RELAY_URL` (the full endpoint URL, path included) / `RELAY_TOKEN`. **Secrets live only in the cloud environment variables — never in the repo.** A ready-to-adapt helper skeleton is at [`examples/relay.sh`](examples/relay.sh) — review any helper before the cloud agent runs it, since it can see the token. The skill tells your local Claude to inventory your options and ask you before deciding the exact wiring.
- **`ask`**: the script prompts you to pick `self` or `relay` on every launch (falls back to `self` when non-interactive).

**Privacy note:** the opening prompt travels in a URL query string, so it lands in browser history (including sync) and any proxy/server logs on the way. Keep secrets and sensitive detail out of the prompt — put them in repo files on the branch or in the cloud environment's secret variables.

## Known limits

- The pre-fill URL supports only `prompt`, `repositories`, `environment` — no branch, no model.
- The official `claude --cloud "desc"` cannot select a web-created environment or branch and drops into interactive mode — not usable for scripted launches. This project works around both by using the URL + prompt header.
- No affiliation: **this project is not affiliated with, sponsored, or endorsed by Anthropic.** "Claude" refers to the product this tool drives.

## 繁體中文摘要

這個工具讓你在本機 Claude Code 裡隔空操作 claude.ai/code 的雲端對話：一、對**已在跑**的雲端對話傳話（`send.py`，自動清掉代理環境變數，確保走你自己 claude.ai 帳號的登入）；二、**開新**雲端對話（`cloudcode.py` 幫你組好官方預填網址——環境＋repo＋開場話——在你已登入的瀏覽器打開，你只按 Enter）。開場模式三選一：`self`（雲端 agent 自己動手，預設）、`relay`（雲端只當隊長，重活轉給你自己架的模型，金鑰只放雲端環境變數）、`ask`（每次自己選）。官方限制：預填網址沒有分支參數（所以分支寫進開場話第一句）、`claude --cloud` 不能選環境與分支。本專案與 Anthropic **無任何隸屬關係**。

## Development

```bash
python -m pytest tests/ -q
```

## License

MIT — see [LICENSE](LICENSE).
