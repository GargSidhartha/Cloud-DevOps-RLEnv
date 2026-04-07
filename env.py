# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Async entrypoint wrapper for external evaluators and custom graders."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel

try:
    from .models import CloudAction, CloudObservation, CloudState
    from .server.cloud_devops_env_environment import CloudDevopsEnvironment
except ImportError:
    from models import CloudAction, CloudObservation, CloudState
    from server.cloud_devops_env_environment import CloudDevopsEnvironment


class EnvResult(BaseModel):
    """Canonical environment result payload for async evaluator loops."""

    observation: CloudObservation
    reward: float
    done: bool
    info: Dict[str, Any]


class CloudDevOpsEnv:
    """Async-compatible facade over the OpenEnv server-side environment logic."""

    def __init__(self, task_name: str = "easy"):
        self._impl = CloudDevopsEnvironment(task_name=task_name)

    @property
    def achievements(self) -> set[str]:
        """Expose completed shaped-reward checkpoints for debugging/evaluation."""
        return set(self._impl._achievements)

    async def reset(self) -> EnvResult:
        """Reset the environment to the initial task state."""
        obs = self._impl.reset()
        return EnvResult(
            observation=obs,
            reward=float(obs.reward or 0.0),
            done=bool(obs.done),
            info=dict(obs.metadata or {}),
        )

    async def step(self, action: CloudAction) -> EnvResult:
        """Execute an action and return a structured async result."""
        obs = self._impl.step(action)
        return EnvResult(
            observation=obs,
            reward=float(obs.reward or 0.0),
            done=bool(obs.done),
            info=dict(obs.metadata or {}),
        )

    async def state(self) -> CloudState:
        """Return hidden environment state for deterministic evaluators."""
        state = self._impl.state
        assert isinstance(state, CloudState)
        return state
