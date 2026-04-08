# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Cloud Devops Env Environment.

The cloud_devops_env environment simulates cloud/devops incident response tasks.
"""

import json
from typing import Any, Dict, Literal, Optional

from openenv.core.env_server.types import Action, Observation, State
from pydantic import Field, field_validator


class CloudAction(Action):
    """Action space (what the agent can do)."""

    command: Literal[
        "list_resources",
        "describe_resource",
        "view_logs",
        "query_metadata",
        "update_security_group",
        "restart_service",
        "submit_solution",
    ] = Field(..., description="The cloud API command to execute.")
    resource_id: Optional[str] = Field(
        default=None,
        description=(
            "The ID of the target resource (e.g., 'i-12345'). "
            "Required for most commands except list_resources and query_metadata."
        ),
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Key-value pairs for updates "
            "(e.g., {'port': '80', 'action': 'allow'} for update_security_group, "
            "or {'ip_address': '10.0.4.5'} for query_metadata)."
        ),
    )
    message: Optional[str] = Field(
        default=None,
        description="Legacy field from template env; safe to remove after server/client migration.",
    )

    @field_validator("parameters", mode="before")
    @classmethod
    def _coerce_parameters(cls, value: Any) -> Any:
        """Allow /web text input to pass JSON for dict parameters."""
        if value is None or value == "":
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "parameters must be a JSON object string, e.g. {\"port\":80,\"action\":\"allow\"}"
                ) from exc
            if not isinstance(parsed, dict):
                raise ValueError("parameters JSON must decode to an object/dictionary")
            return parsed
        raise ValueError("parameters must be a dictionary or JSON object string")


class CloudObservation(Observation):
    """Observation space (what the agent sees)."""

    output: str = Field(
        ...,
        description="The terminal/API response from the last command executed.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if the last command failed or was invalid.",
    )
    system_health_status: str = Field(
        ...,
        description="Current status of the system (e.g., 'CRITICAL', 'DEGRADED', 'HEALTHY').",
    )
    echoed_message: Optional[str] = Field(
        default=None,
        description="Legacy field from template env; safe to remove after server/client migration.",
    )
    message_length: int = Field(
        default=0,
        description="Legacy field from template env; safe to remove after server/client migration.",
    )


class CloudState(State):
    """State space (the hidden environment state)."""

    task_difficulty: str = Field(..., description="Current task: easy, medium, or hard.")
    resources: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="The hidden JSON state of all mock cloud resources.",
    )
    step_count: int = Field(..., description="Number of actions taken so far.")
    is_resolved: bool = Field(
        ...,
        description="Whether the root cause has been successfully fixed.",
    )


# Backward-compatible aliases for scaffolded files that still use template names.
CloudDevopsAction = CloudAction
CloudDevopsObservation = CloudObservation
