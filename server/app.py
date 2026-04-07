# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI application for the Cloud Devops Env Environment.

This module creates an HTTP server that exposes the CloudDevopsEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions

Usage:
    # Development (with auto-reload):
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 4

    # Or run directly:
    python -m server.app
"""

import os
from pathlib import Path

# Default to enabling the OpenEnv web interface for local development.
# You can still disable it explicitly: ENABLE_WEB_INTERFACE=false
os.environ.setdefault("ENABLE_WEB_INTERFACE", "true")
os.environ.setdefault(
    "ENV_README_PATH",
    str((Path(__file__).resolve().parent.parent / "README.md")),
)

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required for the web interface. Install dependencies with '\n    uv sync\n'"
    ) from e

try:
    from ..models import CloudDevopsAction, CloudDevopsObservation
    from .cloud_devops_env_environment import CloudDevopsEnvironment
except (ModuleNotFoundError, ImportError):
    from models import CloudDevopsAction, CloudDevopsObservation
    from server.cloud_devops_env_environment import CloudDevopsEnvironment


# Create the app with web interface and README integration
app = create_app(
    CloudDevopsEnvironment,
    CloudDevopsAction,
    CloudDevopsObservation,
    env_name="cloud_devops_env",
    max_concurrent_envs=1,  # increase this number to allow more concurrent WebSocket sessions
)


def main(host: str | None = None, port: int | None = None):
    """
    Entry point for direct execution via uv run or python -m.

    This function enables running the server without Docker:
        uv run --project . server
        uv run --project . server --port 8001
        python -m cloud_devops_env.server.app

    Args:
        host: Host address to bind to. If not provided, CLI args are parsed.
        port: Port number to listen on. If not provided, CLI args are parsed.

    For production deployments, consider using uvicorn directly with
    multiple workers:
        uvicorn cloud_devops_env.server.app:app --workers 4
    """
    import argparse
    import uvicorn

    # Console-script entry points invoke main() with no parameters, so parse
    # CLI flags here to make `server --host ... --port ...` work as expected.
    if host is None and port is None:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--host", type=str, default="0.0.0.0")
        parser.add_argument("--port", type=int, default=8000)
        args, _ = parser.parse_known_args()
        host = args.host
        port = args.port

    uvicorn.run(app, host=host or "0.0.0.0", port=port or 8000)


if __name__ == "__main__":
    main()
