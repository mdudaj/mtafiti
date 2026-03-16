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
    (viewflow_dir / "viewflow" / "workflow" / "flow" / "nodes.py").write_text(
        "class Start: ...\n"
        "class View: ...\n"
        "class Split: ...\n"
        "class SplitFirst: ...\n"
        "class Join: ...\n"
        "class Subprocess: ...\n"
        "class NSubprocess: ...\n"
        "class Switch: ...\n",
        encoding="utf-8",
    )
    (viewflow_dir / "viewflow" / "forms").mkdir(parents=True)
    (viewflow_dir / "viewflow" / "forms" / "renderers.py").write_text("class WidgetRenderer: ...", encoding="utf-8")
    (viewflow_dir / "viewflow" / "utils.py").write_text("def has_object_perm(user, short_perm_name, model, obj=None): ...", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow").mkdir(parents=True)
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "base.html").write_text("{% block body %}{% endblock %}", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "base_page.html").write_text("{% block page-menu %}{% endblock %}{% block page-toolbar %}{% endblock %}", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "views").mkdir(parents=True)
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "views" / "list.html").write_text("{% extends 'viewflow/base_page.html' %}{% block page-toolbar-actions %}<vf-page-search></vf-page-search>{% endblock %}", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "views" / "detail.html").write_text("{% include 'viewflow/includes/object_detail_card.html' %}", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "views" / "form.html").write_text("{% block extrahead %}{{ form.media }}{% endblock %}{% render form form.layout %}", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "views" / "confirm_delete.html").write_text("{% trans 'Delete' %}", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "views" / "transition.html").write_text("{% extends 'viewflow/views/form.html' %}{% block breadcrumbs_items %}Transition{% endblock %}", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "includes").mkdir(parents=True)
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "includes" / "object_detail_card.html").write_text("<section class='vf-card__header'></section><section class='mdc-card__actions vf-card__actions'></section>", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "includes" / "view_action_menu.html").write_text("{% with actions=view.get_page_actions %}<vf-card-menu></vf-card-menu>{% endwith %}", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "includes" / "snackbar.html").write_text("<vf-snackbar>{{ message }}</vf-snackbar>", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "includes" / "list_bulk_actions.html").write_text("Select all<button>GO</button>", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "includes" / "app_menu.html").write_text("<vf-page-menu-navigation>{% trans 'Back' %}</vf-page-menu-navigation>", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "includes" / "site_menu.html").write_text("<vf-page-menu-navigation>{% trans 'Applications' %}</vf-page-menu-navigation>", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "includes" / "list_filter.html").write_text("<vf-list-filter><button>Filter</button></vf-list-filter>", encoding="utf-8")
    (viewflow_dir / "viewflow" / "templates" / "viewflow" / "includes" / "list_pagination.html").write_text("1-10 of 10", encoding="utf-8")
    (viewflow_dir / "viewflow" / "views").mkdir(parents=True)
    (viewflow_dir / "viewflow" / "views" / "create.py").write_text("class CreateModelView:\n    def get_template_names(self):\n        return ['app/model_form.html', 'viewflow/views/form.html']\n", encoding="utf-8")
    (viewflow_dir / "viewflow" / "views" / "detail.py").write_text("class DetailModelView:\n    template_name = 'viewflow/views/detail.html'\n", encoding="utf-8")
    (viewflow_dir / "viewflow" / "views" / "delete.py").write_text("class DeleteModelView:\n    template_name = 'viewflow/views/confirm_delete.html'\n", encoding="utf-8")
    (viewflow_dir / "viewflow" / "fsm").mkdir(parents=True)
    (viewflow_dir / "viewflow" / "fsm" / "base.py").write_text("class Transition: ...", encoding="utf-8")
    (viewflow_dir / "viewflow" / "fsm" / "viewset.py").write_text("class FlowViewsMixin: ...", encoding="utf-8")
    (viewflow_dir / "viewflow" / "contrib").mkdir(parents=True)
    (viewflow_dir / "viewflow" / "contrib" / "auth.py").write_text("class AuthenticationForm: ...\nclass AuthViewset: ...", encoding="utf-8")
    (viewflow_dir / "tests" / "workflow").mkdir(parents=True)
    (viewflow_dir / "tests" / "workflow" / "test_flow_viewset__workflow.py").write_text("class TestWorkflowViewestFlow: ...", encoding="utf-8")
    (viewflow_dir / "tests" / "workflow" / "test_managers_perms.py").write_text(
        "class StaffOnlyFlow:\n"
        "    start = flow.StartHandle(this.start_process).Next(this.task)\n"
        "    task = flow.View(TaskView.as_view()).Assign(lambda activation: activation.process.owner).Permission(auto_create=True).Next(this.end)\n"
        "    end = flow.End()\n",
        encoding="utf-8",
    )
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
    (forms_dir / "viewset.py").write_text("class Forms(Application): ...\ngeneric.FormView.as_view(template_name='forms/form.html')", encoding="utf-8")
    (forms_dir / "views.py").write_text("class CheckoutFormView(generic.FormView): ...\nclass CreateUserView(generic.CreateView): ...", encoding="utf-8")
    (forms_dir / "order_form.py").write_text("class OrderForm:\n    name = forms.CharField(widget=forms.TextInput(attrs={'leading-icon': 'account_box'}))", encoding="utf-8")
    (forms_dir / "templates" / "forms").mkdir(parents=True)
    (forms_dir / "templates" / "forms" / "form.html").write_text("{% render form form.layout %}", encoding="utf-8")
    custom_widget_dir = source_root / "cookbook" / "forms101" / "custom_widget"
    custom_widget_dir.mkdir(parents=True)
    (custom_widget_dir / "forms.py").write_text("class EmailForm:\n    layout = Layout()\nclass OrderForm:\n    total = forms.CharField(widget=forms.TextInput(attrs={'leading-icon': 'attach_money'}))", encoding="utf-8")
    (custom_widget_dir / "viewset.py").write_text("class OrderViewset(ModelViewset): ...", encoding="utf-8")

    patterns_dir = source_root / "cookbook" / "patterns" / "config"
    patterns_dir.mkdir(parents=True)
    (patterns_dir / "urls.py").write_text("site = Site(title='Workflow patterns')", encoding="utf-8")
    (source_root / "cookbook" / "patterns" / "README.md").write_text(
        "# Learn by examples\n\n### Parallel Split/Join\n### Multiple Instances\n### Task to worker assigning\n",
        encoding="utf-8",
    )
    patterns_flows_dir = source_root / "cookbook" / "patterns" / "flows"
    patterns_flows_dir.mkdir(parents=True)
    (patterns_flows_dir / "multiple_instances.py").write_text(
        "from viewflow.workflow import act, flow\n"
        "class MultipleInstances(flow.Flow):\n"
        "    split_infringements = flow.Split().Next(this.issue_notice, task_data_source=act.process.infringement_list)\n"
        "    issue_notice = flow.Function(this.issue_notice_task).Next(this.join_infringements)\n"
        "    join_infringements = flow.Join().Next(this.end)\n",
        encoding="utf-8",
    )
    (patterns_flows_dir / "role_based.py").write_text(
        "from viewflow.workflow import act, flow\n"
        "class RoleBasedFlow(flow.Flow):\n"
        "    start = flow.Start(CreateProcessView.as_view(fields=['travel_request_details'])).Permission(auto_create=True).Next(this.approve_request)\n"
        "    approve_request = flow.View(UpdateProcessView.as_view(fields=['approved'])).Permission('travel.can_approve_request').Next(this.check_approval)\n"
        "    check_approval = flow.If(act.process.approved).Then(this.approved).Else(this.rejected)\n",
        encoding="utf-8",
    )

    guardian_perms_dir = source_root / "cookbook" / "guardian_perms" / "bills"
    guardian_perms_dir.mkdir(parents=True)
    (guardian_perms_dir / "flows.py").write_text(
        "class BillClearingFlow(flow.Flow):\n"
        "    register_bill = flow.Start(CreateArtifactView.as_view()).Permission('department.can_register_bill').Next(this.accept_bill)\n"
        "    accept_bill = flow.View(UpdateProcessView.as_view()).Permission('department.can_accept_bill', obj=lambda process: process.artifact.order_department).Next(this.end)\n"
        "    end = flow.End()\n",
        encoding="utf-8",
    )

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
    (material_dir / "material" / "templates" / "cotton" / "forms" / "calendar").mkdir(parents=True)
    (material_dir / "material" / "templates" / "cotton" / "forms" / "calendar" / "date.html").write_text("<input data-trailing-button />", encoding="utf-8")
    (material_dir / "material" / "templates" / "cotton" / "button").mkdir(parents=True)
    (material_dir / "material" / "templates" / "cotton" / "button" / "filled.html").write_text("<button up-ripple>{{ slot }}</button>", encoding="utf-8")
    (material_dir / "material" / "templates" / "cotton" / "button" / "fab.html").write_text("<button class='rounded-full'>+</button>", encoding="utf-8")
    (material_dir / "material" / "templates" / "cotton" / "card").mkdir(parents=True)
    (material_dir / "material" / "templates" / "cotton" / "card" / "elevated.html").write_text("<div class='bg-surface'>{{ slot }}</div>", encoding="utf-8")
    (material_dir / "material" / "templates" / "cotton" / "table").mkdir(parents=True)
    (material_dir / "material" / "templates" / "cotton" / "table" / "container.html").write_text(
        "<table><caption>{{ caption }}</caption>{{ header }}{{ slot }}{{ footer }}</table>",
        encoding="utf-8",
    )

    generated = module.generate_content(source_root, content_root)
    entry_ids = {item["entry_id"] for item in generated}

    assert "knowledge-src/cookbook-crud101" in entry_ids
    assert "knowledge-src/django-material-theme-customization" in entry_ids
    assert "knowledge-src/crud-admin-shell-layout" in entry_ids
    assert "knowledge-src/viewflow-workflow-orchestration" in entry_ids
    assert "knowledge-src/viewflow-fsm-state-transitions" in entry_ids
    assert "knowledge-src/django-material-frontend-composition" in entry_ids
    assert "knowledge-src/viewflow-view-recipes" in entry_ids
    assert "knowledge-src/viewflow-crud-page-templates" in entry_ids
    assert "knowledge-src/viewflow-navigation-feedback-includes" in entry_ids
    assert "knowledge-src/viewflow-base-template-composition" in entry_ids
    assert "knowledge-src/viewflow-custom-field-renderers" in entry_ids
    assert "knowledge-src/viewflow-forms-layout-composition" in entry_ids
    assert "knowledge-src/viewflow-crud-scaffolding" in entry_ids
    assert "knowledge-src/viewflow-auth-account-scaffolding" in entry_ids
    assert "knowledge-src/viewflow-dashboard-composition" in entry_ids
    assert "knowledge-src/viewflow-advanced-flow-topologies" in entry_ids
    assert "knowledge-src/viewflow-assignment-permission-patterns" in entry_ids
    assert "knowledge-src/django-material-advanced-ux-patterns" in entry_ids
    assert "knowledge-src/viewflow-configurable-metadata-forms" in entry_ids
    assert "knowledge-src/viewflow-configurable-workflow-runtime-patterns" in entry_ids
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
    assert "Input adornment recipe" in frontend_skill.read_text(encoding="utf-8")
    assert "Custom widget forms with leading-icon attrs and computed tags" in frontend_skill.read_text(encoding="utf-8")

    forms_skill = content_root / "knowledge-src" / "skills" / "viewflow-forms-layout-composition" / "SKILL.md"
    assert forms_skill.exists()
    assert "FieldSet" in forms_skill.read_text(encoding="utf-8")
    assert "FormView registration inside an Application" in forms_skill.read_text(encoding="utf-8")
    assert "Leading-icon and custom widget attribute examples" in forms_skill.read_text(encoding="utf-8")

    view_recipes_skill = content_root / "knowledge-src" / "skills" / "viewflow-view-recipes" / "SKILL.md"
    assert view_recipes_skill.exists()
    assert "DetailViewMixin" in view_recipes_skill.read_text(encoding="utf-8")
    assert "DeleteViewMixin" in view_recipes_skill.read_text(encoding="utf-8")
    assert "Application-mounted FormView and CreateView routes with titles/buttons" in view_recipes_skill.read_text(encoding="utf-8")
    assert "Shared form template with render form form.layout and action footer" in view_recipes_skill.read_text(encoding="utf-8")

    crud_templates_skill = content_root / "knowledge-src" / "skills" / "viewflow-crud-page-templates" / "SKILL.md"
    assert crud_templates_skill.exists()
    assert "object_detail_card" in crud_templates_skill.read_text(encoding="utf-8")
    assert "Delete and transition confirmation contracts" in crud_templates_skill.read_text(encoding="utf-8")
    assert "vf-card__breadcrumbs" in crud_templates_skill.read_text(encoding="utf-8")

    includes_skill = content_root / "knowledge-src" / "skills" / "viewflow-navigation-feedback-includes" / "SKILL.md"
    assert includes_skill.exists()
    assert "list_bulk_actions" in includes_skill.read_text(encoding="utf-8")
    assert "view.get_page_actions()" in includes_skill.read_text(encoding="utf-8")
    assert "vf-snackbar" in includes_skill.read_text(encoding="utf-8")

    base_template_skill = content_root / "knowledge-src" / "skills" / "viewflow-base-template-composition" / "SKILL.md"
    assert base_template_skill.exists()
    assert "page-toolbar" in base_template_skill.read_text(encoding="utf-8")
    assert "viewflow/base_page.html" in base_template_skill.read_text(encoding="utf-8")

    custom_renderer_skill = content_root / "knowledge-src" / "skills" / "viewflow-custom-field-renderers" / "SKILL.md"
    assert custom_renderer_skill.exists()
    assert "AjaxModelSelectRenderer" in custom_renderer_skill.read_text(encoding="utf-8")
    assert "value-label" in custom_renderer_skill.read_text(encoding="utf-8")
    assert "form_widgets" in custom_renderer_skill.read_text(encoding="utf-8")

    auth_skill = content_root / "knowledge-src" / "skills" / "viewflow-auth-account-scaffolding" / "SKILL.md"
    assert auth_skill.exists()
    assert "AuthViewset" in auth_skill.read_text(encoding="utf-8")

    advanced_flow_skill = content_root / "knowledge-src" / "skills" / "viewflow-advanced-flow-topologies" / "SKILL.md"
    assert advanced_flow_skill.exists()
    assert "SplitFirst" in advanced_flow_skill.read_text(encoding="utf-8")
    assert "NSubprocess" in advanced_flow_skill.read_text(encoding="utf-8")
    assert "Multiple Instances" in advanced_flow_skill.read_text(encoding="utf-8")

    assignment_skill = content_root / "knowledge-src" / "skills" / "viewflow-assignment-permission-patterns" / "SKILL.md"
    assert assignment_skill.exists()
    assert "Assign" in assignment_skill.read_text(encoding="utf-8")
    assert "Guardian-backed department bill approval flow" in assignment_skill.read_text(encoding="utf-8")
    assert "has_object_perm" in assignment_skill.read_text(encoding="utf-8")

    advanced_ux_skill = content_root / "knowledge-src" / "skills" / "django-material-advanced-ux-patterns" / "SKILL.md"
    assert advanced_ux_skill.exists()
    assert "Cotton component architecture" in advanced_ux_skill.read_text(encoding="utf-8")
    assert "Table container contract" in advanced_ux_skill.read_text(encoding="utf-8")
    assert "Floating action button primitive" in advanced_ux_skill.read_text(encoding="utf-8")

    metadata_forms_skill = content_root / "knowledge-src" / "skills" / "viewflow-configurable-metadata-forms" / "SKILL.md"
    assert metadata_forms_skill.exists()
    assert "FormDependentSelectMixin" in metadata_forms_skill.read_text(encoding="utf-8")
    assert "archival metadata" in metadata_forms_skill.read_text(encoding="utf-8")
    assert "FormSetField" in metadata_forms_skill.read_text(encoding="utf-8")

    workflow_runtime_skill = content_root / "knowledge-src" / "skills" / "viewflow-configurable-workflow-runtime-patterns" / "SKILL.md"
    assert workflow_runtime_skill.exists()
    assert "Multiple Instances" in workflow_runtime_skill.read_text(encoding="utf-8")
    assert "task_data_source" in workflow_runtime_skill.read_text(encoding="utf-8")
    assert "Assign(...)" in workflow_runtime_skill.read_text(encoding="utf-8")

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
