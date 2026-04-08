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

Cloud DevOps RLEnv is an OpenEnv benchmark for real incident-response workflows in cloud production systems.

It is designed to evaluate whether an agent can triage noisy telemetry, identify root cause, apply a safe fix, and do all of this efficiently under cost and pressure.

## Judge-Aligned Snapshot

This section maps the environment directly to the scoring rubric.

| Parameter | Weight | How this environment addresses it |
| --- | --- | --- |
| Real-world utility | 30% | Simulates practical SRE outage response loops: triage logs, map failing dependency, remediate safely, verify health. |
| Task and grader quality | 25% | Three deterministic tasks (easy/medium/hard), explicit objectives, reproducible reward logic, strict success/failure gates. |
| Environment design | 20% | Typed actions and observations, deterministic reset, shaped rewards, action cost, clear episode boundaries and timeout. |
| Code quality and spec compliance | 15% | OpenEnv-compatible layout, typed models, Dockerized runtime, strict inference logging contract, local validators included. |
| Creativity and novelty | 10% | Multi-hop metadata dependency, cascading failure drift, high-decoy infrastructure search, efficiency-aware reward shaping. |

## Real-World Utility

The benchmark models incidents that closely mirror day-2 operations in production:

- Security group misconfiguration blocks service traffic.
- Service-to-database communication fails with telemetry-first diagnosis required.
- Load balancer upstream failures require dependency mapping and targeted restart under time pressure.

This is not a toy command simulator. The hard task requires reasoning over partial evidence and acting safely under drift.

## Why It Is Hard

- Needle-in-a-haystack discovery: 20+ decoy instances and 20+ decoy security groups.
- Ambiguous telemetry: logs expose symptoms and IPs, not always direct resource names.
- Action-cost pressure: every action incurs a negative reward, penalizing brute-force behavior.
- Multi-hop dependency: agent must use metadata resolution before remediation in medium/hard.
- Cascading failures: unresolved hard incidents degrade additional components after step 8.

## Task Suite And Difficulty Progression

| Task | Objective | Required reasoning depth | Typical strong trajectory |
| --- | --- | --- | --- |
| easy | Restore web access by opening port 80 on sg-web | Single-hop config diagnosis | list_resources -> update_security_group(sg-web, allow 80) |
| medium | Restore DB connectivity by opening port 5432 on sg-db | Multi-hop: logs -> IP -> metadata lookup -> fix | list_resources -> view_logs(i-api) -> query_metadata(10.0.4.5) -> update_security_group(sg-db, allow 5432) |
| hard | Recover checkout path by fixing failing upstream i-web2 | Multi-hop + pressure: logs -> IP -> metadata -> inspect -> restart | list_resources -> view_logs(lb-main) -> query_metadata(10.0.8.22) -> describe/view i-web2 -> restart_service(i-web2) |

## Grader Quality And Determinism

- Deterministic state: no RNG in task initialization.
- Deterministic transitions: action handling is rule-based and reproducible.
- Deterministic rewards: shaped by explicit achievement checkpoints and safety penalties.
- Deterministic success: inferred from resolved incident state, not ad hoc heuristics.

Score behavior:

- Step reward is clipped to [-1.0, 1.0].
- Per-task inference score is clamped to strict open interval (0, 1) for validator compatibility.
- Lower-step successful solutions naturally score higher due to per-step action cost.

## Environment Design Details

- Runtime health states: CRITICAL, DEGRADED, HEALTHY.
- Episode limit: 20 environment steps.
- Hard-task drift: if unresolved after step 8, lb-external is marked DOWN.
- Action cost: -0.01 on every step to encourage efficient plans.

### Action Space (CloudAction)

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| command | enum | yes | list_resources, describe_resource, view_logs, query_metadata, update_security_group, restart_service, submit_solution |
| resource_id | string | conditional | Required for most commands except list_resources and query_metadata |
| parameters | object | conditional | Required for query_metadata.ip_address and update_security_group.port/action |

Security-group mutation semantics:

- update_security_group requires both port and action.
- action must be allow or deny.
- Invalid actions are rejected and do not mutate state.

### Observation and State Models

Observation (CloudObservation): output, error, system_health_status, reward, done, metadata.

State (CloudState): task_difficulty, resources, step_count, is_resolved.

## Inference Contract And Compliance

Mandatory environment variables:

- API_BASE_URL
- MODEL_NAME
- HF_TOKEN

Mandatory inference requirements:

- inference.py is at repository root.
- Uses OpenAI client for all LLM calls.
- Emits strict stdout contract only:

```text
[START] task=<task_name> env=<benchmark> model=<model_name>
[STEP] step=<n> action=<action_json_or_str> reward=<0.00> done=<true|false> error=<msg|null>
[END] success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>
```

## Reference Baseline Behavior

Recent deterministic policy-style run with current environment dynamics:

| Task | Steps | Score | Outcome |
| --- | --- | --- | --- |
| easy | 2 | 0.780 | success=true |
| medium | 4 | 0.960 | success=true |
| hard | 5 | 0.999 | success=true |

## Project Layout And Spec Files

Required OpenEnv files are present:

- openenv.yaml
- env.py
- models.py
- inference.py
- server/app.py
- server/cloud_devops_env_environment.py

## Validation And Reproducibility

From repository root:

```bash
# OpenEnv manifest and schema checks
..\\.venv\\Scripts\\openenv validate

# Full submission checks including inference contract
bash scripts/pre_submit_validate.sh --ping-url https://<your-space>.hf.space

# Official 3-step baseline validator
bash scripts/validate-submission.sh https://<your-space>.hf.space .

# Docker smoke test
docker build -t cloud-devops-env:latest -f Dockerfile .
docker run --rm -p 8000:8000 cloud-devops-env:latest
```

## Hugging Face Space Deployment Checklist

1. Keep front matter intact, including openenv tag and app_port 8000.
2. Push latest main branch to the Space repository.
3. Configure API_BASE_URL, MODEL_NAME, HF_TOKEN in Space settings.
4. Wait for build completion and verify endpoints:
   - GET /health -> 200
   - POST /reset -> 200
5. Run inference.py once in Space logs to confirm strict START/STEP/END output.

Reference:

- https://huggingface.co/docs/hub/spaces-config-reference
