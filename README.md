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

Cloud DevOps RLEnv is an OpenEnv-compatible cloud incident-response benchmark designed for agentic SRE and DevOps workflows.

This environment rewards correct diagnosis and safe remediation, not blind action execution. It is deterministic, reproducible, and optimized for hackathon evaluation.

## Why This Environment

Real incidents are multi-step and noisy. Good agents must:
- gather context before changing systems
- identify root cause from logs and topology
- apply minimal, correct fixes
- verify resolution

Cloud DevOps RLEnv simulates that behavior with realistic failure patterns, decoy resources, shaped rewards, and anti-shortcut guardrails.

## Environment Scope

- Domain: Cloud SRE / DevOps incident response
- Difficulty tiers: easy, medium, hard
- Max environment steps per episode: 20
- Runtime health states: CRITICAL, DEGRADED, HEALTHY
- Decoy resources: 20 backend instances + 20 backend security groups

## OpenEnv Compliance

Core files:
- openenv.yaml
- env.py
- models.py
- inference.py
- server/app.py
- server/cloud_devops_env_environment.py

Validator command:

```bash
..\\.venv\\Scripts\\openenv validate
```

## Action Space

Model: CloudAction

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| command | enum | yes | One of: list_resources, describe_resource, view_logs, update_security_group, restart_service, submit_solution |
| resource_id | string | conditional | Required for most actions except list_resources |
| parameters | object | conditional | Used by mutating actions (for example, security-group updates) |

Action semantics:
- list_resources: Enumerates available resources including decoys.
- describe_resource: Returns structured details for one resource.
- view_logs: Returns logs for one resource.
- update_security_group: Appends a rule (requires parameters.port).
- restart_service: Restarts one instance/service by ID.
- submit_solution: Declares the episode solved (or not solved).

## Observation And State Space

Observation model: CloudObservation

| Field | Description |
| --- | --- |
| output | Main command output |
| error | Error string for failed commands |
| system_health_status | CRITICAL, DEGRADED, HEALTHY |
| done | Episode terminal flag |
| reward | Step reward |
| metadata | Diagnostics such as task, step_count, resolved, achievements |

Hidden state model: CloudState

| Field | Description |
| --- | --- |
| task_difficulty | easy, medium, hard |
| resources | Full resource graph including logs/rules |
| step_count | Current step counter |
| is_resolved | Whether root cause has been fixed |

## Reward Design

Reward shaping is sparse-but-guided:
- discovery rewards for correct investigative steps
- larger terminal rewards for correct remediation
- penalties for unsafe or premature operations
- timeout terminal condition after max steps

Per-step reward is clipped to [-1.0, 1.0].
Inference task score is adjusted to remain strictly within (0.0, 1.0) for Phase-2 validator compatibility.

## Detailed Task Playbooks

### Easy Task

Incident:
- Web traffic blocked by security group.

Objective:
- Open port 80 on sg-web.

Typical successful sequence:
1. list_resources
2. describe_resource(sg-web) for context (+0.2)
3. update_security_group(sg-web, port=80, action=allow) (+0.8, done)

Expected score:
- 1.0 for full playbook
- 0.8 if agent skips the optional read step

### Medium Task

Incident:
- API cannot reach DB due to blocked port 5432.

Objective:
- Confirm root cause from logs, then open port 5432 on sg-db.

Typical successful sequence:
1. list_resources
2. view_logs(i-api) to identify DB timeout (+0.2)
3. describe_resource(sg-db) optional context (+0.2)
4. update_security_group(sg-db, port=5432, action=allow) (+0.6, done if logs were inspected)

Guardrail:
- Applying the SG change before log triage gives a penalty (-0.1) and does not close the incident.

Expected score:
- 1.0 with full investigative path
- 0.8 if SG describe step is skipped but log triage is done

### Hard Task

Incident:
- Checkout path degraded due to upstream timeout to i-web2.

Objective:
- Trace LB errors to the correct target and restart i-web2 only after diagnosis.

Typical successful sequence:
1. list_resources
2. view_logs(lb-main) to identify failing upstream i-web2 (+0.2)
3. describe_resource(i-web2) or view_logs(i-web2) (+0.2)
4. restart_service(i-web2) (+0.8, done when both investigation achievements exist)

Guardrails:
- Restarting i-web2 before investigation: penalty (-0.1), no resolution.
- Restarting healthy i-web1: penalty (-0.2).
- Premature submit_solution in hard mode: penalty (-0.1), episode continues.

Expected score:
- 1.0 after score clamping for the full correct path

## API Endpoints

Core runtime:
- GET /health
- POST /reset
- POST /step
- GET /state
- GET /schema
- WS /ws

Web UI runtime:
- GET /web
- POST /web/reset
- POST /web/step
- GET /web/state
- GET /web/metadata

## Inference Contract

inference.py requirements:
- uses OpenAI client
- reads API_BASE_URL, MODEL_NAME, HF_TOKEN
- emits strict logs: [START], [STEP], [END]

Current defaults in code:
- MODEL_NAME default: google/gemma-4-31B-it
- MAX_STEPS (in inference loop): 15
- SUCCESS_SCORE_THRESHOLD: 0.8

## Baselines

### Deterministic task baselines

| Task | Typical baseline score |
| --- | --- |
| easy | 1.0 |
| medium | 0.8 to 1.0 |
| hard | 1.0 (after clamp) |

### LLM policy comparison

| Model | Easy | Medium | Summary |
| --- | --- | --- | --- |
| gemma-3-27b-it | 0.2 | 0.2 | Underperformed on this environment |
| gemma-4-31b-it | 1.0 | 1.0 | Perfect on both easy and medium |

## Local Setup And Validation

From repository root:

```bash
# Structure + manifest validation
..\\.venv\\Scripts\\openenv validate

# Submission-oriented local checks (without live inference)
bash scripts/pre_submit_validate.sh --skip-inference

# Build local image
docker build -t cloud-devops-env:phase1 -f Dockerfile .
```

Optional local server:

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

## Hugging Face Space Deployment

1. Keep this front matter block intact (includes mandatory openenv tag).
2. Push to Space (Docker SDK).
3. Configure secrets/variables:
   - HF_TOKEN
   - API_BASE_URL (for example https://router.huggingface.co/v1)
   - MODEL_NAME
4. Wait for build completion.
5. Verify:
   - GET /health returns 200
   - POST /reset returns 200

Reference:
- https://huggingface.co/docs/hub/spaces-config-reference
