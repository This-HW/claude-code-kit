#!/usr/bin/env python3
"""SubagentStart / SubagentStop / PreCompact hook: logs agent lifecycle events."""

import json
import os
import sys
from datetime import datetime

hook_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, hook_dir)
try:
    from utils import debug_log
except ImportError:

    def debug_log(msg, error=None):
        pass


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    timestamp = datetime.now().strftime("%H:%M:%S")

    if action == "start":
        agent_name = input_data.get("tool_input", {}).get("agent_name", "unknown")
        debug_log(f"[{timestamp}] Subagent START: {agent_name}")
    elif action == "stop":
        agent_name = input_data.get("tool_input", {}).get("agent_name", "unknown")
        debug_log(f"[{timestamp}] Subagent STOP: {agent_name}")
    elif action == "precompact":
        summary = input_data.get("summary", "")
        debug_log(
            f"[{timestamp}] PreCompact: saving state before compaction ({len(summary)} chars)"
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
