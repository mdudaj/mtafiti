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


def test_generate_content_creates_cookbook_sample_and_theme_skills(tmp_path):
    module = _load_module(SCRIPT_PATH, "configure_knowledge_sources")
    source_root = tmp_path / "knowledge-src"
    content_root = tmp_path / "content"

    crud_dir = source_root / "cookbook" / "crud101"
    crud_dir.mkdir(parents=True)
    (crud_dir / "README.md").write_text("# CRUD 101\n\nAdmin CRUD demo", encoding="utf-8")
    (crud_dir / "config").mkdir()
    (crud_dir / "config" / "urls.py").write_text("site = Site(title='Demo')", encoding="utf-8")
    (crud_dir / "atlas").mkdir()
    (crud_dir / "atlas" / "viewset.py").write_text("class AtlasApp(Application): ...", encoding="utf-8")

    material_dir = source_root / "django-material"
    material_dir.mkdir(parents=True)
    (material_dir / "README.md").write_text("# Django Material\n\nTheme docs", encoding="utf-8")
    (material_dir / "package.json").write_text(json.dumps({"version": "0.1.0"}), encoding="utf-8")
    colors_dir = material_dir / "material" / "assets"
    colors_dir.mkdir(parents=True)
    (colors_dir / "colors.css").write_text("--color-primary: #0277bd;", encoding="utf-8")

    generated = module.generate_content(source_root, content_root)
    entry_ids = {item["entry_id"] for item in generated}

    assert "knowledge-src/cookbook-crud101" in entry_ids
    assert "knowledge-src/django-material-theme-customization" in entry_ids
    assert (content_root / "knowledge-src" / "skills" / "cookbook-crud101" / "SKILL.md").exists()
    assert (content_root / "knowledge-src" / "skills" / "django-material-theme-customization" / "SKILL.md").exists()


def test_generate_content_includes_cookbook_directory_without_readme(tmp_path):
    module = _load_module(SCRIPT_PATH, "configure_knowledge_sources")
    source_root = tmp_path / "knowledge-src"
    content_root = tmp_path / "content"

    guardian_dir = source_root / "cookbook" / "guardian_perms"
    guardian_dir.mkdir(parents=True)
    (guardian_dir / "manage.py").write_text("print('manage')", encoding="utf-8")
    (guardian_dir / "config").mkdir()
    (guardian_dir / "config" / "urls.py").write_text("urlpatterns = []", encoding="utf-8")
    (guardian_dir / "bills").mkdir()
    (guardian_dir / "bills" / "viewsets.py").write_text("class BillsViewset: ...", encoding="utf-8")

    generated = module.generate_content(source_root, content_root)
    entry_ids = {item["entry_id"] for item in generated}

    assert "knowledge-src/cookbook-guardian-perms" in entry_ids
    assert (content_root / "knowledge-src" / "skills" / "cookbook-guardian-perms" / "SKILL.md").exists()
