# Cloud DevOps RLEnv Web Playbook

Use this page as your operator guide when stepping through incidents in /web.

## Mission

You are the on-call SRE for a production outage.

Your loop is always:

1. Triage quickly.
2. Confirm root cause.
3. Apply the minimum safe fix.
4. Verify health and close.

## What Makes This Environment Non-Trivial

- Large decoy inventory: many resources are intentionally irrelevant.
- Ambiguous telemetry: medium/hard logs expose failing IPs, not only direct IDs.
- Action cost: every step incurs a small penalty, so efficient plans outperform exploratory spam.
- Hard-mode drift: delayed remediation causes additional system degradation.

## Command Reference

### list_resources

- Purpose: enumerate all available entities.
- Use first in most runs.
- Required fields: command only.

### describe_resource

- Purpose: inspect one resource configuration or current state.
- Required fields: resource_id.

### view_logs

- Purpose: read operational telemetry for one resource.
- Required fields: resource_id.

### query_metadata

- Purpose: resolve metadata such as ip_address -> resource_id.
- Required fields: parameters.ip_address.
- Typical medium/hard bridge action before mutation.

### update_security_group

- Purpose: mutate network policy.
- Required fields: resource_id, parameters.port, parameters.action.
- Valid action values: allow, deny.

### restart_service

- Purpose: restart a target service/instance.
- Required fields: resource_id.
- Use only after root-cause confirmation.

### submit_solution

- Purpose: attempt to close incident.
- Hard mode may continue with penalty if unresolved.

## JSON Action Examples

```json
{"command":"list_resources"}
```

```json
{"command":"view_logs","resource_id":"i-api"}
```

```json
{"command":"query_metadata","parameters":{"ip_address":"10.0.4.5"}}
```

```json
{"command":"update_security_group","resource_id":"sg-db","parameters":{"port":5432,"action":"allow"}}
```

```json
{"command":"restart_service","resource_id":"i-web2"}
```

## Task Playbooks

### Easy: Web Access Recovery

Objective:

- Open port 80 on sg-web.

Strong path:

1. list_resources
2. update_security_group(sg-web, port=80, action=allow)

Optional safer path (slightly lower efficiency):

1. list_resources
2. describe_resource(sg-web)
3. update_security_group(sg-web, port=80, action=allow)

### Medium: API to DB Connectivity

Objective:

- Restore DB access by opening 5432 on sg-db, but only after diagnosis.

Strong path:

1. list_resources
2. view_logs(i-api)
3. query_metadata(ip_address=10.0.4.5)
4. update_security_group(sg-db, port=5432, action=allow)

Guardrail:

- Mutating sg-db before logs + metadata lookup is penalized and does not resolve.

### Hard: Upstream Failure Under Drift

Objective:

- Find failing upstream from lb-main logs, resolve target identity, inspect, then restart i-web2.

Strong path:

1. list_resources
2. view_logs(lb-main)
3. query_metadata(ip_address=10.0.8.22)
4. describe_resource(i-web2) or view_logs(i-web2)
5. restart_service(i-web2)

Guardrails:

- Restarting i-web1 is penalized.
- Restarting i-web2 before investigation is penalized and blocked from resolution.
- If unresolved after step 8, lb-external also fails (cascading failure).

## Rewards, Termination, And Score Semantics

- Every action includes a small cost.
- Discovery and correct remediation provide shaped positive rewards.
- Unsafe or premature actions apply penalties.
- Episode terminates on resolution or max step limit.
- Submission score is clamped to a strict open interval (0,1).
- success reflects actual incident resolution state.

## Observation Fields To Monitor

- output: command result text
- error: command-level error string
- system_health_status: CRITICAL, DEGRADED, HEALTHY
- reward: step reward
- done: episode termination flag
- metadata: task, step_count, resolved, achievements, action_cost

## Submission Contract Reminder

inference.py must:

- use OpenAI client
- read API_BASE_URL, MODEL_NAME, HF_TOKEN
- emit strict stdout lines with START, STEP, END markers

Practical strategy:

- Inspect first, mutate second.
- Use query_metadata whenever logs give only IP clues.
- Prefer minimal actions for higher score.
