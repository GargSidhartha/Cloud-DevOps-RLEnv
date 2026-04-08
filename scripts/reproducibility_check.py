#!/usr/bin/env python
"""Deterministic reproducibility smoke test for Cloud DevOps RLEnv."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from env import CloudDevOpsEnv
from models import CloudAction

SCORE_MIN = 0.001
SCORE_MAX = 0.999

# Fixed trajectories that should always resolve the incidents.
POLICY_BY_TASK: dict[str, list[dict[str, Any]]] = {
    "easy": [
        {"command": "list_resources"},
        {
            "command": "update_security_group",
            "resource_id": "sg-web",
            "parameters": {"port": 80, "action": "allow"},
        },
    ],
    "medium": [
        {"command": "list_resources"},
        {"command": "view_logs", "resource_id": "i-api"},
        {
            "command": "query_metadata",
            "parameters": {"ip_address": "10.0.4.5"},
        },
        {
            "command": "update_security_group",
            "resource_id": "sg-db",
            "parameters": {"port": 5432, "action": "allow"},
        },
    ],
    "hard": [
        {"command": "list_resources"},
        {"command": "view_logs", "resource_id": "lb-main"},
        {
            "command": "query_metadata",
            "parameters": {"ip_address": "10.0.8.22"},
        },
        {"command": "describe_resource", "resource_id": "i-web2"},
        {"command": "restart_service", "resource_id": "i-web2"},
    ],
}


async def run_policy(task_name: str) -> dict[str, Any]:
    env = CloudDevOpsEnv(task_name=task_name)
    await env.reset()

    trajectory: list[dict[str, Any]] = []
    rewards: list[float] = []
    last = None

    try:
        for index, raw_action in enumerate(POLICY_BY_TASK[task_name], start=1):
            action = CloudAction(**raw_action)
            result = await env.step(action)
            rewards.append(float(result.reward))
            trajectory.append(
                {
                    "step": index,
                    "command": action.command,
                    "resource_id": action.resource_id,
                    "reward": round(float(result.reward), 4),
                    "done": bool(result.done),
                    "error": result.observation.error,
                    "status": result.observation.system_health_status,
                    "resolved": bool(result.info.get("resolved", False)),
                }
            )
            last = result
            if result.done:
                break

        if last is None:
            raise RuntimeError(f"Task {task_name} produced no steps")

        score = max(SCORE_MIN, min(sum(rewards), SCORE_MAX))
        return {
            "task": task_name,
            "resolved": bool(last.info.get("resolved", False)),
            "steps": len(trajectory),
            "score": round(score, 3),
            "trajectory": trajectory,
        }
    finally:
        await env.close()


async def main() -> None:
    summary: dict[str, Any] = {}

    for task_name in ("easy", "medium", "hard"):
        run_1 = await run_policy(task_name)
        run_2 = await run_policy(task_name)

        if run_1["trajectory"] != run_2["trajectory"]:
            raise SystemExit(f"Determinism check failed for task={task_name}: trajectories differ")
        if not run_1["resolved"]:
            raise SystemExit(f"Policy failed to resolve task={task_name}")

        summary[task_name] = {
            "steps": run_1["steps"],
            "score": run_1["score"],
            "resolved": run_1["resolved"],
        }

    print("Deterministic reproducibility check passed")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
