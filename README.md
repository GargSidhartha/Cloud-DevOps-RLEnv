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

## Judge-Aligned Snapshot

| Parameter | Weight | How this environment addresses it |
| --- | --- | --- |
| Real-world utility | 30% | Models practical SRE outage response loops: telemetry triage, dependency mapping, and safe remediation. |
| Task & grader quality | 25% | Three deterministic tasks with explicit objectives, strict success gates, and reproducible scoring behavior. |
| Environment design | 20% | Typed action/observation/state models, clean reset semantics, shaped rewards, action-cost efficiency pressure, clear boundaries. |
| Code quality & spec compliance | 15% | OpenEnv-compliant project layout, Dockerized runtime, strict inference output contract, validation scripts. |
| Creativity & novelty | 10% | Multi-hop metadata dependency, cascading failures, high-decoy search space, and safety-aware penalties. |

## Why This Environment

Real incidents are multi-step and noisy. Good agents must:
- gather context before changing systems
- identify root cause from logs and topology
- apply minimal, correct fixes
- verify resolution

Cloud DevOps RLEnv simulates that behavior with realistic failure patterns, decoy resources, shaped rewards, and anti-shortcut guardrails.

## Why It's Hard

This benchmark is intentionally designed to resist brute-force policies and reward disciplined SRE reasoning:

- Needle-in-a-haystack discovery: 20+ decoy compute nodes and 20+ decoy security groups increase search complexity.
- Ambiguous telemetry: noisy, raw operational logs surface symptoms (including IP-only clues) rather than direct root-cause labels.
- Action-penalty heuristics: every action has a small negative cost, so efficient remediation beats command spamming.
- Multi-hop dependency resolution: agents must map IP addresses to resource IDs via metadata lookup before applying fixes.
- System drift under pressure: in hard mode, delayed remediation triggers cascading failures that worsen observability and reward dynamics.

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
| command | enum | yes | One of: list_resources, describe_resource, view_logs, query_metadata, update_security_group, restart_service, submit_solution |
| resource_id | string | conditional | Required for most actions except list_resources and query_metadata |
| parameters | object | conditional | Used by mutating actions (for example, security-group updates) |

Action semantics:
- list_resources: Enumerates available resources including decoys.
- describe_resource: Returns structured details for one resource.
- view_logs: Returns logs for one resource.
- query_metadata: Resolves infrastructure metadata (for example, IP address to resource ID).
- update_security_group: Appends a rule (requires parameters.port and parameters.action where action is allow/deny).
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
- fixed action cost per step (efficiency pressure)
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
- ~0.97 for full playbook with efficient triage
- ~0.79 if agent skips the optional read step

### Medium Task

Incident:
- API cannot reach DB due to blocked port 5432.

Objective:
- Confirm root cause from logs, then open port 5432 on sg-db.

Typical successful sequence:
1. list_resources
2. view_logs(i-api) to identify DB timeout (+0.2)
3. query_metadata(ip_address=10.0.4.5) to resolve DB target (+0.2)
4. update_security_group(sg-db, port=5432, action=allow) (+0.6, done if logs and metadata lookup were completed)

Guardrail:
- Applying the SG change before log triage + metadata lookup gives a penalty (-0.1) and does not close the incident.

Expected score:
- ~0.97 with full investigative path (logs -> metadata lookup -> remediation)
- below ~0.90 when metadata dependency is skipped

## Determinism And Grader Transparency

- Deterministic reset and transitions: no randomization is used in task generation or transition logic.
- Transparent grading signals: observation metadata includes achievements, resolution status, termination reason, and reward breakdown events.
- Reproducibility helper:

```bash
..\\.venv\\Scripts\\python scripts/reproducibility_check.py
```

### Hard Task

Incident:
- Checkout path degraded due to upstream timeout to an IP-only target that must be resolved first.

Objective:
- Trace LB errors to the correct target, resolve resource identity via metadata, and restart i-web2 only after diagnosis.

Typical successful sequence:
1. list_resources
2. view_logs(lb-main) to identify failing upstream IP (+0.2)
3. query_metadata(ip_address=<failing_ip>) to resolve target ID (+0.2)
4. describe_resource(i-web2) or view_logs(i-web2) (+0.2)
5. restart_service(i-web2) (+0.8, done when all investigation achievements exist)

Guardrails:
- Restarting i-web2 before investigation: penalty (-0.1), no resolution.
- Restarting healthy i-web1: penalty (-0.2).
- Premature submit_solution in hard mode: penalty (-0.1), episode continues.
- If unresolved after step 8 in hard mode, lb-external also fails (cascading failure), increasing pressure and noise.

Expected score:
- near 1.0 after score clamping for strong trajectories (can exceed 1.0 raw before clamp)

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
- MODEL_NAME default: google/gemma-4-26B-A4B-it
- MAX_STEPS (in inference loop): 15
- success flag is derived from environment resolution state

## Baselines

### Deterministic task baselines

| Task | Typical baseline score |
| --- | --- |
| easy | 0.78 |
| medium | 0.96 |
| hard | 0.999 |

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

# Determinism/reproducibility smoke test
..\\.venv\\Scripts\\python scripts/reproducibility_check.py

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
