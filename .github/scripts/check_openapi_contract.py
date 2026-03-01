#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
URLS = ROOT / "backend" / "config" / "urls.py"
OPENAPI = ROOT / "docs" / "openapi.yaml"

CRITICAL_PATHS = {
    "/api/v1/tenants",
    "/api/v1/assets",
    "/api/v1/assets/{asset_id}",
    "/api/v1/ingestions",
    "/api/v1/ingestions/{ingestion_id}",
    "/api/v1/lineage/edges",
    "/api/v1/projects",
    "/api/v1/stewardship/items",
    "/api/v1/stewardship/items/{item_id}/transition",
    "/api/v1/orchestration/workflows",
    "/api/v1/orchestration/runs",
    "/api/v1/orchestration/runs/{run_id}/transition",
    "/api/v1/agent/runs",
    "/api/v1/agent/runs/{run_id}/transition",
    "/api/v1/users",
    "/api/v1/users/{user_id}",
    "/api/v1/notifications",
    "/api/v1/notifications/dispatch",
    "/api/v1/notifications/{notification_id}/retry",
    "/api/v1/projects/{project_id}/members",
    "/api/v1/projects/{project_id}/workspace",
    "/api/v1/projects/{project_id}/members/invite",
    "/api/v1/projects/{project_id}/members/{membership_id}/lifecycle",
    "/api/v1/projects/invitations/accept",
    "/api/v1/projects/invitations/{invitation_id}/revoke",
    "/api/v1/projects/invitations/{invitation_id}/resend",
    "/api/v1/ui/operations/dashboard",
    "/api/v1/ui/operations/stewardship-workbench",
    "/api/v1/ui/operations/orchestration-monitor",
    "/api/v1/ui/operations/agent-monitor",
}

REQUIRED_SCHEMAS = {
    "Error",
    "Tenant",
    "DataAsset",
    "IngestionRequest",
    "LineageQueryResponse",
    "Project",
    "ProjectMembership",
    "ProjectMembershipListResponse",
    "ProjectWorkspace",
    "ProjectInvitation",
    "UserProfile",
    "UserProfileListResponse",
    "StewardshipItem",
    "OrchestrationWorkflow",
    "OrchestrationRun",
    "AgentRun",
    "UserNotification",
    "UserNotificationListResponse",
    "NotificationDispatchSummary",
    "UiOperationsDashboardResponse",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalize_django_path(path_value: str) -> str:
    route = path_value.strip().strip("/")
    if not route:
        return "/"
    route = re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", route)
    return f"/{route}"


def extract_implemented_paths(urls_text: str) -> set[str]:
    raw_routes = re.findall(r"path\(\s*'([^']+)'", urls_text)
    return {
        normalize_django_path(route)
        for route in raw_routes
        if route.startswith("api/v1/")
    }


def extract_openapi_paths(openapi_text: str) -> set[str]:
    lines = openapi_text.splitlines()
    in_paths = False
    result: set[str] = set()
    for line in lines:
        if not in_paths and line.strip() == "paths:":
            in_paths = True
            continue
        if not in_paths:
            continue
        if re.match(r"^\s*components:\s*$", line):
            break
        if re.match(r"^\S", line):
            break
        match = re.match(r"^\s{2}(/[^:]+):\s*$", line)
        if match:
            result.add(match.group(1))
    return result


def extract_schema_names(openapi_text: str) -> set[str]:
    lines = openapi_text.splitlines()
    for idx, line in enumerate(lines):
        if line.strip() != "schemas:":
            continue
        schema_indent = len(line) - len(line.lstrip(" "))
        result: set[str] = set()
        for candidate in lines[idx + 1 :]:
            if not candidate.strip():
                continue
            indent = len(candidate) - len(candidate.lstrip(" "))
            if indent <= schema_indent:
                break
            if indent == schema_indent + 2:
                match = re.match(r"^\s*([A-Za-z0-9_]+):\s*$", candidate)
                if match:
                    result.add(match.group(1))
        return result
    return set()


def main() -> int:
    implemented_paths = extract_implemented_paths(_read(URLS))
    openapi_text = _read(OPENAPI)
    openapi_paths = extract_openapi_paths(openapi_text)
    schema_names = extract_schema_names(openapi_text)

    errors: list[str] = []

    missing_critical_routes = sorted(CRITICAL_PATHS - implemented_paths)
    if missing_critical_routes:
        errors.append(
            "Critical route list is out of sync with implementation: "
            + ", ".join(missing_critical_routes)
        )

    missing_documented_paths = sorted((CRITICAL_PATHS & implemented_paths) - openapi_paths)
    if missing_documented_paths:
        errors.append(
            "OpenAPI paths missing for critical implemented routes: "
            + ", ".join(missing_documented_paths)
        )

    missing_schemas = sorted(REQUIRED_SCHEMAS - schema_names)
    if missing_schemas:
        errors.append(
            "OpenAPI components.schemas missing required contract types: "
            + ", ".join(missing_schemas)
        )

    if errors:
        print("OpenAPI contract drift gate failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("OpenAPI contract drift gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
