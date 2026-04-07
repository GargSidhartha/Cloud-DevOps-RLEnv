# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Cloud Devops Env Environment Implementation.

A deterministic mock cloud/devops environment with reward shaping and
anti-farming guardrails for hackathon evaluation.
"""

from __future__ import annotations

import copy
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import CloudAction, CloudObservation, CloudState
except ImportError:
    from models import CloudAction, CloudObservation, CloudState


class CloudDevopsEnvironment(Environment):
    """
    A deterministic mock cloud/devops environment.

    Tasks:
    - easy: open port 80 on sg-web
    - medium: inspect noisy API logs, then open port 5432 on sg-db
    - hard: trace 502 from lb-main to i-web2, then restart i-web2 (not i-web1)

    Example:
        >>> env = CloudDevopsEnvironment()
        >>> obs = env.reset()
        >>> print(obs.system_health_status)  # "CRITICAL"
        >>>
        >>> obs = env.step(CloudAction(command="list_resources"))
        >>> print(obs.output)
    """

    # Enable concurrent WebSocket sessions.
    # Set to True if your environment isolates state between instances.
    # When True, multiple WebSocket clients can connect simultaneously, each
    # getting their own environment instance (when using factory mode in app.py).
    SUPPORTS_CONCURRENT_SESSIONS: bool = True
    MAX_STEPS: int = 20
    VALID_TASKS = {"easy", "medium", "hard"}

    def __init__(self, task_name: str = "easy"):
        """Initialize the cloud_devops_env environment."""
        normalized_task = (task_name or "easy").lower()
        if normalized_task not in self.VALID_TASKS:
            raise ValueError(f"Unknown task: {task_name}")

        self.task_name = normalized_task
        self._state_data: CloudState | None = None
        self._achievements: set[str] = set()

    def _build_noise_resources(self) -> dict[str, dict[str, object]]:
        """Generate deterministic decoy resources to force retrieval and filtering."""
        resources: dict[str, dict[str, object]] = {}
        for i in range(1, 21):
            suffix = f"{i:02d}"
            resources[f"i-backend-{suffix}"] = {
                "type": "Instance",
                "status": "running",
                "logs": (
                    "[2026-04-06 17:00:00] INFO node-exporter: "
                    "standard metrics reported successfully"
                ),
            }
            resources[f"sg-backend-{suffix}"] = {
                "type": "SecurityGroup",
                "rules": [{"port": 443, "action": "allow"}],
            }
        return resources

    def _build_task_resources(self) -> dict[str, dict[str, object]]:
        resources = self._build_noise_resources()

        if self.task_name == "easy":
            resources.update(
                {
                "i-web": {"type": "Instance", "status": "running"},
                "sg-web": {
                    "type": "SecurityGroup",
                    "rules": [{"port": 22, "action": "allow"}],
                },
                }
            )
            return resources

        if self.task_name == "medium":
            resources.update(
                {
                "i-api": {
                    "type": "Instance",
                    "status": "running",
                    "logs": (
                        "[2026-04-06 17:01:22] [CRITICAL] "
                        "sqlalchemy.exc.OperationalError: "
                        "(psycopg2.OperationalError) connection to server at "
                        "'10.0.4.5' (i-db), port 5432 failed: Connection timed out. "
                        "Is the server running and accepting TCP/IP connections?"
                    ),
                },
                "i-db": {"type": "Instance", "status": "running"},
                "sg-db": {
                    "type": "SecurityGroup",
                    "rules": [{"port": 22, "action": "allow"}],
                },
                }
            )
            return resources

        resources.update(
            {
            "lb-main": {
                "type": "LoadBalancer",
                "logs": (
                    "2026/04/06 17:02:09 [error] 3197#3197: *4189 upstream timed out "
                    "(110: Connection timed out) while reading response header from upstream, "
                    "client: 10.0.2.14, server: api.prod.local, request: \"GET /checkout HTTP/1.1\", "
                    "upstream: \"http://i-web2:8080/checkout\", host: \"api.prod.local\"\n"
                    "2026/04/06 17:02:10 [error] 3197#3197: *4190 no live upstreams while "
                    "connecting to upstream \"i-web2\""
                ),
            },
            "i-web1": {
                "type": "Instance",
                "status": "running",
                "logs": (
                    "[2026-04-06 17:02:11] INFO web-service: readiness probe passed\n"
                    "[2026-04-06 17:02:12] INFO jvm: heap usage stable at 42%"
                ),
            },
            "i-web2": {
                "type": "Instance",
                "status": "degraded",
                "logs": (
                    "kernel: Out of memory: Killed process 12345 (java) total-vm:4194304kB, "
                    "anon-rss:3145728kB\n"
                    "systemd[1]: web-service.service: Main process exited, code=killed, "
                    "status=9/KILL"
                ),
            },
            "sg-web": {
                "type": "SecurityGroup",
                "rules": [{"port": 80, "action": "allow"}],
            },
            }
        )
        return resources

    def _reward_once(self, achievement: str, points: float) -> float:
        if achievement in self._achievements:
            return 0.0
        self._achievements.add(achievement)
        return points

    def reset(self) -> CloudObservation:  # type: ignore[override]
        """Reset the environment to the initial state for the selected task."""
        self._achievements.clear()
        self._state_data = CloudState(
            episode_id=str(uuid4()),
            task_difficulty=self.task_name,
            resources=copy.deepcopy(self._build_task_resources()),
            step_count=0,
            is_resolved=False,
        )

        return CloudObservation(
            output=(
                "Environment initialized. System status is currently CRITICAL. "
                "Use 'list_resources' to begin triage."
            ),
            error=None,
            system_health_status="CRITICAL",
            done=False,
            reward=0.0,
            metadata={
                "step_count": 0,
                "resolved": False,
                "task": self.task_name,
                "total_resources": len(self._state_data.resources),
            },
            echoed_message="Cloud Devops Env environment ready!",
            message_length=0,
        )

    def step(self, action: CloudAction) -> CloudObservation:  # type: ignore[override]
        """Execute the agent action and return the next observation."""
        if self._state_data is None:
            self.reset()

        assert self._state_data is not None
        state = self._state_data

        state.step_count += 1
        reward = 0.0
        done = False
        output = ""
        error = None

        try:
            if action.command == "list_resources":
                res_list = [
                    f"{resource_id} ({data['type']})"
                    for resource_id, data in sorted(state.resources.items())
                ]
                output = "Available Resources:\n" + "\n".join(res_list)

            elif action.command == "describe_resource":
                if not action.resource_id or action.resource_id not in state.resources:
                    raise ValueError(f"Resource {action.resource_id} not found.")

                output = str(state.resources[action.resource_id])

                if self.task_name == "easy" and action.resource_id == "sg-web":
                    reward += self._reward_once("read_sg", 0.2)
                elif self.task_name == "medium" and action.resource_id == "sg-db":
                    reward += self._reward_once("read_sg", 0.2)
                elif self.task_name == "hard" and action.resource_id == "i-web2":
                    reward += self._reward_once("inspect_target", 0.2)

            elif action.command == "view_logs":
                if not action.resource_id:
                    raise ValueError("resource_id is required for view_logs.")

                res = state.resources.get(action.resource_id)
                if not res:
                    raise ValueError(f"Resource {action.resource_id} not found.")

                output = str(res.get("logs", "No logs available for this resource."))

                if self.task_name == "medium" and action.resource_id == "i-api":
                    reward += self._reward_once("read_logs", 0.2)
                elif self.task_name == "hard" and action.resource_id == "lb-main":
                    reward += self._reward_once("inspect_lb", 0.2)
                elif self.task_name == "hard" and action.resource_id == "i-web2":
                    reward += self._reward_once("inspect_target", 0.2)

            elif action.command == "update_security_group":
                if not action.resource_id:
                    raise ValueError("resource_id is required for update_security_group.")

                res = state.resources.get(action.resource_id)
                if not res or res.get("type") != "SecurityGroup":
                    raise ValueError(f"Invalid Security Group ID: {action.resource_id}")
                if not action.parameters or "port" not in action.parameters:
                    raise ValueError("Missing 'port' in parameters.")

                rule = copy.deepcopy(action.parameters)
                rules = res.get("rules")
                if not isinstance(rules, list):
                    raise ValueError(f"Security group {action.resource_id} has invalid rules.")
                rules.append(rule)
                output = f"Successfully updated {action.resource_id} with rule: {rule}"

                port = int(rule["port"])
                if (
                    self.task_name == "easy"
                    and action.resource_id == "sg-web"
                    and port == 80
                ):
                    state.is_resolved = True
                    reward += 0.8
                    done = True
                    output += "\nSUCCESS: Web server is now accessible!"
                elif (
                    self.task_name == "medium"
                    and action.resource_id == "sg-db"
                    and port == 5432
                ):
                    if "read_logs" in self._achievements:
                        state.is_resolved = True
                        reward += 0.6
                        done = True
                        output += "\nSUCCESS: Database connection restored!"
                    else:
                        reward -= 0.1
                        output += (
                            "\nWARNING: Change applied without incident triage. "
                            "Inspect API logs before closing the incident."
                        )

            elif action.command == "restart_service":
                if not action.resource_id:
                    raise ValueError("resource_id is required for restart_service.")
                if action.resource_id not in state.resources:
                    raise ValueError(f"Resource {action.resource_id} not found.")

                output = f"Service on {action.resource_id} restarted."

                if self.task_name == "hard":
                    if action.resource_id == "i-web2":
                        investigated_root_cause = (
                            "inspect_lb" in self._achievements
                            and "inspect_target" in self._achievements
                        )
                        if investigated_root_cause:
                            state.resources["i-web2"]["status"] = "running"
                            state.resources["i-web2"][
                                "logs"
                            ] = "INFO: Restart successful. Memory cleared."
                            state.is_resolved = True
                            reward += 0.8
                            done = True
                            output += "\nSUCCESS: OutOfMemory loop broken. System stable."
                        else:
                            reward -= 0.1
                            output += (
                                "\nWARNING: Restart denied by change policy. "
                                "Find failing upstream from lb-main and inspect i-web2 first."
                            )
                    elif action.resource_id == "i-web1":
                        reward -= 0.2
                        output += (
                            "\nWARNING: You restarted a healthy production server! "
                            "Users dropped."
                        )

            elif action.command == "submit_solution":
                if state.is_resolved:
                    done = True
                    output = "Solution verified. System is HEALTHY."
                else:
                    if self.task_name == "hard":
                        # In hard mode, unresolved submission should not abort the run.
                        done = False
                        reward -= 0.1
                        output = (
                            "Solution incorrect. Incident is still CRITICAL. "
                            "Continue triage and remediation before submitting."
                        )
                    else:
                        done = True
                        output = "Solution incorrect. System is still CRITICAL."

            else:
                raise ValueError(f"Unsupported command: {action.command}")

        except Exception as exc:
            error = str(exc)
            output = f"Command Failed: {error}"

        if state.step_count >= self.MAX_STEPS and not done:
            done = True
            timeout_suffix = "\nTIMEOUT: Max steps reached."
            output = f"{output}{timeout_suffix}" if output else timeout_suffix.strip()

        reward = max(-1.0, min(1.0, reward))
        status = "HEALTHY" if state.is_resolved else "CRITICAL"
        info = {
            "step_count": state.step_count,
            "resolved": state.is_resolved,
            "task": self.task_name,
            "achievements": sorted(self._achievements),
            "total_resources": len(state.resources),
        }

        return CloudObservation(
            output=output,
            error=error,
            system_health_status=status,
            done=done,
            reward=reward,
            metadata=info,
            echoed_message=output,
            message_length=len(output),
        )

    @property
    def state(self) -> State:
        """Return hidden environment state for evaluators/debugging."""
        if self._state_data is None:
            self.reset()
        assert self._state_data is not None
        return self._state_data
