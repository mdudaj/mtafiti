#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FRAMEWORK_KNOWLEDGE = {
    "django": {
        "name": "Django",
        "type": "Framework",
        "installed": True,
        "source_urls": [
            "https://docs.djangoproject.com/en/5.1/intro/overview/",
            "https://docs.djangoproject.com/en/5.1/topics/http/urls/",
            "https://docs.djangoproject.com/en/5.1/topics/forms/",
        ],
        "concepts": [
            "Model",
            "View",
            "URLconf",
            "Form",
            "Middleware",
            "Admin",
            "Migration",
        ],
        "components": [
            "django.db.models",
            "django.urls.path",
            "django.http.JsonResponse",
            "django.views.decorators.csrf.csrf_exempt",
            "django.contrib.admin",
        ],
        "configuration_patterns": [
            "Configure apps through INSTALLED_APPS.",
            "Register request processing through MIDDLEWARE.",
            "Declare routes with path() in URLconf modules.",
            "Manage schema evolution with makemigrations and migrate.",
        ],
        "api_surfaces": [
            "ORM model fields and queryset APIs",
            "Function-based or class-based view dispatch",
            "Forms and widgets",
            "Admin site registration",
        ],
        "architecture": [
            "Model-driven server-side web framework.",
            "URL dispatch maps request paths to Python callables.",
            "Views coordinate request parsing, persistence, and response rendering.",
        ],
        "best_practices": [
            "Keep URL configuration explicit and versioned for stable API contracts.",
            "Use models and migrations as the source of truth for persistence.",
            "Use POST for mutating form/API requests and pair it with CSRF or equivalent protections.",
        ],
        "context_hub": {
            "profile": "django",
        },
    },
    "viewflow": {
        "name": "Viewflow",
        "type": "Framework",
        "installed": False,
        "source_urls": [
            "https://github.com/viewflow/viewflow",
            "https://github.com/viewflow/cookbook",
        ],
        "concepts": [
            "Flow",
            "Process",
            "Start",
            "View",
            "End",
            "FlowAppViewset",
            "Site",
        ],
        "components": [
            "viewflow.workflow.flow.Flow",
            "viewflow.workflow.flow.Start",
            "viewflow.workflow.flow.View",
            "viewflow.workflow.flow.End",
            "viewflow.workflow.models.Process",
        ],
        "configuration_patterns": [
            "Install django-viewflow and add viewflow apps to INSTALLED_APPS.",
            "Create Process models for workflow state and data.",
            "Register Flow classes through FlowAppViewset and Site URLs.",
        ],
        "api_surfaces": [
            "Flow classes with Start/View/End nodes",
            "Process model integration",
            "AuthViewset and FlowAppViewset URL registration",
            "Cookbook samples for workflow, CRUD, and dashboards",
        ],
        "architecture": [
            "Django-native low-code framework for workflows and business apps.",
            "Workflows are modeled as Flow classes that advance Process instances through nodes.",
            "The framework ships integrated routing and UI viewsets for workflow-driven applications.",
        ],
        "best_practices": [
            "Keep process data in explicit Process models.",
            "Model workflow steps as composable Flow nodes with clear assignee/transition boundaries.",
            "Use cookbook examples to validate dashboard and workflow interaction patterns before customization.",
        ],
        "context_hub": {
            "profile": "viewflow",
        },
    },
    "django_material": {
        "name": "django-material",
        "type": "Framework",
        "installed": False,
        "source_urls": [
            "https://github.com/viewflow/django-material",
        ],
        "concepts": [
            "Material Design 3",
            "Card",
            "Form",
            "Table",
            "Navigation",
            "CRUD Views",
            "Responsive Layout",
        ],
        "components": [
            "material/base.html",
            "c-button",
            "c-card",
            "CRUD/admin templates",
            "TailwindCSS-backed design tokens",
        ],
        "configuration_patterns": [
            "Install django-material and add material to INSTALLED_APPS.",
            "Extend material/base.html in server-rendered templates.",
            "Compose UI with django-cotton component tags such as c-button and c-card.",
        ],
        "api_surfaces": [
            "Material templates",
            "Component tags",
            "CRUD and admin page shells",
            "Responsive navigation and form widgets",
        ],
        "architecture": [
            "Server-rendered Material Design 3 component library for Django.",
            "Combines low-level components with CRUD/admin scaffolds without a SPA dependency.",
            "Optimized for predictable UI composition and AI-assisted code generation.",
        ],
        "best_practices": [
            "Use built-in components and layout primitives before creating custom widgets.",
            "Prefer responsive, accessible component composition over custom JavaScript-heavy screens.",
            "Keep template inheritance centered on material/base.html for consistency.",
        ],
        "context_hub": {
            "profile": "django-material",
        },
    },
}

ECOSYSTEM_CONTEXT_PROFILES = {
    "django": {
        "search_queries": ["django", "django forms", "django urls"],
        "doc_ids": ["django/forms", "django/urls"],
        "accept_terms": ["django"],
    },
    "django-tenants": {
        "search_queries": ["django-tenants", "django tenants"],
        "doc_ids": [],
        "accept_terms": ["django-tenants", "django tenants"],
    },
    "celery": {
        "search_queries": ["celery", "celery python"],
        "doc_ids": [],
        "accept_terms": ["celery"],
    },
    "psycopg": {
        "search_queries": ["psycopg", "postgres python driver"],
        "doc_ids": [],
        "accept_terms": ["psycopg"],
    },
    "pika": {
        "search_queries": ["pika rabbitmq python"],
        "doc_ids": [],
        "accept_terms": ["pika"],
    },
    "prometheus-client": {
        "search_queries": ["prometheus python client", "prometheus"],
        "doc_ids": [],
        "accept_terms": ["prometheus"],
    },
    "pytest": {
        "search_queries": ["pytest", "pytest python"],
        "doc_ids": [],
        "accept_terms": ["pytest"],
    },
    "pytest-django": {
        "search_queries": ["pytest django", "pytest-django"],
        "doc_ids": [],
        "accept_terms": ["pytest", "django"],
    },
    "postgres": {
        "search_queries": ["postgres", "postgresql"],
        "doc_ids": [],
        "accept_terms": ["postgres", "postgresql"],
    },
    "rabbitmq": {
        "search_queries": ["rabbitmq", "amqp"],
        "doc_ids": [],
        "accept_terms": ["rabbitmq", "amqp"],
    },
    "kubernetes": {
        "search_queries": ["kubernetes", "k8s"],
        "doc_ids": [],
        "accept_terms": ["kubernetes", "k8s"],
    },
    "helm": {
        "search_queries": ["helm", "helm kubernetes"],
        "doc_ids": [],
        "accept_terms": ["helm"],
    },
    "docker-compose": {
        "search_queries": ["docker compose", "docker-compose"],
        "doc_ids": [],
        "accept_terms": ["docker compose", "docker-compose"],
    },
    "github-actions": {
        "search_queries": ["github actions", "github workflow"],
        "doc_ids": [],
        "accept_terms": ["github actions", "github workflow"],
    },
    "viewflow": {
        "search_queries": ["viewflow", "django workflow"],
        "doc_ids": [],
        "accept_terms": ["viewflow"],
    },
    "django-material": {
        "search_queries": ["django-material", "django material"],
        "doc_ids": [],
        "accept_terms": ["django-material", "django material", "material design"],
    },
}

