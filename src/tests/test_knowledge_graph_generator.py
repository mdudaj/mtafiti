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


def test_bundle_contains_workspace_skill_markdown_files():
    module = _load_module(LIB_PATH, "knowledge_graph_lib")
    bundle = module.build_bundle(REPO_ROOT)

    skill_path = ".github/skills/compose_operations_dashboard_contract/SKILL.md"

    assert skill_path in bundle
    assert (
        'description: "Use when composing operations dashboard summary cards, workbench payloads, and allowed-action responses for UI surfaces."'
        in bundle[skill_path]
    )
    assert "# Compose Operations Dashboard Contract" in bundle[skill_path]
    assert (
        "canonical skill catalog in `.github/scripts/knowledge_graph_lib.py`"
        in bundle[skill_path]
    )
    assert "## Layer" in bundle[skill_path]
    assert "## Depends On" in bundle[skill_path]
    assert "## Confidence" in bundle[skill_path]


def test_generator_module_is_the_canonical_skill_source():
    module = _load_module(LIB_PATH, "knowledge_graph_lib")

    assert any(
        item["id"] == "define_django_json_api_endpoint"
        for item in module.BASE_SKILL_DEFINITIONS
    )
    assert "has_workflows" in module.CONDITIONAL_SKILL_DEFINITIONS
    assert "ui" in module.ONTOLOGY_LAYER_DEFINITIONS


def test_bundle_contains_layered_ontology_files_and_skill_dependencies():
    module = _load_module(LIB_PATH, "knowledge_graph_lib")
    bundle = module.build_bundle(REPO_ROOT)

    assert "ontology/ui.yaml" in bundle
    assert "ontology/navigation.yaml" in bundle
    assert "ontology/workflow.yaml" in bundle
    assert "ontology/state.yaml" in bundle
    assert "ontology/permission.yaml" in bundle
    assert "ontology/cross-layer.yaml" in bundle

    skill = next(
        item
        for item in bundle["skills/generated_skills.yaml"]["skills"]
        if item["id"] == "compose_operations_dashboard_contract"
    )
    assert skill["layer"] == "ui"
    assert skill["depends_on"] == ["define_django_json_api_endpoint"]
    assert skill["confidence"]["level"] == "high"

    edges = bundle["knowledge_graph/edges.yaml"]["edges"]
    assert any(
        edge["relationship"] == "depends_on"
        and edge["from"] == "skill:compose_operations_dashboard_contract"
        and edge["to"] == "skill:define_django_json_api_endpoint"
        for edge in edges
    )


def test_bundle_contains_behavioral_sources_patterns_and_skills():
    module = _load_module(LIB_PATH, "knowledge_graph_lib")
    bundle = module.build_bundle(REPO_ROOT)

    nodes = bundle["knowledge_graph/nodes.yaml"]["nodes"]
    node_ids = {node["id"] for node in nodes}
    assert "behavioralsource:viewflow-demo-site" in node_ids
    assert "pattern:viewflow_demo_site_intro_workflow_form" in node_ids
    assert "skill:observe_viewflow-demo-site_workflow_form_pattern" in node_ids

    ui_ontology = bundle["ontology/ui.yaml"]
    assert any(
        item["source"] == "viewflow-demo-site"
        for item in ui_ontology.get("observed_patterns", [])
    )

    skills = bundle["skills/generated_skills.yaml"]["skills"]
    behavioral_skill = next(
        item
        for item in skills
        if item["id"] == "observe_viewflow-demo-site_workflow_form_pattern"
    )
    assert behavioral_skill["confidence"]["level"] == "low"
    assert behavioral_skill["depends_on"] == ["extract_pattern_from_ui"]


def test_query_script_returns_behavioral_report():
    result = subprocess.run(
        [
            sys.executable,
            str(QUERY_PATH),
            "--report",
            "behavioral",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["report"] == "behavioral"
    assert payload["behavioral_source_count"] >= 1
    assert any(item["name"] == "viewflow-demo-site" for item in payload["sources"])


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
    assert (
        inventory["EnvironmentInventory"]["context_hub_registry"]["available"] is False
    )


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
    assert any(
        item["id"] == "skill:compose_operations_dashboard_contract" for item in payload
    )


def test_query_script_returns_layer_report():
    result = subprocess.run(
        [
            sys.executable,
            str(QUERY_PATH),
            "--report",
            "layers",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["report"] == "layers"
    assert "ontology/ui.yaml" in payload["ontology_files"]
    assert payload["layers"]["ui"]["skill_count"] >= 1


def test_query_script_returns_dependency_report():
    result = subprocess.run(
        [
            sys.executable,
            str(QUERY_PATH),
            "--report",
            "dependencies",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["report"] == "dependencies"
    assert "skill:compose_operations_dashboard_contract" in payload["skills"]
    assert (
        "skill:define_django_json_api_endpoint"
        in payload["skills"]["skill:compose_operations_dashboard_contract"]
    )
