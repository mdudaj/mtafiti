# Platform security baseline design notes

This note defines mandatory platform security controls for EDMP runtime and integrations.

## Goals

* Keep tenant boundaries enforceable at network, identity, and data layers.
* Make security posture auditable and operationally measurable.
* Align controls with Kubernetes-native deployment constraints.

## Mandatory controls

* HTTPS for all external endpoints.
* mTLS for internal service-to-service communication where supported.
* Encrypted database/broker/object-store connections.
* Secrets managed through Kubernetes Secrets or external Vault integration.
* NetworkPolicies limiting ingress/egress to required service paths only.
* Rate limiting and abuse protection at ingress/gateway per tenant.
* Immutable audit trail for security-sensitive actions.
* No plaintext credential storage in code or configuration.

## Operational enforcement points

* Ingress/gateway: TLS termination, authn integration, rate limits.
* Kubernetes: pod security context, network policies, secret mounts.
* Application: tenant-scoped authz checks, correlation ids, audit emission.

## Validation expectations

* Security scan in CI/CD path.
* Tenant boundary tests for API and async paths.
* Credential rotation playbook validated in non-production.

## Non-goals (this increment)

* Full compliance-framework mapping (SOC/ISO controls catalog).
* Product-specific SIEM/SOAR implementation details.
