#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any
from urllib import error, request

DEFAULT_OWNER = "mdudaj"
DEFAULT_REPO = "mtafiti"
DEFAULT_BRANCH = "main"
DEFAULT_REQUIRED_CONTEXTS = [
    "docs-gate",
    "src-tests (shard 0/4)",
    "src-tests (shard 1/4)",
    "src-tests (shard 2/4)",
    "src-tests (shard 3/4)",
    "performance-baseline-tests",
]


def build_repository_settings_payload() -> dict[str, Any]:
    return {
        "allow_squash_merge": True,
        "allow_merge_commit": False,
        "allow_rebase_merge": False,
        "allow_auto_merge": True,
        "delete_branch_on_merge": True,
    }


def build_branch_protection_payload(contexts: list[str]) -> dict[str, Any]:
    return {
        "required_status_checks": {
            "strict": True,
            "contexts": contexts,
        },
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": False,
            "require_code_owner_reviews": False,
            "required_approving_review_count": 0,
        },
        "restrictions": None,
        "required_linear_history": False,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": False,
        "required_conversation_resolution": False,
        "lock_branch": False,
        "allow_fork_syncing": False,
    }


def resolve_token() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token

    gh = subprocess.run(
        ["gh", "auth", "token"],
        check=False,
        capture_output=True,
        text=True,
    )
    if gh.returncode == 0 and gh.stdout.strip():
        return gh.stdout.strip()

    raise RuntimeError(
        "GitHub authentication not available. Set GH_TOKEN or GITHUB_TOKEN, "
        "or run `gh auth login` before applying branch protection."
    )


def update_branch_protection(
    owner: str,
    repo: str,
    branch: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    token = resolve_token()
    endpoint = (
        "https://api.github.com/repos/" f"{owner}/{repo}/branches/{branch}/protection"
    )
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        method="PUT",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            "GitHub API rejected branch protection update: " f"{exc.code} {detail}"
        ) from exc


def update_repository_settings(
    owner: str,
    repo: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    token = resolve_token()
    endpoint = f"https://api.github.com/repos/{owner}/{repo}"
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        method="PATCH",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            "GitHub API rejected repository settings update: " f"{exc.code} {detail}"
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument(
        "--context",
        action="append",
        dest="contexts",
        help="Override required status checks by repeating --context",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the payload instead of calling the GitHub API",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contexts = args.contexts or DEFAULT_REQUIRED_CONTEXTS
    repo_payload = build_repository_settings_payload()
    payload = build_branch_protection_payload(contexts)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "branch_protection": payload,
                    "repository_settings": repo_payload,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    repo_result = update_repository_settings(
        args.owner,
        args.repo,
        repo_payload,
    )

    result = update_branch_protection(
        args.owner,
        args.repo,
        args.branch,
        payload,
    )
    enabled_contexts = result.get("required_status_checks", {}).get(
        "contexts",
        [],
    )
    print(
        json.dumps(
            {
                "owner": args.owner,
                "repo": args.repo,
                "branch": args.branch,
                "required_status_checks": enabled_contexts,
                "enforce_admins": result.get("enforce_admins", {}).get("enabled"),
                "required_approving_review_count": result.get(
                    "required_pull_request_reviews", {}
                ).get("required_approving_review_count"),
                "dismiss_stale_reviews": result.get(
                    "required_pull_request_reviews", {}
                ).get("dismiss_stale_reviews"),
                "required_conversation_resolution": result.get(
                    "required_conversation_resolution", {}
                ).get("enabled"),
                "allow_squash_merge": repo_result.get("allow_squash_merge"),
                "allow_merge_commit": repo_result.get("allow_merge_commit"),
                "allow_rebase_merge": repo_result.get("allow_rebase_merge"),
                "allow_auto_merge": repo_result.get("allow_auto_merge"),
                "delete_branch_on_merge": repo_result.get("delete_branch_on_merge"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
