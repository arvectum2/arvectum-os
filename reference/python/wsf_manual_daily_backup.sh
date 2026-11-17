#!/bin/sh
# Owner-approved daily backup. All logs and the executable release remain on
# the internal disk. No automatic grant, renewal, deletion or data migration.
set -eu
ROOT=${ARVECTUM_P7_02_ROOT:-"$HOME/Library/Application Support/ArvectumOS/persistent-internal"}
[ -L "$ROOT/current" ]
SHA=$(basename "$(readlink "$ROOT/current")")
case "$SHA" in (*[!0-9a-f]*|"") exit 1;; esac
[ "${#SHA}" -eq 40 ]
PY="$ROOT/venvs/$SHA/bin/python"
SCRIPT="$ROOT/releases/$SHA/source/reference/python/wsf_manual_operator.py"
[ -x "$PY" ] && [ -f "$SCRIPT" ]
export ARVECTUM_P7_02_ROOT="$ROOT"
export PYTHONDONTWRITEBYTECODE=1
"$PY" -B "$SCRIPT" backup
if [ -e "$ROOT/config/crm-activation.json" ] || [ -L "$ROOT/config/crm-activation.json" ]; then
  CRM_SCRIPT="$ROOT/releases/$SHA/source/reference/python/wsf_crm_operator.py"
  [ -f "$CRM_SCRIPT" ]
  "$PY" -B "$CRM_SCRIPT" backup
fi

if [ -e "$ROOT/config/roadmap-inbox-activation.json" ] || [ -L "$ROOT/config/roadmap-inbox-activation.json" ]; then
  INBOX_SCRIPT="$ROOT/releases/$SHA/source/reference/python/wsf_inbox_operator.py"
  [ -f "$INBOX_SCRIPT" ]
  "$PY" -B "$INBOX_SCRIPT" backup
fi
