"""Shared PreToolUse protocol. Never execute input or expose raw event contents."""
import json
import os
from pathlib import Path
import sys


def project_root(event):
    cwd = Path(event["cwd"]).resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".bigbang").is_dir():
            return candidate
    fallback = os.environ.get("CLAUDE_PROJECT_DIR")
    if fallback and (Path(fallback) / ".bigbang").is_dir():
        return Path(fallback).resolve()
    raise ValueError("raiz do projeto não encontrada")


def run(handler):
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict) or event.get("hook_event_name") != "PreToolUse":
            raise ValueError("evento inválido")
        if not isinstance(event.get("tool_input"), dict) or not isinstance(event.get("cwd"), str):
            raise ValueError("entrada inválida")
        decision = handler(event)
        if decision:
            action, reason = decision
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "permissionDecision": action, "permissionDecisionReason": reason}}, ensure_ascii=False))
        return 0  # Silence is not approval: normal permissions still apply.
    except Exception:  # Any unexpected failure must block rather than silently weaken this local guard.
        print("Big Bang: não foi possível conferir esta operação; chamada bloqueada. Confira a entrada e o projeto.",
              file=sys.stderr)
        return 2  # A nonzero code other than 2 would fail open in Claude Code.
