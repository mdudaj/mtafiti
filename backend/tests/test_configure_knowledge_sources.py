import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "configure_knowledge_sources.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_detect_version_prefers_package_json(tmp_path):
    module = _load_module(SCRIPT_PATH, "configure_knowledge_sources")
    repo = tmp_path / "demo"
    repo.mkdir()
    (repo / "package.json").write_text(json.dumps({"version": "1.2.3"}), encoding="utf-8")
    assert module.detect_version(repo, "# demo") == "1.2.3"


def test_generate_content_creates_doc_and_skill_entries(tmp_path):
    module = _load_module(SCRIPT_PATH, "configure_knowledge_sources")
    source_root = tmp_path / "knowledge-src"
    content_root = tmp_path / "content"
    doc_repo = source_root / "viewflow"
    skill_repo = source_root / "cookbook"
    doc_repo.mkdir(parents=True)
    skill_repo.mkdir(parents=True)
    (doc_repo / "README.md").write_text("# Viewflow\n\nWorkflow docs", encoding="utf-8")
    (doc_repo / "package.json").write_text(json.dumps({"version": "2.2.15"}), encoding="utf-8")
    (skill_repo / "README.md").write_text("# Cookbook\n\nExamples", encoding="utf-8")

    generated = module.generate_content(source_root, content_root)

    assert {item["entry_type"] for item in generated} == {"doc", "skill"}
    assert (content_root / "knowledge-src" / "docs" / "viewflow" / "DOC.md").exists()
    assert (content_root / "knowledge-src" / "skills" / "cookbook" / "SKILL.md").exists()
