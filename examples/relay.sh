#!/bin/sh
# Example relay helper for "--worker relay" mode.
#
# The cloud sandbox cannot reach your home machine, so RELAY_URL must be the
# FULL public HTTPS endpoint of a hop you control — e.g. a tunnel (cloudflared,
# Tailscale Funnel, ngrok) in front of your local OpenAI/Anthropic-compatible
# endpoint or Ollama, or a small forwarder function on a VPS/serverless host.
# Example shape (placeholder, NOT a real URL):
#   RELAY_URL=https://your-relay.example.com/v1/chat/completions
# (The path is part of RELAY_URL — this script POSTs to it as-is and never
# appends anything.)
#
# Configure BOTH values as secrets of the cloud environment (web app →
# environment settings). NEVER commit real URLs or tokens into a repo.
# Optional: RELAY_MAX_TIME (seconds, default 300) for slow local models.
#
# Requires curl and python3 (both present in the cloud sandbox). Task text
# arrives on stdin; the payload speaks the OpenAI chat-completions shape —
# adapt the model name and payload to whatever your relay expects.
# The token goes through a 0600 curl config file so it never shows up in a
# process listing, and the payload streams via --data-binary so long tasks
# stay clear of argv limits.
#
# Usage (inside the cloud session):
#   printf '%s' 'Implement X in file Y; done when tests pass' | ./relay.sh
set -eu

: "${RELAY_URL:?set RELAY_URL in the cloud environment secrets}"
: "${RELAY_TOKEN:?set RELAY_TOKEN in the cloud environment secrets}"

case "$RELAY_URL" in
  https://?*|HTTPS://?*) ;;
  *) echo "error: RELAY_URL must be an https:// endpoint with a host" >&2; exit 1 ;;
esac

cfg=$(mktemp "${TMPDIR:-/tmp}/relay.XXXXXX")
chmod 600 "$cfg"
trap 'rm -f "$cfg"' EXIT
printf 'header = "Authorization: Bearer %s"\n' "$RELAY_TOKEN" > "$cfg"

python3 -c '
import json, sys
print(json.dumps({
    "model": "your-model-name",
    "messages": [{"role": "user", "content": sys.stdin.read()}],
}))
' | curl -fsS --connect-timeout 15 --max-time "${RELAY_MAX_TIME:-300}" \
  -K "$cfg" -H "Content-Type: application/json" --data-binary @- "$RELAY_URL"