_CONTEXT_HUB_CACHE: dict[str, dict[str, Any]] = {}

PACKAGE_CLASSIFICATIONS = {
    "django": "Framework",
    "django-tenants": "Framework",
    "celery": "Framework",
    "psycopg": "Library",
    "pika": "Library",
    "prometheus-client": "Library",
    "pytest": "Tool",
    "pytest-django": "Tool",
}

FRAMEWORK_ALIASES = {
    "django": "django",
    "django-tenants": "django-tenants",
    "celery": "celery",
    "viewflow": "viewflow",
    "django-material": "django_material",
    "material": "django_material",
}

IMPORT_TO_NODE = {
    "django": "framework:django",
    "django_tenants": "framework:django-tenants",
    "celery": "framework:celery",
    "pika": "library:pika",
    "psycopg": "library:psycopg",
    "prometheus_client": "library:prometheus-client",
}

QUERY_EXAMPLES = [
    {
        "question": "Find skills related to dashboards",
        "command": 'python .github/scripts/query_knowledge_graph.py --type Skill --text dashboard',
    },
    {
        "question": "Find UI components compatible with django-material",
        "command": 'python .github/scripts/query_knowledge_graph.py --type UIComponent --relationship uses --target framework:django_material',
    },
    {
        "question": "Find workflow nodes supported by Viewflow",
        "command": 'python .github/scripts/query_knowledge_graph.py --type Workflow --relationship uses --target framework:viewflow',
    },
    {
        "question": "Find modules implementing workflows",
        "command": 'python .github/scripts/query_knowledge_graph.py --type Module --relationship implements --target workflow:workflow_lifecycle',
    },
]


@dataclass
class PythonFunction:
    name: str
    line: int
    decorators: list[str]
    call_names: list[str]
    methods: list[str]
    roles: list[str]


@dataclass
class PythonClass:
    name: str
    line: int
    bases: list[str]
    fields: list[str]


@dataclass
class PythonModule:
    path: Path
    module_name: str
    imports: list[str]
    classes: list[PythonClass]
    functions: list[PythonFunction]


class CallCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: set[str] = set()
        self.methods: set[str] = set()
        self.roles: set[str] = set()

    def visit_Call(self, node: ast.Call) -> Any:
        name = dotted_name(node.func)
        if name:
            self.calls.add(name)
            if name.endswith("require_role") and node.args:
                literal = literal_value(node.args[1] if len(node.args) > 1 else node.args[0])
                if isinstance(literal, str):
                    self.roles.add(literal)
            if name.endswith("require_any_role") and node.args:
                literal = literal_value(node.args[1] if len(node.args) > 1 else node.args[0])
                if isinstance(literal, (list, tuple, set)):
                    for item in literal:
                        if isinstance(item, str):
                            self.roles.add(item)
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> Any:
        if (
            isinstance(node.left, ast.Attribute)
            and dotted_name(node.left) == "request.method"
        ):
            for comparator in node.comparators:
                literal = literal_value(comparator)
                if isinstance(literal, str):
                    self.methods.add(literal)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, str) and node.value in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
            self.methods.add(node.value)


def dotted_name(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Call):
        return dotted_name(node.func)
    if isinstance(node, ast.Subscript):
        return dotted_name(node.value)
    return ""


def literal_value(node: ast.AST | None) -> Any:
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalize_route(route: str) -> str:
    route = route.strip().strip("/")
    if not route:
        return "/"
    route = re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", route)
    return f"/{route}"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def module_name_from_path(root: Path, path: Path) -> str:
    return ".".join(path.relative_to(root).with_suffix("").parts)


def parse_python_module(root: Path, path: Path) -> PythonModule:
    tree = ast.parse(read_text(path), filename=str(path))
    imports: set[str] = set()
    classes: list[PythonClass] = []
    functions: list[PythonFunction] = []

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                base_parts = module_name_from_path(root, path).split(".")[:-1]
                if module:
                    base_parts.extend(module.split("."))
                module = ".".join(base_parts)
            if module:
                imports.add(module)
        elif isinstance(node, ast.ClassDef):
            bases = [dotted_name(base) for base in node.bases if dotted_name(base)]
            fields: list[str] = []
            for item in node.body:
                value = None
                target = None
                if isinstance(item, ast.Assign) and item.targets:
                    target = item.targets[0]
                    value = item.value
                elif isinstance(item, ast.AnnAssign):
                    target = item.target
                    value = item.value
                if isinstance(target, ast.Name) and isinstance(value, ast.Call):
                    field_name = dotted_name(value.func)
                    if field_name.startswith("models.") or field_name.endswith("Field"):
                        fields.append(target.id)
            classes.append(
                PythonClass(
                    name=node.name,
                    line=node.lineno,
                    bases=bases,
                    fields=sorted(fields),
                )
            )
        elif isinstance(node, ast.FunctionDef):
            collector = CallCollector()
            collector.visit(node)
            decorators = [dotted_name(decorator) for decorator in node.decorator_list if dotted_name(decorator)]
            functions.append(
                PythonFunction(
                    name=node.name,
                    line=node.lineno,
                    decorators=sorted(decorators),
                    call_names=sorted(collector.calls),
                    methods=sorted(collector.methods),
                    roles=sorted(collector.roles),
                )
            )

    return PythonModule(
        path=path,
        module_name=module_name_from_path(root, path),
        imports=sorted(imports),
        classes=classes,
        functions=functions,
    )


