#!/bin/sh
# Example relay helper for "--worker relay" mode.
#
# The cloud sandbox cannot reach your home machine, so RELAY_URL must be the
# FULL public HTTPS endpoint of a hop you control — e.g. a tunnel (cloudflared,
# Tailscale Funnel, ngrok) in front of your local OpenAI/Anthropic-compatible
# endpoint or Ollama, or a small forwarder function on a VPS/serverless host.
# Example shape (placeholder, NOT a real URL):
#   RELAY_URL=https://your-relay.example.com/v1/chat/completions
#
# Configure BOTH values as secrets of the cloud environment (web app →
# environment settings). NEVER commit real URLs or tokens into a repo.
#
# Requires curl and python3 (both present in the cloud sandbox). Task text
# arrives on stdin; the payload below speaks the OpenAI chat-completions
# shape — adapt model name and payload to whatever your relay expects.
#
# Usage (inside the cloud session):
#   printf '%s' 'Implement X in file Y; done when tests pass' | ./relay.sh
set -eu

: "${RELAY_URL:?set RELAY_URL in the cloud environment secrets}"
: "${RELAY_TOKEN:?set RELAY_TOKEN in the cloud environment secrets}"

case "$RELAY_URL" in
  https://*) ;;
  *) echo "error: RELAY_URL must be an https:// endpoint" >&2; exit 1 ;;
esac

task=$(cat)
payload=$(printf '%s' "$task" | python3 -c '
import json, sys
print(json.dumps({
    "model": "your-model-name",
    "messages": [{"role": "user", "content": sys.stdin.read()}],
}))
')
curl -fsS --max-time 120 -X POST "$RELAY_URL" \
  -H "Authorization: Bearer $RELAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$payload"
