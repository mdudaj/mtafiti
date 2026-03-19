#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(os.environ.get("SPEC_KIT_WORKFLOW_ROOT", Path(__file__).resolve().parents[2])).resolve()
TASK_RE = re.compile(r"^- \[(?P<done>[ xX])\]\s+(?P<body>.+)$")


@dataclass(frozen=True)
class FeatureBundle:
    feature_dir: Path
    spec_path: Path
    plan_path: Path
    tasks_path: Path


def resolve_feature_dir(feature: str) -> Path:
    path = Path(feature)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def load_bundle(feature: str) -> FeatureBundle:
    feature_dir = resolve_feature_dir(feature)
    return FeatureBundle(
        feature_dir=feature_dir,
        spec_path=feature_dir / "spec.md",
        plan_path=feature_dir / "plan.md",
        tasks_path=feature_dir / "tasks.md",
    )


def ensure_exists(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def relative_to_repo(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def normalize_heading(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def extract_title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Untitled feature"


def clean_feature_title(title: str) -> str:
    cleaned = re.sub(r"^Feature Specification:\s*", "", title).strip()
    return cleaned or title.strip()


def extract_section(text: str, *candidate_titles: str) -> str:
    wanted = {normalize_heading(item) for item in candidate_titles}
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if not match:
            continue
        heading_level = len(match.group(1))
        heading_title = normalize_heading(match.group(2))
        if heading_title not in wanted:
            continue
        collected: list[str] = []
        for body_line in lines[index + 1 :]:
            body_match = re.match(r"^(#{1,6})\s+(.*)$", body_line)
            if body_match and len(body_match.group(1)) <= heading_level:
                break
            collected.append(body_line)
        return "\n".join(collected).strip()
    return ""


def first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("**"):
            return stripped
    return ""


def parse_tasks(text: str) -> tuple[int, int, list[str]]:
    total = 0
    done = 0
    previews: list[str] = []
    for line in text.splitlines():
        match = TASK_RE.match(line)
        if not match:
            continue
        total += 1
        if match.group("done").lower() == "x":
            done += 1
        body = re.sub(r"\[[^\]]+\]\s*", "", match.group("body")).strip()
        previews.append(body)
    return total, done, previews


def bulletize(section_text: str, *, fallback: str) -> list[str]:
    items = [
        line.strip()[2:].strip()
        for line in section_text.splitlines()
        if line.strip().startswith("- ")
    ]
    if items:
        return items
    first_line = first_meaningful_line(section_text)
    if first_line:
        return [first_line]
    return [fallback]


def build_issue_body(feature: str) -> str:
    bundle = load_bundle(feature)
    ensure_exists(bundle.spec_path)
    ensure_exists(bundle.plan_path)
    ensure_exists(bundle.tasks_path)

    spec_text = read_text(bundle.spec_path)
    plan_text = read_text(bundle.plan_path)
    tasks_text = read_text(bundle.tasks_path)

    title = clean_feature_title(extract_title(spec_text))
    summary = extract_section(plan_text, "Summary")
    success = extract_section(spec_text, "Success Criteria", "Measurable Outcomes")
    delivery = extract_section(spec_text, "Delivery Mapping")
    repository_context = extract_section(spec_text, "Repository Context")
    total_tasks, done_tasks, previews = parse_tasks(tasks_text)

    deliverables = previews[:5] or ["Convert the approved plan into implementation-sized tasks."]
    acceptance_items = bulletize(
        success,
        fallback="Feature behavior matches the approved spec and plan.",
    )
    reference_items = [
        f"`{relative_to_repo(bundle.spec_path)}`",
        f"`{relative_to_repo(bundle.plan_path)}`",
        f"`{relative_to_repo(bundle.tasks_path)}`",
    ]
    if repository_context:
        reference_items.extend(bulletize(repository_context, fallback="Repository context captured in the spec."))

    objective = first_meaningful_line(summary) or f"Implement `{title}` from the approved spec-kit bundle."
    dependency_items = bulletize(delivery, fallback="Depends on: None")

    lines = [
        f"## Objective",
        "",
        objective,
        "",
        "## Spec Kit artifacts",
        "",
        f"- Spec: `{relative_to_repo(bundle.spec_path)}`",
        f"- Plan: `{relative_to_repo(bundle.plan_path)}`",
        f"- Tasks: `{relative_to_repo(bundle.tasks_path)}`",
        f"- Task progress at issue creation: {done_tasks}/{total_tasks} complete",
        "",
        "## Deliverables",
        "",
    ]
    lines.extend(f"- [ ] {item}" for item in deliverables)
    lines.extend(
        [
            "",
            "## Acceptance Criteria",
            "",
        ]
    )
    lines.extend(f"- [ ] {item}" for item in acceptance_items)
    lines.extend(
        [
            "",
            "## Dependencies",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in dependency_items)
    lines.extend(
        [
            "",
            "## References",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in reference_items)
    lines.extend(
        [
            "",
            "## Handoff contract (required updates during execution)",
            "",
            f"- Scope boundary: `{title}`",
            "- Changed files:",
            "- Risk notes:",
            "- Done/blocker state:",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def build_pr_body(feature: str, issue_number: str | None = None) -> str:
    bundle = load_bundle(feature)
    ensure_exists(bundle.spec_path)
    ensure_exists(bundle.plan_path)
    ensure_exists(bundle.tasks_path)

    spec_text = read_text(bundle.spec_path)
    plan_text = read_text(bundle.plan_path)
    tasks_text = read_text(bundle.tasks_path)

    title = clean_feature_title(extract_title(spec_text))
    summary = extract_section(plan_text, "Summary")
    validation = bulletize(
        extract_section(plan_text, "Planned Validation"),
        fallback="Run targeted validation and the repository merge gate.",
    )
    total_tasks, done_tasks, _ = parse_tasks(tasks_text)

    issue_line = f"- [ ] Linked issue: #{issue_number}" if issue_number else "- [ ] Linked issue:"
    summary_line = first_meaningful_line(summary) or f"This PR implements `{title}` from the approved spec-kit bundle."

    lines = [
        "## Summary",
        "",
        summary_line,
        "",
        "## Spec Kit artifacts",
        "",
        f"- Spec: `{relative_to_repo(bundle.spec_path)}`",
        f"- Plan: `{relative_to_repo(bundle.plan_path)}`",
        f"- Tasks: `{relative_to_repo(bundle.tasks_path)}`",
        f"- Task progress: {done_tasks}/{total_tasks} complete",
        issue_line,
        "",
        "## Issue contract",
        "",
        "- [ ] Linked execution issue includes Objective, Deliverables, Acceptance Criteria, Dependencies, and References.",
        "- [ ] Scope boundary for this PR is explicit and matches the issue deliverables.",
        "",
        "## Handoff contract",
        "",
        "- [ ] Changed files and risk notes are captured in the PR description.",
        "- [ ] Done/blocker state is explicit (no implicit follow-up gaps).",
        "- [ ] Spec bundle was updated first if scope changed during implementation.",
        "",
        "## Validation",
        "",
    ]
    lines.extend(f"- [ ] {item}" for item in validation)
    return "\n".join(lines).strip() + "\n"


def build_summary(feature: str) -> dict[str, object]:
    bundle = load_bundle(feature)
    ensure_exists(bundle.spec_path)
    summary: dict[str, object] = {
        "feature_dir": relative_to_repo(bundle.feature_dir),
        "spec": relative_to_repo(bundle.spec_path),
        "title": clean_feature_title(extract_title(read_text(bundle.spec_path))),
    }
    if bundle.plan_path.exists():
        summary["plan"] = relative_to_repo(bundle.plan_path)
    if bundle.tasks_path.exists():
        summary["tasks"] = relative_to_repo(bundle.tasks_path)
        total_tasks, done_tasks, previews = parse_tasks(read_text(bundle.tasks_path))
        summary["task_counts"] = {"total": total_tasks, "done": done_tasks}
        summary["task_preview"] = previews[:5]
    return summary


def validate(feature: str) -> list[str]:
    bundle = load_bundle(feature)
    errors: list[str] = []
    if not bundle.feature_dir.exists():
        errors.append(f"feature directory does not exist: {bundle.feature_dir}")
        return errors
    for path in (bundle.spec_path, bundle.plan_path, bundle.tasks_path):
        if not path.exists():
            errors.append(f"missing required file: {relative_to_repo(path)}")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bridge spec-kit feature bundles into GitHub issue and PR workflows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate that a feature directory has the required spec-kit files.")
    validate_parser.add_argument("feature")

    issue_parser = subparsers.add_parser("issue-body", help="Render a GitHub issue body from a feature bundle.")
    issue_parser.add_argument("feature")

    pr_parser = subparsers.add_parser("pr-body", help="Render a GitHub PR body from a feature bundle.")
    pr_parser.add_argument("feature")
    pr_parser.add_argument("--issue-number")

    summary_parser = subparsers.add_parser("summary", help="Emit a JSON summary for a feature bundle.")
    summary_parser.add_argument("feature")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "validate":
        errors = validate(args.feature)
        if errors:
            for item in errors:
                print(item)
            return 1
        print("Feature bundle is valid.")
        return 0

    if args.command == "issue-body":
        print(build_issue_body(args.feature), end="")
        return 0

    if args.command == "pr-body":
        print(build_pr_body(args.feature, issue_number=args.issue_number), end="")
        return 0

    if args.command == "summary":
        print(json.dumps(build_summary(args.feature), indent=2, sort_keys=True))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
