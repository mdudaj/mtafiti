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

    viewflow_dir = source_root / "viewflow"
    viewflow_dir.mkdir(parents=True)
    (viewflow_dir / "README.md").write_text("# Viewflow\n\nWorkflow docs", encoding="utf-8")
    (viewflow_dir / "package.json").write_text(json.dumps({"version": "2.2.15"}), encoding="utf-8")
    (viewflow_dir / "viewflow" / "urls").mkdir(parents=True)
    (viewflow_dir / "viewflow" / "urls" / "sites.py").write_text("class Site: ...\nclass Application: ...", encoding="utf-8")
    (viewflow_dir / "viewflow" / "urls" / "model.py").write_text("class ModelViewset: ...", encoding="utf-8")
    (viewflow_dir / "viewflow" / "workflow" / "flow").mkdir(parents=True)
    (viewflow_dir / "viewflow" / "workflow" / "base.py").write_text("class Node: ...", encoding="utf-8")
    (viewflow_dir / "viewflow" / "workflow" / "activation.py").write_text("class Activation: ...", encoding="utf-8")
    (viewflow_dir / "viewflow" / "workflow" / "flow" / "nodes.py").write_text("class Start: ...\nclass View: ...\nclass Split: ...\nclass Join: ...", encoding="utf-8")
    (viewflow_dir / "viewflow" / "forms").mkdir(parents=True)
    (viewflow_dir / "viewflow" / "forms" / "renderers.py").write_text("class WidgetRenderer: ...", encoding="utf-8")
    (viewflow_dir / "viewflow" / "fsm").mkdir(parents=True)
    (viewflow_dir / "viewflow" / "fsm" / "base.py").write_text("class Transition: ...", encoding="utf-8")
    (viewflow_dir / "viewflow" / "fsm" / "viewset.py").write_text("class FlowViewsMixin: ...", encoding="utf-8")
    (viewflow_dir / "viewflow" / "contrib").mkdir(parents=True)
    (viewflow_dir / "viewflow" / "contrib" / "auth.py").write_text("class AuthenticationForm: ...\nclass AuthViewset: ...", encoding="utf-8")
    (viewflow_dir / "tests" / "workflow").mkdir(parents=True)
    (viewflow_dir / "tests" / "workflow" / "test_flow_viewset__workflow.py").write_text("class TestWorkflowViewestFlow: ...", encoding="utf-8")
    (viewflow_dir / "tests" / "workflow" / "test_managers_perms.py").write_text("class StaffOnlyFlow: ...", encoding="utf-8")
    (viewflow_dir / "tests" / "fsm").mkdir(parents=True)
    (viewflow_dir / "tests" / "fsm" / "test_fsm__permissions.py").write_text("class _Publication: ...", encoding="utf-8")

    crud_dir = source_root / "cookbook" / "crud101"
    crud_dir.mkdir(parents=True)
    (crud_dir / "README.md").write_text("# CRUD 101\n\nAdmin CRUD demo", encoding="utf-8")
    (crud_dir / "config").mkdir()
    (crud_dir / "config" / "urls.py").write_text("site = Site(title='Demo')", encoding="utf-8")
    (crud_dir / "atlas").mkdir()
    (crud_dir / "atlas" / "viewset.py").write_text("class AtlasApp(Application): ...", encoding="utf-8")
    (crud_dir / "staff").mkdir()
    (crud_dir / "staff" / "viewset.py").write_text("class EmployeeViewset(ModelViewset): ...", encoding="utf-8")

    workflow_dir = source_root / "cookbook" / "workflow101" / "shipment"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "flows.py").write_text("class ShipmentFlow(flow.Flow): ...", encoding="utf-8")
    (workflow_dir / "views.py").write_text("class StartView: ...\nclass ShipmentView: ...", encoding="utf-8")

    fsm_dir = source_root / "cookbook" / "fsm101" / "review"
    fsm_dir.mkdir(parents=True)
    (fsm_dir / "viewset.py").write_text("class ReviewViewset(FlowViewsMixin): ...", encoding="utf-8")

    forms_dir = source_root / "cookbook" / "forms101" / "forms"
    forms_dir.mkdir(parents=True)
    (forms_dir / "bank_form.py").write_text("class BankForm:\n    layout = Layout()", encoding="utf-8")

    patterns_dir = source_root / "cookbook" / "patterns" / "config"
    patterns_dir.mkdir(parents=True)
    (patterns_dir / "urls.py").write_text("site = Site(title='Workflow patterns')", encoding="utf-8")

    dashboard_dir = source_root / "cookbook" / "dashboard"
    (dashboard_dir / "config").mkdir(parents=True)
    (dashboard_dir / "config" / "urls.py").write_text("site = Site(title='Dashboard')", encoding="utf-8")
    (dashboard_dir / "oilngas").mkdir(parents=True)
    (dashboard_dir / "oilngas" / "dashboard.py").write_text("dashboard = Dashboard(app_name='oilngas')", encoding="utf-8")

    material_dir = source_root / "django-material"
    material_dir.mkdir(parents=True)
    (material_dir / "README.md").write_text("# Django Material\n\nTheme docs", encoding="utf-8")
    (material_dir / "package.json").write_text(json.dumps({"version": "0.1.0"}), encoding="utf-8")
    colors_dir = material_dir / "material" / "assets"
    colors_dir.mkdir(parents=True)
    (colors_dir / "colors.css").write_text("--color-primary: #0277bd;", encoding="utf-8")
    (material_dir / "tests").mkdir(parents=True)
    (material_dir / "tests" / "test_views_base.py").write_text("class FormLayoutMixinTests: ...", encoding="utf-8")
    (material_dir / "tests" / "test_views_create.py").write_text("class CreateModelViewTests: ...", encoding="utf-8")
    (material_dir / "demo" / "templates" / "demo").mkdir(parents=True)
    (material_dir / "demo" / "templates" / "demo" / "showcases.html").write_text("{% extends 'material/base_page.html' %}", encoding="utf-8")
    (material_dir / "demo" / "templates" / "demo" / "widgets.html").write_text("{% extends 'material/base_page.html' %}", encoding="utf-8")
    (material_dir / "material" / "templates" / "cotton").mkdir(parents=True)
    (material_dir / "material" / "templates" / "cotton" / "CLAUDE.md").write_text("# Cotton component guide", encoding="utf-8")
    (material_dir / "material" / "templates" / "cotton" / "forms" / "text").mkdir(parents=True)
    (material_dir / "material" / "templates" / "cotton" / "forms" / "text" / "outlined.html").write_text("<input placeholder=' ' data-input />", encoding="utf-8")
    (material_dir / "material" / "templates" / "cotton" / "forms" / "select").mkdir(parents=True)
    (material_dir / "material" / "templates" / "cotton" / "forms" / "select" / "outlined.html").write_text("<input up-select-trigger />", encoding="utf-8")
    (material_dir / "material" / "templates" / "cotton" / "button").mkdir(parents=True)
    (material_dir / "material" / "templates" / "cotton" / "button" / "filled.html").write_text("<button up-ripple>{{ slot }}</button>", encoding="utf-8")
    (material_dir / "material" / "templates" / "cotton" / "button" / "fab.html").write_text("<button class='rounded-full'>+</button>", encoding="utf-8")
    (material_dir / "material" / "templates" / "cotton" / "card").mkdir(parents=True)
    (material_dir / "material" / "templates" / "cotton" / "card" / "elevated.html").write_text("<div class='bg-surface'>{{ slot }}</div>", encoding="utf-8")

    generated = module.generate_content(source_root, content_root)
    entry_ids = {item["entry_id"] for item in generated}

    assert "knowledge-src/cookbook-crud101" in entry_ids
    assert "knowledge-src/django-material-theme-customization" in entry_ids
    assert "knowledge-src/crud-admin-shell-layout" in entry_ids
    assert "knowledge-src/viewflow-workflow-orchestration" in entry_ids
    assert "knowledge-src/viewflow-fsm-state-transitions" in entry_ids
    assert "knowledge-src/django-material-frontend-composition" in entry_ids
    assert "knowledge-src/viewflow-forms-layout-composition" in entry_ids
    assert "knowledge-src/viewflow-crud-scaffolding" in entry_ids
    assert "knowledge-src/viewflow-auth-account-scaffolding" in entry_ids
    assert "knowledge-src/viewflow-dashboard-composition" in entry_ids
    assert "knowledge-src/knowledge-source-maintenance" in entry_ids
    assert (content_root / "knowledge-src" / "skills" / "cookbook-crud101" / "SKILL.md").exists()
    assert (content_root / "knowledge-src" / "skills" / "django-material-theme-customization" / "SKILL.md").exists()
    admin_shell = content_root / "knowledge-src" / "skills" / "crud-admin-shell-layout" / "SKILL.md"
    assert admin_shell.exists()
    assert "Sidebar navigation" in admin_shell.read_text(encoding="utf-8")
    assert "hover/focus tooltip" in admin_shell.read_text(encoding="utf-8")
    assert "Implementation lessons" in admin_shell.read_text(encoding="utf-8")
    assert "Google Material icons" in admin_shell.read_text(encoding="utf-8")
    assert "two topbar variants" in admin_shell.read_text(encoding="utf-8")
    assert "preserving a visible gap between the sidebar and the content column" in admin_shell.read_text(encoding="utf-8")
    assert "Choose a Material icon that matches the action context" in admin_shell.read_text(encoding="utf-8")

    workflow_skill = content_root / "knowledge-src" / "skills" / "viewflow-workflow-orchestration" / "SKILL.md"
    assert workflow_skill.exists()
    assert "StartHandle" in workflow_skill.read_text(encoding="utf-8")
    assert "Cookbook orchestration example" in workflow_skill.read_text(encoding="utf-8")

    frontend_skill = content_root / "knowledge-src" / "skills" / "django-material-frontend-composition" / "SKILL.md"
    assert frontend_skill.exists()
    assert "cotton components" in frontend_skill.read_text(encoding="utf-8")
    assert "base_page.html" in frontend_skill.read_text(encoding="utf-8")
    assert "Rapid agentic UI metadata" in frontend_skill.read_text(encoding="utf-8")
    assert "Outlined text field component" in frontend_skill.read_text(encoding="utf-8")
    assert "Workflow task views using built-in workflow templates" in frontend_skill.read_text(encoding="utf-8")

    forms_skill = content_root / "knowledge-src" / "skills" / "viewflow-forms-layout-composition" / "SKILL.md"
    assert forms_skill.exists()
    assert "FieldSet" in forms_skill.read_text(encoding="utf-8")

    auth_skill = content_root / "knowledge-src" / "skills" / "viewflow-auth-account-scaffolding" / "SKILL.md"
    assert auth_skill.exists()
    assert "AuthViewset" in auth_skill.read_text(encoding="utf-8")

    maintenance_skill = content_root / "knowledge-src" / "skills" / "knowledge-source-maintenance" / "SKILL.md"
    assert maintenance_skill.exists()
    assert "generate_domain_skill_entries" in maintenance_skill.read_text(encoding="utf-8")
    assert "chub update" in maintenance_skill.read_text(encoding="utf-8")


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
