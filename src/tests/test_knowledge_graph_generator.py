import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "generate_knowledge_graph.py"
LIB_PATH = REPO_ROOT / ".github" / "scripts" / "knowledge_graph_lib.py"
QUERY_PATH = REPO_ROOT / ".github" / "scripts" / "query_knowledge_graph.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(path.parent))
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def test_generate_knowledge_graph_check_passes_for_current_repo():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_bundle_contains_expected_framework_and_skill_nodes():
    module = _load_module(LIB_PATH, "knowledge_graph_lib")
    bundle = module.build_bundle(REPO_ROOT)
    nodes = bundle["knowledge_graph/nodes.yaml"]["nodes"]
    skills = bundle["skills/generated_skills.yaml"]["skills"]

    node_ids = {node["id"] for node in nodes}
    skill_ids = {skill["id"] for skill in skills}

    assert "framework:django" in node_ids
    assert "framework:viewflow" in node_ids
    assert "framework:django_material" in node_ids
    assert "framework:celery" in node_ids
    assert "framework:django-tenants" in node_ids
    assert "skill:compose_operations_dashboard_contract" in node_ids
    assert "compose_operations_dashboard_contract" in skill_ids

    django_node = next(node for node in nodes if node["id"] == "framework:django")
    assert "local_source_workflow" in django_node["context_hub"]


def test_knowledge_graph_library_prefers_src_app_root():
    module = _load_module(LIB_PATH, "knowledge_graph_lib")
    assert module.resolve_app_root(REPO_ROOT) == REPO_ROOT / "src"


def test_programming_language_detection_uses_tracked_files():
    module = _load_module(LIB_PATH, "knowledge_graph_lib")
    languages = {
        item["name"]: item["file_count"]
        for item in module.detect_programming_languages(REPO_ROOT)
    }
    assert languages["Python"] < 1000
    assert languages["Markdown"] < 200


def test_context_hub_entries_are_environment_independent(monkeypatch):
    module = _load_module(LIB_PATH, "knowledge_graph_lib")
    monkeypatch.setattr(module.shutil, "which", lambda _: "/tmp/fake-chub")
    module._CONTEXT_HUB_CACHE.clear()

    entry = module.build_context_hub_entry("django")
    inventory = module.build_environment_inventory(
        REPO_ROOT,
        module.collect_python_modules(REPO_ROOT / "src"),
        module.extract_urlpatterns(REPO_ROOT / "src" / "config" / "urls.py"),
        module.extract_settings(REPO_ROOT / "src" / "config" / "settings.py"),
    )

    assert entry["available"] is False
    assert entry["status"] == "external_optional_cli"
    assert "search_results" not in entry
    assert "candidate_registry_ids" not in entry
    assert inventory["EnvironmentInventory"]["context_hub_registry"]["available"] is False


def test_query_script_returns_dashboard_skills():
    result = subprocess.run(
        [
            sys.executable,
            str(QUERY_PATH),
            "--type",
            "Skill",
            "--text",
            "dashboard",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert any(item["id"] == "skill:compose_operations_dashboard_contract" for item in payload)
