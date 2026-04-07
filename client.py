# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Cloud Devops Env Environment Client."""

from typing import Any, Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from .models import CloudAction, CloudObservation


class CloudDevopsEnv(
    EnvClient[CloudAction, CloudObservation, State]
):
    """
    Client for the Cloud Devops Env Environment.

    This client maintains a persistent WebSocket connection to the environment server,
    enabling efficient multi-step interactions with lower latency.
    Each client instance has its own dedicated environment session on the server.

    Example:
        >>> # Connect to a running server
        >>> with CloudDevopsEnv(base_url="http://localhost:8000") as client:
        ...     result = client.reset()
        ...     print(result.observation.system_health_status)
        ...
        ...     result = client.step(CloudAction(command="list_resources"))
        ...     print(result.observation.output)

    Example with Docker:
        >>> # Automatically start container and connect
        >>> client = CloudDevopsEnv.from_docker_image("cloud_devops_env-env:latest")
        >>> try:
        ...     result = client.reset()
        ...     result = client.step(CloudAction(command="list_resources"))
        ... finally:
        ...     client.close()
    """

    def _step_payload(self, action: CloudAction) -> Dict[str, Any]:
        """
        Convert CloudAction to JSON payload for step message.

        Args:
            action: CloudAction instance

        Returns:
            Dictionary representation suitable for JSON encoding
        """
        payload: Dict[str, Any] = {
            "command": action.command,
            "resource_id": action.resource_id,
            "parameters": action.parameters,
        }
        if action.message is not None:
            payload["message"] = action.message
        return payload

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[CloudObservation]:
        """
        Parse server response into StepResult[CloudObservation].

        Args:
            payload: JSON response data from server

        Returns:
            StepResult with CloudObservation
        """
        obs_data = payload.get("observation", {})
        observation = CloudObservation(
            output=obs_data.get("output", ""),
            error=obs_data.get("error"),
            system_health_status=obs_data.get("system_health_status", "CRITICAL"),
            message_length=obs_data.get("message_length", 0),
            echoed_message=obs_data.get("echoed_message"),
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=obs_data.get("metadata", {}),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict[str, Any]) -> State:
        """
        Parse server response into State object.

        Args:
            payload: JSON response from state request

        Returns:
            State object with episode_id and step_count
        """
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