def collect_python_modules(backend_root: Path) -> list[PythonModule]:
    modules: list[PythonModule] = []
    for path in sorted(backend_root.rglob("*.py")):
        relative = path.relative_to(backend_root)
        if any(part in {"migrations", "__pycache__", "tests"} for part in relative.parts):
            continue
        modules.append(parse_python_module(backend_root, path))
    return modules


def parse_requirements(path: Path) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    if not path.exists():
        return packages
    for raw_line in read_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-r "):
            continue
        name = re.split(r"[<>=\[]", line, maxsplit=1)[0].strip()
        version_match = re.search(r"==([^;]+)", line)
        version = version_match.group(1).strip() if version_match else "unspecified"
        packages.append({"name": name, "version": version})
    return packages


def parse_simple_yaml_keys(path: Path, section: str, indent: int) -> list[str]:
    if not path.exists():
        return []
    lines = read_text(path).splitlines()
    capture = False
    keys: list[str] = []
    for line in lines:
        if not capture and line.strip() == f"{section}:":
            capture = True
            continue
        if not capture:
            continue
        if re.match(r"^\S", line):
            break
        match = re.match(rf"^\s{{{indent}}}([A-Za-z0-9_.-]+):\s*$", line)
        if match:
            keys.append(match.group(1))
    return keys


def extract_urlpatterns(path: Path) -> list[dict[str, Any]]:
    tree = ast.parse(read_text(path), filename=str(path))
    urlpatterns: list[dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "urlpatterns" for target in node.targets):
            continue
        for item in getattr(node.value, "elts", []):
            if not isinstance(item, ast.Call) or dotted_name(item.func) != "path":
                continue
            if len(item.args) < 2:
                continue
            route = literal_value(item.args[0])
            if not isinstance(route, str):
                continue
            view_name = dotted_name(item.args[1]).split(".")[-1]
            name_kw = next((kw.value for kw in item.keywords if kw.arg == "name"), None)
            urlpatterns.append(
                {
                    "path": normalize_route(route),
                    "route": route,
                    "view": view_name,
                    "name": literal_value(name_kw) if name_kw is not None else view_name,
                }
            )
    return urlpatterns


def extract_settings(settings_path: Path) -> dict[str, Any]:
    tree = ast.parse(read_text(settings_path), filename=str(settings_path))
    values: dict[str, Any] = {}
    settings_text = read_text(settings_path)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    literal = literal_value(node.value)
                    if literal is not None:
                        values[target.id] = literal
    shared_apps = values.get("SHARED_APPS", [])
    tenant_apps = values.get("TENANT_APPS", [])
    middleware = values.get("MIDDLEWARE", [])
    databases = values.get("DATABASES", {})
    database_engine = databases.get("default", {}).get("ENGINE", "")
    if not database_engine:
        match = re.search(r"'ENGINE'\s*:\s*'([^']+)'", settings_text)
        database_engine = match.group(1) if match else ""
    return {
        "shared_apps": shared_apps,
        "tenant_apps": tenant_apps,
        "installed_apps": [*shared_apps, *tenant_apps],
        "middleware": middleware,
        "database_engine": database_engine,
    }


def find_module(modules: list[PythonModule], module_name: str) -> PythonModule | None:
    return next((module for module in modules if module.module_name == module_name), None)


def extract_models(modules: list[PythonModule]) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    for module in modules:
        for cls in module.classes:
            if any(base.endswith("Model") or base.endswith("TenantMixin") or base.endswith("DomainMixin") for base in cls.bases):
                models.append(
                    {
                        "name": cls.name,
                        "module": module.module_name,
                        "fields": cls.fields,
                        "source": f"{module.path.relative_to(module.path.parents[2])}:{cls.line}",
                    }
                )
    return sorted(models, key=lambda item: item["name"])


def extract_tasks(modules: list[PythonModule]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for module in modules:
        for function in module.functions:
            if any(name.endswith("shared_task") or name.endswith("app.task") for name in function.decorators):
                tasks.append(
                    {
                        "name": function.name,
                        "module": module.module_name,
                        "calls": function.call_names,
                        "source": f"{module.path.relative_to(module.path.parents[2])}:{function.line}",
                    }
                )
    return sorted(tasks, key=lambda item: item["name"])


def extract_views(modules: list[PythonModule]) -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = []
    module = find_module(modules, "core.views")
    if not module:
        return views
    for function in module.functions:
        if function.name.startswith("_"):
            continue
        if function.methods or function.name in {"health", "healthz", "livez", "readyz", "metrics"}:
            views.append(
                {
                    "name": function.name,
                    "module": module.module_name,
                    "methods": function.methods or ["GET", "POST"],
                    "roles": function.roles,
                    "ui_component": function.name.startswith("ui_"),
                    "source": f"{module.path.relative_to(module.path.parents[2])}:{function.line}",
                }
            )
    return sorted(views, key=lambda item: item["name"])


def detect_programming_languages(root: Path) -> list[dict[str, Any]]:
    counts = {
        "Python": len(list(root.rglob("*.py"))),
        "YAML": len(list(root.rglob("*.yaml"))) + len(list(root.rglob("*.yml"))),
        "Shell": len(list(root.rglob("*.sh"))),
        "Markdown": len(list(root.rglob("*.md"))),
    }
    return [
        {"name": name, "file_count": count}
        for name, count in counts.items()
        if count
    ]


def resolve_app_root(root: Path) -> Path:
    candidates = (root / "src", root / "backend")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Could not locate application root. Checked: "
        + ", ".join(str(path) for path in candidates)
    )


