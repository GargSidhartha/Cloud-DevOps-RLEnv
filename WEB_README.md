# Cloud DevOps RLEnv

Use this page as the operator playbook in the /web interface.

## Core Loop

1. Triage quickly.
2. Build evidence from logs and metadata.
3. Apply the minimum safe remediation.
4. Verify resolution and stop.

Why this matters: each action has a cost (`-0.01`), so shorter correct trajectories score higher.

## Command Cheat Sheet

- `list_resources`
: Start here to map real targets vs decoys.

- `describe_resource(resource_id)`
: Inspect config/state details.

- `view_logs(resource_id)`
: Primary source of root-cause evidence.

- `query_metadata(parameters={"ip_address": "..."})`
: Resolve IP-only clues to resource IDs (mandatory multi-hop step in medium/hard).

- `update_security_group(resource_id, parameters)`
: Requires `parameters.port` and `parameters.action` where action is `allow` or `deny`.

- `restart_service(resource_id)`
: Use only after causal evidence confirms target.

- `submit_solution`
: Useful for explicit closure checks; unresolved hard submissions are penalized and continue.

## Task Playbooks

### Easy

Objective:
- Restore web access by allowing port `80` on `sg-web`.

Strong path:
1. `list_resources`
2. `update_security_group("sg-web", {"port": 80, "action": "allow"})`

Typical outcome:
- 2 steps, score around `0.78`

### Medium

Objective:
- Restore API to DB connectivity by allowing port `5432` on `sg-db`.

Strong path:
1. `list_resources`
2. `view_logs("i-api")`
3. `query_metadata({"ip_address": "10.0.4.5"})`
4. `update_security_group("sg-db", {"port": 5432, "action": "allow"})`

Guardrail:
- Applying SG changes before logs + metadata lookup is penalized and does not resolve the incident.

### Hard

Objective:
- Recover checkout flow by identifying the failing upstream and restarting `i-web2` safely.

Strong path:
1. `list_resources`
2. `view_logs("lb-main")`
3. `query_metadata({"ip_address": "10.0.8.22"})`
4. `describe_resource("i-web2")` or `view_logs("i-web2")`
5. `restart_service("i-web2")`

Guardrails:
- Restarting `i-web1` is penalized.
- Restarting `i-web2` without investigation is penalized.
- If unresolved after step 8, `lb-external` also fails (cascading failure).

## Reading Metadata

Watch these response fields each step:

- `system_health_status`: `CRITICAL` / `DEGRADED` / `HEALTHY`
- `done`: episode ended or still running
- `reward`: immediate signal after action cost and shaping
- `metadata.resolved`: authoritative success flag
- `metadata.termination_reason`: why episode ended
- `metadata.reward_breakdown`: transparent reward events for grader/debug inspection

## Submission Contract Reminder

`inference.py` must:

- use OpenAI client
- read `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN`
- emit strict stdout markers: `[START]`, `[STEP]`, `[END]`
