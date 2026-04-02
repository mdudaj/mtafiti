#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
ROADMAP = ROOT / "docs" / "roadmap.md"
ALLOWED_BRANCH_TYPES = {
    "feat",
    "fix",
    "docs",
    "refactor",
    "test",
    "chore",
    "build",
    "ci",
    "perf",
    "revert",
}
BRANCH_PATTERN = re.compile(
    r"^(?:" + "|".join(sorted(ALLOWED_BRANCH_TYPES)) + r")\/[a-z0-9]+(?:-[a-z0-9]+)*$"
)
COMMIT_SUBJECT_PATTERN = re.compile(
    r"^(?:"
    + "|".join(sorted(ALLOWED_BRANCH_TYPES))
    + r")(?:\([A-Za-z0-9][A-Za-z0-9._\/-]*\))?!?: [A-Za-z0-9].+$"
)
DISALLOWED_PR_TITLE_PREFIXES = ("wip", "do not merge", "dnm")
REQUIRED_PR_SECTIONS = [
    "summary",
    "review unit",
    "spec kit artifacts",
    "issue contract",
    "commit contract",
    "handoff contract",
    "validation",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_doc_links(text: str) -> set[str]:
    return set(
        re.findall(
            r"docs/([a-z0-9][a-z0-9_/-]*\.md)",
            text,
            flags=re.IGNORECASE,
        )
    )


def run_git_diff(base_ref: str | None) -> list[str]:
    if base_ref:
        diff_cmd = ["git", "diff", "--name-only", f"origin/{base_ref}...HEAD"]
    else:
        diff_cmd = ["git", "diff", "--name-only", "HEAD~1..HEAD"]
    try:
        out = subprocess.run(
            diff_cmd,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def run_git_log_subjects(base_ref: str | None) -> list[str]:
    if base_ref:
        log_cmd = ["git", "log", "--format=%s", f"origin/{base_ref}..HEAD"]
    else:
        log_cmd = ["git", "log", "--format=%s", "HEAD~1..HEAD"]
    try:
        out = subprocess.run(
            log_cmd,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def current_branch_name() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def read_event_payload(event_path: str | None) -> dict:
    if not event_path:
        return {}
    event_file = Path(event_path)
    if not event_file.exists():
        return {}
    return json.loads(event_file.read_text(encoding="utf-8"))


def extract_pr_section_titles(body: str) -> set[str]:
    return {
        match.group(1).strip().lower()
        for match in re.finditer(
            r"^#{1,6}\s+(.+?)\s*$",
            body or "",
            flags=re.MULTILINE,
        )
    }


def validate_branch_policy(branch_name: str, event_name: str) -> list[str]:
    if not branch_name or branch_name in {"main", "master", "HEAD"}:
        return []
    if event_name == "pull_request_target":
        return []
    if BRANCH_PATTERN.match(branch_name):
        return []
    return [
        "Branch names must use a Git-safe Conventional Commit slug such as "
        "feat/spec-kit-workflow or fix/tenant-routing."
    ]


def validate_commit_subjects(
    commit_subjects: list[str], branch_name: str, event_name: str = ""
) -> list[str]:
    if not commit_subjects or branch_name in {"", "main", "master", "HEAD"}:
        return []

    invalid_subjects = [
        subject
        for subject in commit_subjects
        if not (event_name == "pull_request" and subject.startswith("Merge "))
        if not COMMIT_SUBJECT_PATTERN.match(subject)
    ]
    if not invalid_subjects:
        return []

    return [
        "Commit subjects must use Conventional Commits on issue branches. "
        "Invalid subjects: " + "; ".join(invalid_subjects[:5])
    ]


def validate_pull_request_metadata(event_name: str, payload: dict) -> list[str]:
    if event_name != "pull_request":
        return []

    errors: list[str] = []
    pull_request = payload.get("pull_request") or {}
    title = (pull_request.get("title") or "").strip()
    body = pull_request.get("body") or ""

    if not title:
        errors.append("Pull requests must have a non-empty title.")
    elif title.lower().startswith(DISALLOWED_PR_TITLE_PREFIXES):
        errors.append(
            "Pull request titles must not use WIP/DNM prefixes; "
            "use draft PR state instead."
        )

    headings = extract_pr_section_titles(body)
    missing_sections = [
        section for section in REQUIRED_PR_SECTIONS if section not in headings
    ]
    if missing_sections:
        errors.append(
            "Pull request body must include the required template sections: "
            + ", ".join(missing_sections)
        )

    return errors


def validate_links() -> list[str]:
    errors: list[str] = []
    readme_links = extract_doc_links(read_text(README))
    roadmap_links = extract_doc_links(read_text(ROADMAP))

    missing = sorted(
        doc
        for doc in (readme_links | roadmap_links)
        if not (ROOT / "docs" / doc).exists()
    )
    if missing:
        errors.append(
            "Missing linked docs files: "
            + ", ".join(f"docs/{name}" for name in missing)
        )

    missing_from_readme = sorted(roadmap_links - readme_links)
    if missing_from_readme:
        errors.append(
            "Roadmap docs missing from README Design docs list: "
            + ", ".join(f"docs/{name}" for name in missing_from_readme)
        )
    return errors


def validate_batch_size(changed_files: list[str]) -> list[str]:
    errors: list[str] = []
    doc_md = sorted(
        {f for f in changed_files if f.startswith("docs/") and f.endswith(".md")}
    )
    if not doc_md:
        return errors

    allowed_non_doc = {"README.md", ".github/pull_request_template.md"}
    non_doc_changes = [
        f
        for f in changed_files
        if not (f in allowed_non_doc or (f.startswith("docs/") and f.endswith(".md")))
    ]
    docs_only_change = len(non_doc_changes) == 0

    if docs_only_change and len(doc_md) < 3:
        errors.append(
            "Docs-only changes must be submitted in larger chunks: "
            "change at least 3 markdown files under docs/."
        )

    if docs_only_change and "docs/roadmap.md" in doc_md:
        domain_docs = [f for f in doc_md if f != "docs/roadmap.md"]
        if not domain_docs:
            errors.append(
                "Roadmap updates in docs-only changes must include at least "
                "one "
                "domain design doc in the same PR."
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-ref",
        default="",
        help="Git base branch for PR comparison",
    )
    parser.add_argument(
        "--event-name",
        default=os.environ.get("GITHUB_EVENT_NAME", ""),
    )
    parser.add_argument(
        "--event-path",
        default=os.environ.get("GITHUB_EVENT_PATH", ""),
    )
    parser.add_argument(
        "--branch-name",
        default=os.environ.get("GITHUB_HEAD_REF")
        or os.environ.get("GITHUB_REF_NAME")
        or "",
    )
    args = parser.parse_args()

    errors = validate_links()
    changed_files = run_git_diff(args.base_ref or None)
    errors.extend(validate_batch_size(changed_files))
    branch_name = args.branch_name or current_branch_name()
    errors.extend(validate_branch_policy(branch_name, args.event_name))
    errors.extend(
        validate_commit_subjects(
            run_git_log_subjects(args.base_ref or None),
            branch_name,
            args.event_name,
        )
    )
    errors.extend(
        validate_pull_request_metadata(
            args.event_name, read_event_payload(args.event_path)
        )
    )

    if errors:
        print("Docs workflow gate failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Docs workflow gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
