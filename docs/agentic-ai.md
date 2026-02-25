# Agentic AI execution design notes

This note defines controls for tenant-safe agentic AI workflows in EDMP.

## Goals

* Ensure agent execution remains tenant-isolated and auditable.
* Restrict agents to approved tools and bounded runtime.
* Integrate agent execution with RabbitMQ eventing conventions.

## Guardrail requirements

* Agent runs must carry explicit tenant context.
* Tools are allowlisted; no arbitrary tool invocation.
* Direct database access from agents is prohibited.
* Execution timeout and cancellation must be enforced per run.
* Prompts and outputs are logged with retention controls.

## Execution lifecycle

1. User/system requests agent run.
2. Policy and role checks authorize run + tool set.
3. Run is enqueued and executed in tenant context.
4. Start/completion/failure events are emitted.
5. Audit record stores inputs, outputs, tool invocations, and outcome metadata.

## Required event fields

* `tenant_id`
* `correlation_id`
* `run_id`
* `actor_id` (when user-initiated)
* `timestamp`

## Non-goals (this increment)

* Unrestricted autonomous execution across all platform resources.
* Long-lived agents bypassing governance and approval paths.
