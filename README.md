---
title: Cloud-DevOps-RLEnv
emoji: ☁️
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 8000
tags:
- openenv
---

# Cloud DevOps RLEnv

Cloud DevOps RLEnv is an OpenEnv-compatible environment for training and evaluating agents on realistic cloud SRE and DevOps incident-response tasks.

## Environment Description And Motivation

Production incidents are often multi-step: triage, inspect resources, check logs, apply a safe remediation, and then verify the fix. This environment simulates that loop with deterministic scenarios and shaped rewards.

Goals:
- Benchmark planning and tool-use behavior for cloud operations agents.
- Reward correct diagnosis over blind action execution.
- Provide repeatable task outcomes for fair grading and comparison.

## Action Space

Action model: `CloudAction`

Fields:
- `command` (required): one of `list_resources`, `describe_resource`, `view_logs`, `update_security_group`, `restart_service`, `submit_solution`.
- `resource_id` (optional): target resource identifier (required for most non-list actions).
- `parameters` (optional): structured key/value arguments used by mutating actions.

Notes:
- `update_security_group` expects `parameters.port` and usually `parameters.action`.
- `restart_service` targets a single instance by `resource_id`.

## Observation And State Space

Observation model: `CloudObservation`

Primary observation fields:
- `output`: command result payload.
- `error`: command error, when present.
- `system_health_status`: `CRITICAL`, `DEGRADED`, or `HEALTHY`.
- `done`: terminal flag.
- `reward`: scalar step reward.
- `metadata`: includes task name, resolution status, step count, and other diagnostics.

Hidden state model: `CloudState`
- `task_difficulty`: `easy`, `medium`, or `hard`.
- `resources`: underlying resource graph and logs.
- `step_count`: total actions issued.
- `is_resolved`: whether incident root cause is remediated.

## Task Definitions And Expected Difficulty

- `easy`:
	Open port `80` on `sg-web` so web traffic can flow.
	Expected difficulty: low.
- `medium`:
	Inspect API logs to identify DB connectivity failure, then open port `5432` on `sg-db`.
	Expected difficulty: medium (requires diagnosis before remediation).
- `hard`:
	Trace load balancer timeout to `i-web2`, inspect the target, then restart the correct service.
	Expected difficulty: high (multi-hop diagnosis and anti-shortcut checks).

## Setup And Usage

From repository root:

```bash
# Validate OpenEnv package structure and manifest
..\\.venv\\Scripts\\openenv validate

# Run pre-submission validator (skip live inference)
bash scripts/pre_submit_validate.sh --skip-inference

# Build local submission image
docker build -t cloud-devops-env:phase1 -f Dockerfile .
```

Optional local server run:

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

## Inference Contract

`inference.py` uses the OpenAI client and reads the following environment variables:
- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`

It emits strict structured logs:
- `[START] { ... }` per task
- `[STEP] { ... }` per environment action
- `[END] { ... }` per task summary

## Baseline Scores

Representative deterministic scripted-policy targets:

| Task | Baseline Score (0-1) | Notes |
| --- | --- | --- |
| easy | 1.0 | Includes identifying and fixing security group rule |
| medium | 0.8-1.0 | Depends on whether optional diagnostic reward is collected |
| hard | 1.0 | Requires correct root-cause path before restart |

Validation expectation:
- Aggregate scores are clamped to `[0.0, 1.0]`.
- `SUCCESS_SCORE_THRESHOLD` for inference summaries is `0.8`.

## Hugging Face Space Deployment

1. Push this repository to your Space (Docker SDK).
2. Ensure `README.md` front matter (above) is present.
3. Set Space secrets/variables:
	 - `HF_TOKEN` (secret)
	 - `API_BASE_URL` (for example `https://router.huggingface.co/v1`)
	 - `MODEL_NAME` (chosen model slug)
4. Wait for Space build to complete.
5. Verify endpoints:
	 - `GET /health` returns `200`
	 - `POST /reset` returns `200`

Reference: https://huggingface.co/docs/hub/spaces-config-reference
