# Cloud DevOps RLEnv

This environment trains and tests agents on cloud incident response.

## What You Need To Do

Solve incidents by following the same workflow a real SRE would use:
1. Inspect resources.
2. Read logs.
3. Apply a safe fix.
4. Submit the solution.

## Available Actions

- `list_resources`: See all resources.
- `describe_resource`: View one resource.
- `view_logs`: Read logs for one resource.
- `update_security_group`: Add/modify security rules.
- `restart_service`: Restart an instance.
- `submit_solution`: Submit your final answer.

## What You Receive Each Step

- `output`: Main command result.
- `error`: Error text if a command fails.
- `system_health_status`: `CRITICAL`, `DEGRADED`, or `HEALTHY`.
- `reward`: Step reward.
- `done`: Whether the episode has ended.

## Difficulty Levels

- `easy`: Open port `80` on `sg-web`.
- `medium`: Find DB timeout in logs, then open port `5432` on `sg-db`.
- `hard`: Trace timeout through load balancer to `i-web2`, then restart the correct service.

## Quick Start

Run from repo root:

```bash
..\\.venv\\Scripts\\openenv validate
bash scripts/pre_submit_validate.sh --skip-inference
docker build -t cloud-devops-env:phase1 -f Dockerfile .
```

Run server locally:

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

## Inference Requirements

`inference.py` reads:
- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`

It logs strict markers:
- `[START]`
- `[STEP]`
- `[END]`

## Baseline Score Targets

- easy: `1.0`
- medium: `0.8` to `1.0`
- hard: `1.0`

Scores are clamped to `[0.0, 1.0]`.