def build_environment_inventory(root: Path, modules: list[PythonModule], urlpatterns: list[dict[str, Any]], settings: dict[str, Any]) -> dict[str, Any]:
    app_root = resolve_app_root(root)
    requirements = parse_requirements(app_root / "requirements.txt")
    requirements_dev = parse_requirements(app_root / "requirements-dev.txt")
    package_index = {item["name"]: item["version"] for item in [*requirements, *requirements_dev]}
    ci_jobs = parse_simple_yaml_keys(root / ".github" / "workflows" / "ci.yml", "jobs", 2)
    compose_services = parse_simple_yaml_keys(root / "docker-compose.yml", "services", 2)
    models = extract_models(modules)
    tasks = extract_tasks(modules)
    views = extract_views(modules)

    frameworks: list[dict[str, Any]] = []
    for package_name in ["Django", "django-tenants", "celery"]:
        version = package_index.get(package_name, package_index.get(package_name.lower(), "unspecified"))
        frameworks.append(
            {
                "name": package_name,
                "version": version,
                "status": "installed",
            }
        )
    frameworks.extend(
        [
            {
                "name": "Viewflow",
                "version": "documentation-profile",
                "status": "documented_target",
                "evidence": "docs/workflow-ui.md",
            },
            {
                "name": "django-material",
                "version": "documentation-profile",
                "status": "documented_target",
                "evidence": "docs/workflow-ui.md",
            },
        ]
    )

    libraries: list[dict[str, Any]] = []
    for package_name in ["pika", "psycopg", "prometheus-client"]:
        if package_name in package_index:
            libraries.append({"name": package_name, "version": package_index[package_name], "status": "installed"})

    frontend_libraries = [
        {
            "name": "django-material",
            "status": "documented_target",
            "note": "Referenced in workflow UI design notes but not installed in backend requirements.",
        }
    ]

    database_layers = [
        {"name": "PostgreSQL", "status": "service", "evidence": "docker-compose.yml"},
        {"name": settings.get("database_engine", ""), "status": "configured_engine", "evidence": "src/config/settings.py"},
        {"name": "psycopg", "status": "driver", "evidence": "src/requirements.txt"},
    ]

    apis = []
    for item in urlpatterns:
        if not item["path"].startswith("/api/v1/"):
            continue
        domain = item["path"].split("/")[3] if len(item["path"].split("/")) > 3 else "root"
        apis.append(
            {
                "name": item["name"],
                "path": item["path"],
                "domain": domain,
                "handler": item["view"],
            }
        )

    infrastructure = [
        {"name": "Docker Compose", "status": "configured", "evidence": "docker-compose.yml"},
        {"name": "Kubernetes manifests", "status": "configured", "evidence": "deploy/k8s"},
        {"name": "Helm chart", "status": "configured", "evidence": "deploy/helm/mtafiti-platform"},
        {"name": "GitHub Actions", "status": "configured", "evidence": ".github/workflows/ci.yml"},
    ]

    services = [
        {"name": service, "status": "configured"} for service in compose_services
    ]
    services.extend(
        [
            {"name": "backend", "status": "application"},
            {"name": "worker", "status": "application"},
        ]
    )

    internal_modules = [
        {
            "name": module.module_name,
            "path": str(module.path.relative_to(root)),
            "imports": module.imports[:8],
        }
        for module in modules
        if module.module_name.split(".")[0] in {"config", "core", "tenants"}
    ]

    context_hub_profiles = {
        key: build_context_hub_entry(key)
        for key in [
            "django",
            "django-tenants",
            "celery",
            "psycopg",
            "pika",
            "prometheus-client",
            "pytest",
            "postgres",
            "rabbitmq",
            "kubernetes",
            "helm",
            "github-actions",
        ]
    }

    return {
        "EnvironmentInventory": {
            "programming_languages": detect_programming_languages(root),
            "frameworks": frameworks,
            "libraries": sorted(libraries, key=lambda item: item["name"]),
            "frontend_libraries": frontend_libraries,
            "database_layers": database_layers,
            "services": sorted(services, key=lambda item: item["name"]),
            "APIs": sorted(apis, key=lambda item: item["path"]),
            "infrastructure": infrastructure,
            "ci_cd_tools": [{"name": name, "status": "configured"} for name in ci_jobs],
            "internal_modules": internal_modules,
            "context_hub_registry": {
                "available": shutil.which("chub") is not None,
                "profiles": context_hub_profiles,
                "local_source_note": "chub update refreshes configured sources. To use a git repo, clone it locally, run `chub build <content-dir>`, and add the built dist path under `sources[].path` in ~/.chub/config.yaml.",
            },
            "code_analysis_summary": {
                "modules_scanned": len(modules),
                "models_detected": len(models),
                "views_detected": len(views),
                "tasks_detected": len(tasks),
            },
        }
    }


