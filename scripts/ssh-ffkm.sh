#!/usr/bin/env bash
# SSH на production VPS ФФКМ (SSH).
# С Windows-машины то же самое:
#   ssh -i "$USERPROFILE/.ssh/id_ed25519" -p 2222 root@46.173.17.188
set -euo pipefail

HOST="${FFKM_SSH_HOST:-46.173.17.188}"
PORT="${FFKM_SSH_PORT:-2222}"
USER_NAME="${FFKM_SSH_USER:-root}"
KEY_PATH="${FFKM_SSH_KEY_PATH:-}"

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

if [[ -n "${FFKM_SSH_PRIVATE_KEY:-}" ]]; then
  KEY_PATH="$HOME/.ssh/ffkm_consent_ed25519"
  printf '%s\n' "${FFKM_SSH_PRIVATE_KEY//$'\r'/}" | sed 's/\\n/\n/g' > "$KEY_PATH"
  chmod 600 "$KEY_PATH"
fi

if [[ -z "$KEY_PATH" ]]; then
  if [[ -f "$HOME/.ssh/id_ed25519" ]]; then
    KEY_PATH="$HOME/.ssh/id_ed25519"
  else
    KEY_PATH="$HOME/.ssh/ffkm_consent_ed25519"
  fi
fi

if [[ ! -f "$KEY_PATH" ]]; then
  echo "ERROR: SSH key not found. Set FFKM_SSH_PRIVATE_KEY or FFKM_SSH_KEY_PATH, or put ~/.ssh/id_ed25519." >&2
  exit 1
fi

exec ssh -i "$KEY_PATH" -p "$PORT" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new \
  "${USER_NAME}@${HOST}" "$@"
