# Cloud DevOps RLEnv

Use this page as your in-app playbook while interacting with the environment.

## Mission

You are an incident responder in a simulated cloud production system.

Your goal is to:
1. Investigate symptoms quickly.
2. Identify root cause.
3. Apply the correct remediation.
4. Confirm resolution with minimal unsafe actions.

## Command Cheat Sheet

- `list_resources`
	- Use first in almost every run.
	- Helps separate real targets from decoy resources.

- `describe_resource(resource_id)`
	- Use for configuration/state inspection.
	- Helpful before mutating operations.

- `view_logs(resource_id)`
	- Primary root-cause signal for medium/hard tasks.
	- Often required for best reward path.

- `update_security_group(resource_id, parameters)`
	- Requires `parameters.port`.
	- Typical payload: `{ "port": 80, "action": "allow" }`.

- `restart_service(resource_id)`
	- Use only after diagnosis on hard task.
	- Restarting the wrong host is penalized.

- `submit_solution`
	- Ends easy/medium if solved.
	- In hard task, unresolved submit may continue with penalty.

## Rewards And Guardrails

- Positive rewards are given for meaningful diagnosis + correct fixes.
- Penalties are applied for premature or unsafe actions.
- Step reward is clipped to `[-1.0, 1.0]`.
- Final task score is kept strictly inside `(0.0, 1.0)` for submission validator compatibility.
- Episode ends on success or timeout (`MAX_STEPS = 20`).

## Task Playbooks

### Easy (Web Access Issue)

Objective:
- Open port `80` on `sg-web`.

Recommended path:
1. `list_resources`
2. `describe_resource("sg-web")`
3. `update_security_group("sg-web", {"port": 80, "action": "allow"})`

Notes:
- Includes one optional investigation reward step.

### Medium (API to DB Connectivity)

Objective:
- Confirm DB timeout from logs, then open port `5432` on `sg-db`.

Recommended path:
1. `list_resources`
2. `view_logs("i-api")`
3. `describe_resource("sg-db")` (optional but useful)
4. `update_security_group("sg-db", {"port": 5432, "action": "allow"})`

Important:
- Updating SG before checking `i-api` logs can incur penalty and may not resolve.

### Hard (Upstream Timeout / Wrong Host Risk)

Objective:
- Trace LB errors to `i-web2`, inspect target, then restart `i-web2`.

Recommended path:
1. `list_resources`
2. `view_logs("lb-main")`
3. `describe_resource("i-web2")` or `view_logs("i-web2")`
4. `restart_service("i-web2")`

Important:
- Restarting `i-web1` is penalized.
- Restarting `i-web2` before investigation is also penalized.

## Response Fields You Should Watch

- `output`: command result text
- `error`: failure reason, if any
- `system_health_status`: CRITICAL / DEGRADED / HEALTHY
- `reward`: current step reward
- `done`: whether episode ended
- `metadata`: task, step_count, resolved, achievements

## Baseline Targets

Deterministic scripted policy targets:
- easy: `1.0`
- medium: `0.8` to `1.0`
- hard: `1.0`

LLM comparison:
- gemma-3-27b-it: easy `0.2`, medium `0.2`
- gemma-4-31b-it: easy `1.0`, medium `1.0`

## Inference Contract (for submission)

`inference.py` must:
- use OpenAI client
- read `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`
- emit strict markers: `[START]`, `[STEP]`, `[END]`

## Practical Strategy

- Do not mutate first; inspect first.
- Use logs to justify each remediation.
- Prefer minimal, targeted changes.
- Avoid restart actions unless root cause points there.
