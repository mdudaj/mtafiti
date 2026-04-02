import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "check_docs_workflow.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "check_docs_workflow",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["check_docs_workflow"] = module
    spec.loader.exec_module(module)
    return module


def test_branch_policy_accepts_git_safe_conventional_slug():
    module = _load_module()
    assert (
        module.validate_branch_policy(
            "feat/spec-kit-workflow",
            "pull_request",
        )
        == []
    )


def test_branch_policy_rejects_issue_number_only_branch():
    module = _load_module()
    errors = module.validate_branch_policy("123-work-item", "pull_request")
    assert errors
    assert "Git-safe Conventional Commit slug" in errors[0]


def test_commit_subjects_require_conventional_commits():
    module = _load_module()
    errors = module.validate_commit_subjects(
        ["feat(shell): add navigation resolver", "fix: repair issue"],
        "feat/spec-kit-workflow",
    )
    assert errors == []

    errors = module.validate_commit_subjects(
        ["address feedback", "feat(shell): add navigation resolver"],
        "feat/spec-kit-workflow",
    )
    assert errors
    assert "address feedback" in errors[0]


def test_pull_request_metadata_requires_template_sections_and_non_wip_title(
    tmp_path,
):
    module = _load_module()
    payload = {
        "pull_request": {
            "title": "WIP: shell resolver",
            "body": "## Summary\n\nBody only has one section.\n",
        }
    }

    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(payload), encoding="utf-8")

    errors = module.validate_pull_request_metadata(
        "pull_request", module.read_event_payload(str(event_path))
    )

    assert len(errors) == 2
    assert "WIP/DNM prefixes" in errors[0]
    assert "review unit" in errors[1]


def test_pull_request_metadata_accepts_template_headings():
    module = _load_module()
    body = """# Pull Request

## Summary

Summary text.

## Review unit

- [x] Scope matches one issue.

## Spec Kit artifacts

- [x] Spec path recorded.

## Issue contract

- [x] Linked issue recorded.

## Commit contract

- [x] Conventional Commits used.

## Handoff contract

- [x] Risks documented.

## Validation

- [x] Tests listed.
"""
    payload = {
        "pull_request": {
            "title": "feat(shell): add resolver",
            "body": body,
        }
    }

    assert module.validate_pull_request_metadata("pull_request", payload) == []
