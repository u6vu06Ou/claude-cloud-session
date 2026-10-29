#!/bin/sh
# Example relay helper for "--worker relay" mode.
#
# The cloud sandbox cannot reach your home machine, so RELAY_URL must point at
# a PUBLIC HTTPS endpoint you control — e.g. a tunnel (cloudflared, Tailscale
# Funnel, ngrok) in front of your local OpenAI/Anthropic-compatible endpoint or
# Ollama, or a small forwarder function on a VPS/serverless host.
#
# Configure BOTH values as secrets of the cloud environment (web app →
# environment settings). NEVER commit real URLs or tokens into a repo.
#
# Usage (inside the cloud session):
#   printf '%s' 'Implement X in file Y; done when tests pass' | ./relay.sh
set -eu

: "${RELAY_URL:?set RELAY_URL in the cloud environment secrets}"
: "${RELAY_TOKEN:?set RELAY_TOKEN in the cloud environment secrets}"

# Adapt the path and payload shape to your relay (this example speaks the
# OpenAI chat-completions shape). Task text arrives on stdin.
task=$(cat)
curl -fsS -X POST "$RELAY_URL/v1/chat/completions" \
  -H "Authorization: Bearer $RELAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(printf '{\"model\":\"your-model-name\",\"messages\":[{\"role\":\"user\",\"content\":%s}]}' \
       "$(printf '%s' "$task" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'))"