def build_skills(models: list[dict[str, Any]], tasks: list[dict[str, Any]], urlpatterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ui_paths = [item for item in urlpatterns if item["path"].startswith("/api/v1/ui/operations/")]
    has_lineage = any(item["name"] == "LineageEdge" for item in models)
    has_projects = any(item["name"] == "ProjectMembership" for item in models)
    has_workflows = any(item["name"].startswith("Workflow") for item in models)

    skills = [
        {
            "id": "define_django_json_api_endpoint",
            "name": "Define Django JSON API Endpoint",
            "description": "Create a versioned Django function-based endpoint backed by explicit URLconf routing and JsonResponse payloads.",
            "inputs": ["url_path", "request_methods", "serializer_logic"],
            "tools": ["Django"],
            "steps": [
                "Add a path() entry in src/config/urls.py.",
                "Implement request parsing and response shaping in core.views.",
                "Enforce versioning, tenancy, and role checks consistently.",
            ],
            "evidence": ["src/config/urls.py", "src/core/views.py"],
        },
        {
            "id": "implement_schema_per_tenant_api",
            "name": "Implement Schema-per-Tenant API",
            "description": "Scope models, requests, and background execution to tenant schemas using django-tenants.",
            "inputs": ["tenant_domain", "tenant_scoped_model", "request_context"],
            "tools": ["Django", "django-tenants"],
            "steps": [
                "Register tenant and domain models in tenants.models.",
                "Resolve tenants from the Host header with EDMPTenantMiddleware.",
                "Execute ORM access inside tenant schemas and reject cross-tenant access.",
            ],
            "evidence": ["src/tenants/models.py", "src/config/settings.py", "src/core/views.py"],
        },
        {
            "id": "implement_tenant_aware_background_task",
            "name": "Implement Tenant-aware Background Task",
            "description": "Create a Celery shared_task that runs inside a tenant schema and emits audit or domain events.",
            "inputs": ["tenant_schema", "task_payload", "event_metadata"],
            "tools": ["Celery", "Django"],
            "steps": [
                "Declare the task with shared_task(base=TenantTask).",
                "Load tenant-scoped models and perform the state transition.",
                "Publish completion and audit events with correlation metadata.",
            ],
            "evidence": ["src/core/tasks.py", "src/core/celery.py", "src/core/events.py"],
        },
    ]

    if has_workflows:
        skills.append(
            {
                "id": "implement_workflow_lifecycle",
                "name": "Implement Workflow Lifecycle",
                "description": "Model explicit workflow definition, run, task, and transition lifecycles using Django models and JSON APIs.",
                "inputs": ["workflow_definition", "run_payload", "transition_action"],
                "tools": ["Django"],
                "steps": [
                    "Model definitions, runs, and tasks as persistent Django models.",
                    "Expose create/list/detail/transition endpoints under /api/v1/workflows.",
                    "Apply role checks and tenant-scoped task visibility rules.",
                ],
                "evidence": ["src/core/models.py", "src/core/views.py", "src/tests/test_workflow_ui_api.py"],
            }
        )

    if ui_paths:
        skills.append(
            {
                "id": "compose_operations_dashboard_contract",
                "name": "Compose Operations Dashboard Contract",
                "description": "Aggregate operational summary cards and workbench payloads for dashboard-style UI surfaces.",
                "inputs": ["dashboard_panels", "tenant_scope", "project_filter"],
                "tools": ["Django", "django-material"],
                "steps": [
                    "Create API-focused UI endpoints under /api/v1/ui/operations.",
                    "Return summary widgets and allowed actions for each workbench item.",
                    "Preserve tenant scoping so future server-rendered dashboards stay isolated.",
                ],
                "evidence": ["docs/workflow-ui.md", "src/core/views.py"],
            }
        )

    if has_lineage:
        skills.append(
            {
                "id": "model_lineage_graph_edges",
                "name": "Model Lineage Graph Edges",
                "description": "Represent asset-to-asset lineage as directed graph edges backed by Django models and APIs.",
                "inputs": ["from_asset", "to_asset", "edge_type"],
                "tools": ["Django"],
                "steps": [
                    "Store lineage relationships in a dedicated edge model.",
                    "Expose query and mutation APIs for lineage traversal.",
                    "Attach properties and metadata needed for downstream reasoning.",
                ],
                "evidence": ["src/core/models.py", "docs/lineage.md"],
            }
        )

    if has_projects:
        skills.append(
            {
                "id": "manage_project_membership_lifecycle",
                "name": "Manage Project Membership Lifecycle",
                "description": "Handle invitations, membership transitions, and workspace configuration for tenant-local projects.",
                "inputs": ["project", "member_identity", "lifecycle_action"],
                "tools": ["Django"],
                "steps": [
                    "Persist membership and invitation state in project models.",
                    "Expose invitation and lifecycle APIs for member operations.",
                    "Emit notification and audit data for role or status changes.",
                ],
                "evidence": ["src/core/models.py", "src/core/views.py"],
            }
        )

    skills.append(
        {
            "id": "plan_viewflow_material_workflow_ui",
            "name": "Plan Viewflow + Material Workflow UI",
            "description": "Translate workflow UI design notes into a future Viewflow and django-material implementation plan.",
            "inputs": ["workflow_nodes", "material_components", "role_matrix"],
            "tools": ["Viewflow", "django-material"],
            "steps": [
                "Map workflow states and actions to Viewflow Flow nodes.",
                "Map dashboards, cards, and menus to django-material components.",
                "Keep server-side role enforcement and tenant isolation aligned with backend APIs.",
            ],
            "evidence": ["docs/workflow-ui.md", "https://github.com/viewflow/viewflow", "https://github.com/viewflow/django-material"],
        }
    )

    return sorted(skills, key=lambda item: item["id"])


def build_context_hub_entry(profile_key: str) -> dict[str, Any]:
    cached = _CONTEXT_HUB_CACHE.get(profile_key)
    if cached is not None:
        return json.loads(json.dumps(cached))
    profile = ECOSYSTEM_CONTEXT_PROFILES.get(profile_key, {"search_queries": [profile_key], "doc_ids": []})
    available = shutil.which("chub") is not None
    entry = {
        "available": available,
        "install_command": "npm install -g @aisuite/chub",
        "update_command": "chub update",
        "help_command": "chub help",
        "search_queries": profile["search_queries"],
        "get_commands": [f"chub get {item}" for item in profile.get("doc_ids", [])],
        "status": "ready" if available else "install_required",
        "local_source_workflow": {
            "supports_git_url_directly": False,
            "clone_and_build_steps": [
                "git clone <repo-url> <local-dir>",
                "chub build <content-dir> -o <content-dir>/dist",
                "Add `<content-dir>/dist` as `sources[].path` in ~/.chub/config.yaml",
                "Run `chub update` to refresh configured sources",
            ],
        },
    }
    if available:
        search_results: list[dict[str, Any]] = []
        top_ids: list[str] = []
        for query in profile["search_queries"]:
            result = run_chub_search(query, accept_terms=profile.get("accept_terms", []))
            search_results.append(result)
            for match in result.get("matches", []):
                if match["id"] not in top_ids:
                    top_ids.append(match["id"])
        entry["search_results"] = search_results
        entry["search_status"] = "matched" if top_ids else "no_registry_match"
        if top_ids:
            entry["candidate_registry_ids"] = top_ids[:5]
        docs: list[dict[str, str]] = []
        for command in entry["get_commands"][:2]:
            content = run_command(command)
            if content:
                docs.append({"command": command, "content": content})
        if docs:
            entry["retrieved_docs"] = docs
    _CONTEXT_HUB_CACHE[profile_key] = entry
    return json.loads(json.dumps(entry))


def run_command(command: str) -> str:
    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()[:4000]


def run_command_args(args: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None


def run_chub_search(query: str, accept_terms: list[str] | None = None) -> dict[str, Any]:
    completed = run_command_args(["chub", "search", query, "--json"])
    if completed is None:
        return {"query": query, "total": 0, "matches": [], "status": "unavailable"}
    stdout = completed.stdout.strip()
    if completed.returncode == 0 and stdout.startswith("{"):
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {}
        raw_matches = [
            {
                "id": item.get("id", ""),
                "source": item.get("source", ""),
                "description": item.get("description", ""),
            }
            for item in payload.get("results", [])[:3]
        ]
        matches = raw_matches
        if accept_terms:
            lowered_terms = [term.lower() for term in accept_terms]
            matches = [
                item
                for item in raw_matches
                if any(term in f"{item['id']} {item['description']}".lower() for term in lowered_terms)
            ]
        return {
            "query": query,
            "total": len(matches),
            "matches": matches,
            "status": "matched" if matches else "no_registry_match",
        }
    no_results_text = stdout or completed.stderr.strip()
    if "No results" in no_results_text:
        return {"query": query, "total": 0, "matches": [], "status": "no_registry_match"}
    return {
        "query": query,
        "total": 0,
        "matches": [],
        "status": "search_error",
        "message": no_results_text[:500],
    }


def build_framework_knowledge(root: Path, settings: dict[str, Any]) -> dict[str, dict[str, Any]]:
    installed_apps = set(settings.get("installed_apps", []))
    framework_data: dict[str, dict[str, Any]] = {}
    for slug, profile in FRAMEWORK_KNOWLEDGE.items():
        entry = dict(profile)
        if slug == "django":
            repository_fit = {
                "status": "installed",
                "evidence": [
                    "src/requirements.txt",
                    "src/config/settings.py",
                    "src/config/urls.py",
                ],
                "repository_patterns": [
                    "Function-based JsonResponse APIs in core.views",
                    "Django model layer in core.models",
                    "Middleware-driven request instrumentation and auth",
                ],
            }
        elif slug == "viewflow":
            repository_fit = {
                "status": "documented_target",
                "evidence": ["docs/workflow-ui.md"],
                "repository_patterns": [
                    "Workflow UI notes describe Viewflow as the target workflow engine.",
                    "Current code uses custom workflow models instead of installed Viewflow packages.",
                ],
            }
        else:
            repository_fit = {
                "status": "documented_target",
                "evidence": ["docs/workflow-ui.md"],
                "repository_patterns": [
                    "Workflow UI notes describe django-material as the planned server-rendered UI stack.",
                    "Current backend has API-only operational UI endpoints and no material app in INSTALLED_APPS.",
                ],
            }
        entry["repository_fit"] = repository_fit
        entry["context_hub"] = build_context_hub_entry(profile["context_hub"]["profile"])
        if slug == "django_material":
            entry["installed_app_present"] = "material" in installed_apps
        framework_data[slug] = entry
    return framework_data


def make_node(node_type: str, name: str, description: str, **metadata: Any) -> dict[str, Any]:
    slug = metadata.pop("slug", slugify(name))
    return {
        "id": f"{node_type.lower()}:{slug}",
        "type": node_type,
        "name": name,
        "description": description,
        **metadata,
    }


def build_workflows(models: list[dict[str, Any]], tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    workflows: list[dict[str, Any]] = []
    if any(model["name"].startswith("Workflow") for model in models):
        workflows.append(
            {
                "id": "workflow:workflow_lifecycle",
                "name": "Workflow lifecycle",
                "description": "Definition, run, task, and transition flow implemented with Django models and APIs.",
                "frameworks": ["framework:django"],
            }
        )
    if any(model["name"] == "GovernancePolicy" for model in models):
        workflows.append(
            {
                "id": "workflow:governance_policy_lifecycle",
                "name": "Governance policy lifecycle",
                "description": "Draft-to-active governance policy transitions with audit tracking.",
                "frameworks": ["framework:django"],
            }
        )
    if any(task["name"] == "execute_retention_run" for task in tasks):
        workflows.append(
            {
                "id": "workflow:retention_execution",
                "name": "Retention execution",
                "description": "Retention evaluation and archive/delete execution through Celery tasks.",
                "frameworks": ["framework:django", "framework:celery"],
            }
        )
    return workflows


def build_ui_components(urlpatterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    component_map = {
        "/api/v1/ui/operations/dashboard": ("Operations Dashboard", "Dashboard summary cards for workflow, stewardship, orchestration, and agent operations."),
        "/api/v1/ui/operations/stewardship-workbench": ("Stewardship Workbench", "Workbench payload for stewardship queues, status, and allowed actions."),
        "/api/v1/ui/operations/orchestration-monitor": ("Orchestration Monitor", "UI-ready payload for orchestration workflow and run monitoring."),
        "/api/v1/ui/operations/agent-monitor": ("Agent Monitor", "UI-ready payload for agent run history and control visibility."),
    }
    components: list[dict[str, Any]] = []
    for item in urlpatterns:
        if item["path"] not in component_map:
            continue
        name, description = component_map[item["path"]]
        components.append(
            {
                "id": f"uicomponent:{slugify(name)}",
                "name": name,
                "description": description,
                "path": item["path"],
                "view": item["view"],
            }
        )
    return components


def build_nodes_and_edges(root: Path, modules: list[PythonModule], urlpatterns: list[dict[str, Any]], framework_knowledge: dict[str, dict[str, Any]], skills: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    models = extract_models(modules)
    tasks = extract_tasks(modules)
    ui_components = build_ui_components(urlpatterns)
    workflows = build_workflows(models, tasks)

    for slug, profile in framework_knowledge.items():
        nodes.append(
            make_node(
                "Framework" if profile["type"] == "Framework" else "Library",
                profile["name"],
                profile["architecture"][0],
                slug=slug if slug != "django_material" else "django_material",
                context_hub=profile["context_hub"],
                repository_fit=profile["repository_fit"],
            )
        )

    package_nodes = {
        "django-tenants": ("Framework", "Schema-per-tenant extension for Django.", "django-tenants"),
        "celery": ("Framework", "Distributed task queue used for tenant-aware background processing.", "celery"),
        "psycopg": ("Library", "PostgreSQL driver used by Django and operational scripts.", "psycopg"),
        "pika": ("Library", "RabbitMQ/AMQP client used for event publishing.", "pika"),
        "prometheus-client": ("Library", "Prometheus instrumentation library for metrics exposure.", "prometheus-client"),
        "pytest": ("Tool", "Python test runner used by repository validation.", "pytest"),
        "pytest-django": ("Tool", "Django integration plugin for pytest.", "pytest-django"),
    }
    app_root = resolve_app_root(root)
    for requirements_path in [app_root / "requirements.txt", app_root / "requirements-dev.txt"]:
        for package in parse_requirements(requirements_path):
            if package["name"] not in package_nodes:
                continue
            node_type, description, profile_key = package_nodes[package["name"]]
            nodes.append(
                make_node(
                    node_type,
                    package["name"],
                    description,
                    slug=package["name"],
                    version=package["version"],
                    context_hub=build_context_hub_entry(profile_key),
                )
            )

    for package in parse_requirements(app_root / "requirements-dev.txt"):
        classification = PACKAGE_CLASSIFICATIONS.get(package["name"], "Tool")
        if classification != "Tool":
            continue
        if package["name"] in package_nodes:
            continue
        nodes.append(
            make_node(
                "Tool",
                package["name"],
                f'Developer tool dependency pinned at version {package["version"]}.',
                version=package["version"],
            )
        )

    for tool_name, description, profile_key in [
        ("Docker Compose", "Local service orchestration for PostgreSQL and RabbitMQ.", "docker-compose"),
        ("Kubernetes", "Deployment manifests for backend, worker, ingress, and supporting services.", "kubernetes"),
        ("Helm", "Release packaging for the mtafiti-platform chart.", "helm"),
        ("GitHub Actions", "Repository CI/CD automation and drift gates.", "github-actions"),
        ("Context Hub", "External API documentation retrieval for coding agents via chub search/get.", None),
    ]:
        metadata = {}
        if profile_key:
            metadata["context_hub"] = build_context_hub_entry(profile_key)
        nodes.append(make_node("Tool", tool_name, description, **metadata))

    for service_name, description in [
        ("backend", "Django API service."),
        ("worker", "Celery worker service."),
        ("postgres", "PostgreSQL persistence service."),
        ("rabbitmq", "RabbitMQ broker service."),
    ]:
        metadata = {}
        if service_name in {"postgres", "rabbitmq"}:
            metadata["context_hub"] = build_context_hub_entry(service_name)
        nodes.append(make_node("Service", service_name, description, **metadata))

    for module in modules:
        if module.module_name.split(".")[0] not in {"config", "core", "tenants"}:
            continue
        nodes.append(
            make_node(
                "Module",
                module.module_name,
                f"Python module at {module.path.relative_to(root)}.",
                path=str(module.path.relative_to(root)),
            )
        )

    for model in models:
        nodes.append(
            make_node(
                "DataModel",
                model["name"],
                f'Django model defined in {model["module"]}.',
                fields=model["fields"],
                source=model["source"],
            )
        )

    for item in urlpatterns:
        if not item["path"].startswith("/api/v1/"):
            continue
        view = next((view for view in extract_views(modules) if view["name"] == item["view"]), None)
        nodes.append(
            make_node(
                "API",
                item["path"],
                f'API route handled by {item["view"]}.',
                slug=slugify(item["path"]),
                handler=item["view"],
                route_name=item["name"],
                methods=view["methods"] if view else [],
            )
        )

    for component in ui_components:
        nodes.append(
            make_node(
                "UIComponent",
                component["name"],
                component["description"],
                slug=component["id"].split(":", 1)[1],
                path=component["path"],
            )
        )

    for workflow in workflows:
        nodes.append(
            make_node(
                "Workflow",
                workflow["name"],
                workflow["description"],
                slug=workflow["id"].split(":", 1)[1],
            )
        )

    for skill in skills:
        nodes.append(
            make_node(
                "Skill",
                skill["name"],
                skill["description"],
                slug=skill["id"],
                inputs=skill["inputs"],
                tools=skill["tools"],
                steps=skill["steps"],
                evidence=skill["evidence"],
            )
        )

    for module in modules:
        from_id = f"module:{slugify(module.module_name)}"
        for imported in module.imports:
            base = imported.split(".")[0]
            if imported.startswith(("config", "core", "tenants")):
                edges.append(edge("uses", from_id, f"module:{slugify(imported)}"))
            elif base in IMPORT_TO_NODE:
                edges.append(edge("uses", from_id, IMPORT_TO_NODE[base]))

    for item in urlpatterns:
        if not item["path"].startswith("/api/v1/"):
            continue
        api_id = f"api:{slugify(item['path'])}"
        edges.append(edge("calls", api_id, "module:core_views"))
        view_match = next((view for view in extract_views(modules) if view["name"] == item["view"]), None)
        if view_match and view_match["ui_component"]:
            component_name = item["path"].split("/")[-1].replace("-", " ").title()
            if item["path"] == "/api/v1/ui/operations/dashboard":
                component_name = "Operations Dashboard"
            elif item["path"] == "/api/v1/ui/operations/stewardship-workbench":
                component_name = "Stewardship Workbench"
            elif item["path"] == "/api/v1/ui/operations/orchestration-monitor":
                component_name = "Orchestration Monitor"
            elif item["path"] == "/api/v1/ui/operations/agent-monitor":
                component_name = "Agent Monitor"
            edges.append(edge("implements", "module:core_views", f"uicomponent:{slugify(component_name)}"))

    for model in models:
        edges.append(edge("implements", "module:core_models", f"datamodel:{slugify(model['name'])}"))

    for workflow in workflows:
        edges.append(edge("implements", "module:core_views", workflow["id"]))
        edges.append(edge("implements", "module:core_models", workflow["id"]))
        for framework_id in workflow["frameworks"]:
            edges.append(edge("uses", workflow["id"], framework_id))

    for component in ui_components:
        component_id = component["id"]
        edges.append(edge("uses", component_id, "framework:django"))
        edges.append(edge("uses", component_id, "framework:django_material"))
        if "Dashboard" in component["name"]:
            for model_name in ["StewardshipItem", "WorkflowRun", "OrchestrationRun", "AgentRun"]:
                edges.append(edge("renders", component_id, f"datamodel:{slugify(model_name)}"))
        elif component["name"] == "Stewardship Workbench":
            edges.append(edge("renders", component_id, "datamodel:stewardshipitem"))
        elif component["name"] == "Orchestration Monitor":
            edges.append(edge("renders", component_id, "datamodel:orchestrationworkflow"))
            edges.append(edge("renders", component_id, "datamodel:orchestrationrun"))
        elif component["name"] == "Agent Monitor":
            edges.append(edge("renders", component_id, "datamodel:agentrun"))

    for skill in skills:
        skill_id = f"skill:{skill['id']}"
        for tool in skill["tools"]:
            target_slug = FRAMEWORK_ALIASES.get(tool.lower(), slugify(tool))
            target_type = "framework" if target_slug in {"django", "django-tenants", "celery", "viewflow"} else "library"
            if target_slug in {"django_material"}:
                target_type = "framework"
            edges.append(edge("uses", skill_id, f"{target_type}:{target_slug}"))
        for evidence in skill["evidence"]:
            if evidence.startswith("src/core/views.py"):
                edges.append(edge("implements", "module:core_views", skill_id))
            elif evidence.startswith("src/core/models.py"):
                edges.append(edge("implements", "module:core_models", skill_id))
            elif evidence.startswith("src/core/tasks.py"):
                edges.append(edge("implements", "module:core_tasks", skill_id))
            elif evidence.startswith("src/tenants/models.py"):
                edges.append(edge("implements", "module:tenants_models", skill_id))

    for framework_id in ["framework:django", "framework:django-tenants", "framework:celery"]:
        edges.append(edge("depends_on", framework_id, "service:postgres"))
    edges.append(edge("depends_on", "framework:celery", "service:rabbitmq"))
    edges.append(edge("depends_on", "service:backend", "service:postgres"))
    edges.append(edge("depends_on", "service:worker", "service:postgres"))
    edges.append(edge("depends_on", "service:worker", "service:rabbitmq"))

    for api in [node for node in nodes if node["type"] == "API"]:
        edges.append(edge("produces", "service:backend", api["id"]))
    edges.append(edge("configures", "tool:github_actions", "skill:define_django_json_api_endpoint"))
    for target in ["framework:django", "framework:viewflow", "framework:django_material"]:
        edges.append(edge("configures", "tool:context_hub", target))

    return dedupe(nodes, "id"), dedupe(edges, ("relationship", "from", "to"))


def edge(relationship: str, source: str, target: str) -> dict[str, str]:
    return {"relationship": relationship, "from": source, "to": target}


def dedupe(items: list[dict[str, Any]], key: str | tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[Any] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        marker = item[key] if isinstance(key, str) else tuple(item[name] for name in key)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return sorted(result, key=lambda value: json.dumps(value, sort_keys=True))


def build_ontology() -> dict[str, Any]:
    return {
        "ontology": {
            "node_types": [
                {"name": "Skill", "description": "Reusable engineering capability extracted from repository patterns or framework knowledge."},
                {"name": "Tool", "description": "External or repository tool used to build, test, deploy, or document the system."},
                {"name": "Framework", "description": "Opinionated platform or runtime framework shaping repository architecture."},
                {"name": "Library", "description": "Dependency used inside modules without owning overall application structure."},
                {"name": "API", "description": "HTTP or external integration surface."},
                {"name": "Module", "description": "Internal Python module or package implementing domain logic."},
                {"name": "UIComponent", "description": "UI-facing contract or server-rendered component surface."},
                {"name": "Workflow", "description": "Lifecycle or orchestrated process node grouping."},
                {"name": "DataModel", "description": "Persistent domain entity or data structure."},
                {"name": "Service", "description": "Deployable runtime or backing service."},
            ],
            "relationship_types": [
                {"name": "implements", "description": "An internal module or service realizes a capability, workflow, API, or skill."},
                {"name": "uses", "description": "A node directly relies on another framework, tool, module, or component."},
                {"name": "depends_on", "description": "A node requires another node to operate correctly."},
                {"name": "calls", "description": "A node invokes another node at runtime or through dispatch."},
                {"name": "produces", "description": "A service or tool emits an output, contract, or artifact."},
                {"name": "consumes", "description": "A node accepts or reads another node as input."},
                {"name": "renders", "description": "A UI component or API presents a model or aggregated data shape."},
                {"name": "extends", "description": "A framework or module builds on the contract of another node."},
                {"name": "configures", "description": "A tool or module configures or enriches another node."},
            ],
            "query_examples": QUERY_EXAMPLES,
        }
    }


def build_bundle(root: Path) -> dict[str, Any]:
    app_root = resolve_app_root(root)
    modules = collect_python_modules(app_root)
    urlpatterns = extract_urlpatterns(app_root / "config" / "urls.py")
    settings = extract_settings(app_root / "config" / "settings.py")
    framework_knowledge = build_framework_knowledge(root, settings)
    models = extract_models(modules)
    tasks = extract_tasks(modules)
    skills = build_skills(models, tasks, urlpatterns)
    nodes, edges = build_nodes_and_edges(root, modules, urlpatterns, framework_knowledge, skills)

    return {
        "analysis/environment_inventory.yaml": build_environment_inventory(root, modules, urlpatterns, settings),
        "knowledge_graph/ontology.yaml": build_ontology(),
        "knowledge_graph/nodes.yaml": {"nodes": nodes},
        "knowledge_graph/edges.yaml": {"edges": edges},
        "skills/generated_skills.yaml": {"skills": skills},
        "framework_knowledge/django.yaml": framework_knowledge["django"],
        "framework_knowledge/viewflow.yaml": framework_knowledge["viewflow"],
        "framework_knowledge/django_material.yaml": framework_knowledge["django_material"],
    }


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if value == "":
            return '""'
        if "\n" in value:
            return json.dumps(value)
        if re.fullmatch(r"[A-Za-z0-9_./:{}@+-]+", value):
            return value
        return json.dumps(value)
    raise TypeError(f"Unsupported YAML scalar: {type(value)!r}")


def dump_yaml(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines: list[str] = []
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(dump_yaml(child, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(child)}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{prefix}[]"
        lines = []
        for child in value:
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(dump_yaml(child, indent + 2))
            else:
                lines.append(f"{prefix}- {yaml_scalar(child)}")
        return "\n".join(lines)
    return f"{prefix}{yaml_scalar(value)}"


def write_bundle(root: Path, bundle: dict[str, Any]) -> None:
    for relative_path, payload in bundle.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump_yaml(payload) + "\n", encoding="utf-8")


def check_bundle(root: Path, bundle: dict[str, Any]) -> list[str]:
    drifted: list[str] = []
    for relative_path, payload in bundle.items():
        path = root / relative_path
        expected = dump_yaml(payload) + "\n"
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != expected:
            drifted.append(relative_path)
    return drifted


def query_nodes(root: Path, node_type: str | None = None, text: str | None = None, relationship: str | None = None, target: str | None = None) -> list[dict[str, Any]]:
    bundle = build_bundle(root)
    nodes = bundle["knowledge_graph/nodes.yaml"]["nodes"]
    edges = bundle["knowledge_graph/edges.yaml"]["edges"]
    candidates = nodes
    if node_type:
        candidates = [node for node in candidates if node["type"].lower() == node_type.lower()]
    if text:
        lowered = text.lower()
        candidates = [
            node
            for node in candidates
            if lowered in json.dumps(node, sort_keys=True).lower()
        ]
    if relationship and target:
        related = {
            edge["from"]
            for edge in edges
            if edge["relationship"] == relationship and edge["to"] == target
        }
        candidates = [node for node in candidates if node["id"] in related]
    return candidates


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    return parser
