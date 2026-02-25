#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
ROADMAP = ROOT / "docs" / "roadmap.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_doc_links(text: str) -> set[str]:
    return set(re.findall(r"docs/([a-z0-9][a-z0-9_/-]*\.md)", text, flags=re.IGNORECASE))


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
                "Roadmap updates in docs-only changes must include at least one "
                "domain design doc in the same PR."
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", default="", help="Git base branch for PR comparison")
    args = parser.parse_args()

    errors = validate_links()
    changed_files = run_git_diff(args.base_ref or None)
    errors.extend(validate_batch_size(changed_files))

    if errors:
        print("Docs workflow gate failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Docs workflow gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
