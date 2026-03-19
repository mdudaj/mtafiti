import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "spec_kit_workflow.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_bundle(root: Path) -> Path:
    feature_dir = root / "specs" / "012-spec-kit-workflow"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(
        "# Feature Specification: Spec Kit workflow\n\n"
        "## Repository Context\n\n"
        "- `docs/spec-kit-workflow.md`\n"
        "- `knowledge_graph/nodes.yaml`\n\n"
        "## Success Criteria\n\n"
        "- Spec artifacts generate GitHub delivery bodies consistently.\n\n"
        "## Delivery Mapping\n\n"
        "- Primary issue title: Integrate spec-kit workflow\n"
        "- Planned branch label: `feat/spec-kit-workflow`\n",
        encoding="utf-8",
    )
    (feature_dir / "plan.md").write_text(
        "# Implementation Plan: Spec Kit workflow\n\n"
        "## Summary\n\n"
        "Make spec-kit artifacts the source of truth for issues and PRs.\n\n"
        "## Planned Validation\n\n"
        "- python .github/scripts/spec_kit_workflow.py validate specs/012-spec-kit-workflow\n"
        "- .github/scripts/local_fast_feedback.sh --full-gate\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "# Tasks: Spec Kit workflow\n\n"
        "- [x] T001 Confirm `spec.md` reflects the latest clarified scope\n"
        "- [ ] T002 Generate issue body from the feature bundle\n"
        "- [ ] T003 Generate PR body from the feature bundle\n",
        encoding="utf-8",
    )
    return feature_dir


def test_build_issue_body_includes_spec_artifacts(tmp_path):
    module = _load_module(SCRIPT_PATH, "spec_kit_workflow")
    feature_dir = _write_bundle(tmp_path)
    module.REPO_ROOT = tmp_path

    body = module.build_issue_body(str(feature_dir))

    assert "## Spec Kit artifacts" in body
    assert "`specs/012-spec-kit-workflow/spec.md`" in body
    assert "Task progress at issue creation: 1/3 complete" in body
    assert "Make spec-kit artifacts the source of truth for issues and PRs." in body


def test_build_pr_body_uses_validation_section(tmp_path):
    module = _load_module(SCRIPT_PATH, "spec_kit_workflow_pr")
    feature_dir = _write_bundle(tmp_path)
    module.REPO_ROOT = tmp_path

    body = module.build_pr_body(str(feature_dir), issue_number="123")

    assert "Linked issue: #123" in body
    assert "python .github/scripts/spec_kit_workflow.py validate specs/012-spec-kit-workflow" in body
    assert "Task progress: 1/3 complete" in body


def test_summary_command_emits_json(tmp_path):
    feature_dir = _write_bundle(tmp_path)
    env = dict(os.environ, SPEC_KIT_WORKFLOW_ROOT=str(tmp_path))
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "summary", str(feature_dir)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["feature_dir"] == "specs/012-spec-kit-workflow"
    assert payload["task_counts"] == {"total": 3, "done": 1}
