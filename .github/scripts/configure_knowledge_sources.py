#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import date
from pathlib import Path


COMMUNITY_SOURCE = {"name": "community", "url": "https://cdn.aichub.org/v1"}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def detect_version(repo_dir: Path, readme_text: str) -> str | None:
    package_json = repo_dir / "package.json"
    if package_json.exists():
        try:
            payload = json.loads(read_text(package_json))
        except json.JSONDecodeError:
            payload = {}
        version = payload.get("version")
        if isinstance(version, str) and version.strip():
            return version.strip()

    pyproject = repo_dir / "pyproject.toml"
    if pyproject.exists():
        text = read_text(pyproject)
        match = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()

    readme_match = re.search(r"^##\s+(\d+\.\d+\.\d+)\b", readme_text, flags=re.MULTILINE)
    if readme_match:
        return readme_match.group(1)

    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_dir), "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode == 0 and completed.stdout.strip():
        return completed.stdout.strip().lstrip("v")
    return None


def detect_language(repo_name: str, readme_text: str) -> str:
    lowered = f"{repo_name}\n{readme_text}".lower()
    if "javascript" in lowered or "node.js" in lowered or "typescript" in lowered:
        return "javascript"
    return "python"


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def build_doc(repo_name: str, readme_text: str, version: str, language: str) -> str:
    today = date.today().isoformat()
    description = f"Local knowledge source generated from the {repo_name} repository README."
    tags = ",".join(filter(None, [repo_name, "local", "knowledge-src", "framework"]))
    frontmatter = "\n".join(
        [
            "---",
            f"name: {repo_name}",
            f"description: {yaml_quote(description)}",
            "metadata:",
            f'  languages: "{language}"',
            f'  versions: "{version}"',
            "  revision: 1",
            f'  updated-on: "{today}"',
            "  source: maintainer",
            f'  tags: "{tags}"',
            "---",
            "",
        ]
    )
    return frontmatter + readme_text.strip() + "\n"


def build_skill(repo_name: str, readme_text: str) -> str:
    today = date.today().isoformat()
    description = f"Local knowledge source skill generated from the {repo_name} repository README."
    tags = ",".join(filter(None, [repo_name, "local", "knowledge-src", "skill"]))
    frontmatter = "\n".join(
        [
            "---",
            f"name: {repo_name}",
            f"description: {yaml_quote(description)}",
            "metadata:",
            "  revision: 1",
            f'  updated-on: "{today}"',
            "  source: community",
            f'  tags: "{tags}"',
            "---",
            "",
        ]
    )
    return frontmatter + readme_text.strip() + "\n"


def read_if_exists(path: Path) -> str:
    return read_text(path) if path.exists() else ""


def detect_fence(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".html": "django",
        ".css": "css",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
    }.get(suffix, "")


def read_snippet(path: Path, start_line: int | None = None, end_line: int | None = None) -> str:
    if not path.exists():
        return ""
    text = read_text(path)
    if start_line is None and end_line is None:
        return text.strip()

    lines = text.splitlines()
    start = max((start_line or 1) - 1, 0)
    if start >= len(lines):
        start = 0
    end = min(end_line or len(lines), len(lines))
    if end <= start:
        end = len(lines)
    return "\n".join(lines[start:end]).strip()


def render_source_snippet(
    source_root: Path,
    relative_path: str,
    *,
    start_line: int | None = None,
    end_line: int | None = None,
    label: str | None = None,
) -> str:
    path = source_root / relative_path
    snippet = read_snippet(path, start_line=start_line, end_line=end_line)
    if not snippet:
        return ""
    fence = detect_fence(path)
    rendered = [f"Source: `{relative_path}`"]
    if label:
        rendered.insert(0, f"### {label}")
    rendered.append(f"```{fence}".rstrip())
    rendered.append(snippet)
    rendered.append("```")
    return "\n\n".join(rendered)


def build_section_content(source_root: Path, section_spec: dict[str, object]) -> str:
    parts: list[str] = []
    body = section_spec.get("body")
    if isinstance(body, str) and body.strip():
        parts.append(body.strip())

    for source in section_spec.get("sources", []):
        if not isinstance(source, dict):
            continue
        rendered = render_source_snippet(
            source_root,
            str(source["path"]),
            start_line=source.get("start_line"),
            end_line=source.get("end_line"),
            label=source.get("label"),
        )
        if rendered:
            parts.append(rendered)
    return "\n\n".join(parts).strip()


def build_composite_skill(name: str, description: str, sections: list[tuple[str, str]], tags: list[str]) -> str:
    today = date.today().isoformat()
    frontmatter = "\n".join(
        [
            "---",
            f"name: {name}",
            f"description: {yaml_quote(description)}",
            "metadata:",
            "  revision: 1",
            f'  updated-on: "{today}"',
            "  source: community",
            f'  tags: "{",".join(tags)}"',
            "---",
            "",
        ]
    )
    body_parts = []
    for title, content in sections:
        cleaned = content.strip()
        if not cleaned:
            continue
        body_parts.append(f"## {title}\n\n{cleaned}")
    return frontmatter + "\n\n".join(body_parts).strip() + "\n"


def generate_cookbook_entries(source_root: Path, content_root: Path) -> list[dict[str, str]]:
    generated: list[dict[str, str]] = []
    cookbook_root = source_root / "cookbook"
    if not cookbook_root.exists():
        return generated

    entries_root = content_root / "knowledge-src" / "skills"
    ignored = {".git", "__pycache__", "locale"}
    for sample_dir in sorted(
        path
        for path in cookbook_root.iterdir()
        if path.is_dir() and path.name not in ignored and not path.name.startswith(".")
    ):
        sections: list[tuple[str, str]] = []
        readme = sample_dir / "README.md"
        if readme.exists():
            sections.append(("Overview", read_text(readme)))
        sampled_files = collect_representative_files(sample_dir)
        for file_path in sampled_files:
            title = str(file_path.relative_to(sample_dir))
            sections.append((title, read_text(file_path)))
        if not sections:
            continue
        target = entries_root / f"cookbook-{slugify(sample_dir.name)}" / "SKILL.md"
        write_text(
            target,
            build_composite_skill(
                name=f"cookbook-{slugify(sample_dir.name)}",
                description=f"Local cookbook sample for {sample_dir.name} generated from the Viewflow cookbook repository.",
                sections=sections,
                tags=["cookbook", sample_dir.name, "local", "knowledge-src", "viewflow"],
            ),
        )
        generated.append(
            {
                "repo": f"cookbook/{sample_dir.name}",
                "entry_type": "skill",
                "entry_id": f"knowledge-src/cookbook-{slugify(sample_dir.name)}",
            }
        )
    return generated


def collect_representative_files(sample_dir: Path) -> list[Path]:
    priority_names = [
        "config/urls.py",
        "config/settings.py",
        "manage.py",
        "atlas/viewset.py",
        "atlas/viewsets.py",
    ]
    collected: list[Path] = []
    for relative in priority_names:
        path = sample_dir / relative
        if path.exists():
            collected.append(path)

    patterns = [
        "**/urls.py",
        "**/viewset.py",
        "**/viewsets.py",
        "**/views.py",
        "**/forms.py",
        "**/models.py",
        "**/*.css",
        "**/README.md",
    ]
    for pattern in patterns:
        for path in sorted(sample_dir.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(sample_dir)
            if any(part.startswith(".") for part in rel.parts):
                continue
            if "migrations" in rel.parts or "__pycache__" in rel.parts or path in collected:
                continue
            collected.append(path)
            if len(collected) >= 12:
                return collected
    return collected[:12]


def generate_django_material_entries(source_root: Path, content_root: Path) -> list[dict[str, str]]:
    generated: list[dict[str, str]] = []
    material_root = source_root / "django-material"
    if not material_root.exists():
        return generated

    colors = material_root / "material" / "assets" / "colors.css"
    if colors.exists():
        target = content_root / "knowledge-src" / "skills" / "django-material-theme-customization" / "SKILL.md"
        write_text(
            target,
            build_composite_skill(
                name="django-material-theme-customization",
                description="Local theming skill generated from django-material design token sources.",
                sections=[
                    ("Theme customization guidance", read_text(material_root / "README.md")),
                    ("Color token file", read_text(colors)),
                ],
                tags=["django-material", "theme", "colors", "design-tokens", "local", "knowledge-src"],
            ),
        )
        generated.append(
            {
                "repo": "django-material/theme",
                "entry_type": "skill",
                "entry_id": "knowledge-src/django-material-theme-customization",
            }
        )
    return generated


def generate_admin_shell_skill_entries(source_root: Path, content_root: Path) -> list[dict[str, str]]:
    generated: list[dict[str, str]] = []
    cookbook_root = source_root / "cookbook" / "crud101"
    material_root = source_root / "django-material"
    if not cookbook_root.exists():
        return generated

    layout_contract = """
Use an admin-style CRUD shell with four core regions:

1. Sidebar navigation for application sections.
2. Top navigation bar above the content area.
3. Main content region for dashboards, tables, and forms.
4. Optional floating action button anchored at the bottom-right of the content viewport for primary actions such as add, create, or start.

Place the top navigation as the first visible row in the main content shell, not below summary cards or page-specific sections. Support two topbar variants: an inset variant that sits inside padded content, and a flush variant that touches only the top edge of the content area while preserving a visible gap between the sidebar and the content column. Add a compact user/account component near the top of the sidebar with avatar, user identity, tenant, and role context. Sidebar behavior should minimize to a compact rail instead of disappearing completely. Keep application access visible with compact icons or short labels even when collapsed. The top bar should include the sidebar toggle on the left and utility actions such as notifications, quick links, or activity on the far right.

Use icon-first utility actions in the top bar, including the sidebar toggle and notifications, with text fallback labels when needed. The sidebar toggle should render as a single Material hamburger menu icon rather than exposing open/collapse state text in the visible UI. Include an account action dropdown on the far right for actions such as profile, password change, and logout.

When a floating action button is present, prefer an icon-first circular button. Choose a Material icon that matches the action context (for example `print` for printing, `note_add` for templates/documents, or another domain-specific action icon). Add a hover/focus tooltip that names the action, and provide an accessible text fallback through the label if an icon is unavailable or cannot be rendered.
""".strip()

    implementation_lessons = """
- Put global shell controls in the top bar before page-specific panels so they read as application chrome.
- Treat sidebar identity as part of navigation chrome rather than body content.
- Prefer Google Material icons because cookbook CRUD and dashboard samples consistently use Material icon names such as `location_city`, `terrain`, `group_work`, `timeline`, and `notifications`.
- Pair cookbook-style colors like `primary_color="#3949ab"` and `secondary_color="#5c6bc0"` with lighter surface containers for admin shells.
- Use icon-first Material controls plus text fallback for shell controls and utility actions.
- Keep the sidebar toggle visually icon-only and reserve text fallback for accessibility rather than visible state labels.
- Reserve the far-right top-bar area for account and session actions via a dropdown menu.
- Make the floating primary action context-sensitive by matching its Material icon to the domain action instead of always using a generic add icon.
""".strip()

    icon_and_color_guidance = """
- Follow cookbook CRUD and dashboard icon naming patterns by using Google Material icon identifiers directly.
- Reuse strong indigo/blue shell colors from cookbook `Site(...)` examples (`#3949ab`, `#5c6bc0`) and lighter blue container tones from django-material theme tokens.
- Navigation items, notifications, account actions, and floating action buttons should all prefer Material icons with accessible text fallback labels.
- Choose between inset and flush topbar variants based on whether the shell should float within content padding or only connect to the top edge while keeping sidebar/content spacing intact.
- For floating primary actions, prefer semantic icons such as `print`, `note_add`, or other task-specific Material icons instead of a single generic plus icon.
""".strip()

    sections: list[tuple[str, str]] = [
        ("Admin shell layout contract", layout_contract),
        ("Implementation lessons", implementation_lessons),
        ("Icon and color guidance", icon_and_color_guidance),
    ]

    crud_readme = cookbook_root / "README.md"
    if crud_readme.exists():
        sections.append(("CRUD 101 overview", read_text(crud_readme)))
    crud_urls = cookbook_root / "config" / "urls.py"
    if crud_urls.exists():
        sections.append(("Site and application shell example", read_text(crud_urls)))
    crud_viewset = cookbook_root / "atlas" / "viewset.py"
    if crud_viewset.exists():
        sections.append(("Application viewset example", read_text(crud_viewset)))

    colors = material_root / "material" / "assets" / "colors.css"
    if colors.exists():
        sections.append(("Blue theme token reference", read_text(colors)))

    target = content_root / "knowledge-src" / "skills" / "crud-admin-shell-layout" / "SKILL.md"
    write_text(
        target,
        build_composite_skill(
            name="crud-admin-shell-layout",
            description="Opinionated admin CRUD shell guidance derived from cookbook CRUD samples and django-material theme tokens.",
            sections=sections,
            tags=["crud", "admin", "shell", "sidebar", "topbar", "fab", "local", "knowledge-src", "viewflow"],
        ),
    )
    generated.append(
        {
            "repo": "cookbook/crud101-admin-shell",
            "entry_type": "skill",
            "entry_id": "knowledge-src/crud-admin-shell-layout",
        }
    )
    return generated


def generate_domain_skill_entries(source_root: Path, content_root: Path) -> list[dict[str, str]]:
    generated: list[dict[str, str]] = []
    entries_root = content_root / "knowledge-src" / "skills"

    domain_specs = [
        {
            "entry_id": "knowledge-src/viewflow-workflow-orchestration",
            "name": "viewflow-workflow-orchestration",
            "description": "Workflow architecture, APIs, and cookbook patterns for building user and programmatic orchestrations with Viewflow.",
            "tags": [
                "viewflow",
                "workflow",
                "orchestration",
                "flow",
                "application",
                "local",
                "knowledge-src",
            ],
            "requires": ["viewflow/README.md"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Model workflow state with a `Process` subclass or proxy and keep business data on the process.
- Define orchestration in a `flow.Flow` class, not scattered across ad hoc views or templates.
- Prefer built-in flow nodes (`Start`, `StartHandle`, `View`, `If`, `Split`, `Join`, `End`) and connect them with `.Next(...)`, `.Then(...)`, and `.Else(...)`.
- Use `FlowViewset` or `FlowAppViewset` inside `Application`/`Site` scaffolding so workflows plug into navigation, permissions, inbox, and dashboard chrome.
- Treat task titles, descriptions, summaries, permissions, and assignment rules as flow metadata instead of hard-coded UI behavior.
""".strip(),
                },
                {
                    "title": "Quickstart and registration",
                    "sources": [
                        {"path": "viewflow/README.md", "start_line": 55, "end_line": 143, "label": "README quickstart"},
                        {
                            "path": "viewflow/viewflow/urls/sites.py",
                            "start_line": 48,
                            "end_line": 175,
                            "label": "Site and Application registration",
                        },
                        {
                            "path": "viewflow/tests/workflow/test_flow_viewset__workflow.py",
                            "start_line": 58,
                            "end_line": 80,
                            "label": "Workflow app viewset registration",
                        },
                    ],
                },
                {
                    "title": "Node API surface",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/workflow/base.py",
                            "start_line": 71,
                            "end_line": 220,
                            "label": "Base node contract",
                        },
                        {
                            "path": "viewflow/viewflow/workflow/flow/nodes.py",
                            "start_line": 8,
                            "end_line": 228,
                            "label": "Flow node classes",
                        },
                        {
                            "path": "viewflow/viewflow/workflow/flow/nodes.py",
                            "start_line": 309,
                            "end_line": 360,
                            "label": "Split and Join nodes",
                        },
                    ],
                },
                {
                    "title": "Activation lifecycle and permissions",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/workflow/activation.py",
                            "start_line": 79,
                            "end_line": 220,
                            "label": "Activation lifecycle",
                        },
                        {
                            "path": "viewflow/tests/workflow/test_managers_perms.py",
                            "start_line": 27,
                            "end_line": 60,
                            "label": "Flow visibility and task permission examples",
                        },
                    ],
                },
                {
                    "title": "Cookbook orchestration example",
                    "sources": [
                        {
                            "path": "cookbook/workflow101/shipment/flows.py",
                            "start_line": 10,
                            "end_line": 146,
                            "label": "Shipment flow with split, if, join, assignment, and permissions",
                        },
                        {
                            "path": "cookbook/patterns/config/urls.py",
                            "start_line": 21,
                            "end_line": 70,
                            "label": "Workflow pattern catalog",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/viewflow-fsm-state-transitions",
            "name": "viewflow-fsm-state-transitions",
            "description": "State transition architecture, permission checks, and viewset integration for Viewflow FSM flows.",
            "tags": [
                "viewflow",
                "fsm",
                "state-machine",
                "transition",
                "permissions",
                "local",
                "knowledge-src",
            ],
            "requires": ["viewflow/viewflow/fsm/base.py"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Put lifecycle rules on a `State(...)` field and define transitions on methods with `@state.transition(...)`.
- Keep transition conditions and permission logic close to the transition declaration so agents can reason about allowed state changes without scanning unrelated code.
- Use `FlowViewsMixin` on CRUD/detail viewsets when a model should expose user-triggered transition actions through the UI.
- Prefer transition-specific fields from `get_transition_fields(...)` instead of overloading generic update forms.
""".strip(),
                },
                {
                    "title": "Core FSM API",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/fsm/base.py",
                            "start_line": 30,
                            "end_line": 236,
                            "label": "Transition, conditions, and bound method behavior",
                        },
                        {
                            "path": "viewflow/viewflow/fsm/viewset.py",
                            "start_line": 23,
                            "end_line": 167,
                            "label": "FlowViewsMixin and transition routes",
                        },
                    ],
                },
                {
                    "title": "Cookbook FSM integration",
                    "sources": [
                        {
                            "path": "cookbook/fsm101/review/viewset.py",
                            "start_line": 22,
                            "end_line": 105,
                            "label": "Readonly model viewset with FlowViewsMixin",
                        },
                    ],
                },
                {
                    "title": "Permission example",
                    "sources": [
                        {
                            "path": "viewflow/tests/fsm/test_fsm__permissions.py",
                            "start_line": 10,
                            "end_line": 46,
                            "label": "Transition permission callable example",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/django-material-frontend-composition",
            "name": "django-material-frontend-composition",
            "description": "Component-first frontend and form-composition guidance for django-material with minimal custom templates.",
            "tags": [
                "django-material",
                "frontend",
                "forms",
                "layout",
                "components",
                "local",
                "knowledge-src",
            ],
            "requires": ["django-material/README.md"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Extend `material/base.html` or `material/base_page.html` first; only add custom templates when you truly need to redefine behavior.
- Prefer cotton components (`<c-button>`, `<c-card>`, `<c-nav.item>`) and `{% render form form.layout %}` over hand-built HTML form markup.
- Put structure in `Layout`, `Row`, `Column`, `FieldSet`, and `Span` objects so UI remains composable and predictable for both humans and agents.
- When a view provides `view.layout`, let it override `form.layout`; this keeps behavior configurable from view/viewset APIs instead of template forks.
""".strip(),
                },
                {
                    "title": "Rapid agentic UI metadata",
                    "body": """
- CRUD page recipe: register a `ModelViewset`, configure `list_columns` and `form_layout`, mount it into an `Application`, and let `Site(...)` supply navigation and shell chrome.
- Workflow page recipe: keep workflow-specific forms in `StartView`/`UpdateView` classes or workflow task views and reuse `viewflow/workflow/start.html` or `viewflow/workflow/task.html` rather than inventing a new shell.
- Field recipe: prefer outlined text/select patterns with floating labels, placeholder-free inputs, help text, and explicit error state wiring.
- Primary action recipe: use filled buttons for main submit actions and icon FABs for context-specific creation/launch actions.
- Card recipe: use elevated cards with title, subtitle, content slot, and footer slot to package forms and table sections.
- Theme recipe: prefer blue `primary` tokens, `surface`/`surface-container-*` backgrounds, and `on-surface-variant` text for supporting labels and hints.
""".strip(),
                },
                {
                    "title": "Component and base-template primitives",
                    "sources": [
                        {"path": "django-material/README.md", "start_line": 23, "end_line": 62, "label": "README usage and base template"},
                        {
                            "path": "django-material/material/templates/cotton/CLAUDE.md",
                            "start_line": 1,
                            "end_line": 220,
                            "label": "Cotton component and accessibility guidance",
                        },
                        {
                            "path": "django-material/demo/templates/demo/showcases.html",
                            "start_line": 1,
                            "end_line": 40,
                            "label": "Showcase page composition",
                        },
                        {
                            "path": "django-material/demo/templates/demo/widgets.html",
                            "start_line": 1,
                            "end_line": 31,
                            "label": "Widget page composition",
                        },
                    ],
                },
                {
                    "title": "Component recipes",
                    "sources": [
                        {
                            "path": "django-material/material/templates/cotton/forms/text/outlined.html",
                            "start_line": 1,
                            "end_line": 85,
                            "label": "Outlined text field component",
                        },
                        {
                            "path": "django-material/material/templates/cotton/forms/select/outlined.html",
                            "start_line": 1,
                            "end_line": 97,
                            "label": "Outlined select component",
                        },
                        {
                            "path": "django-material/material/templates/cotton/button/filled.html",
                            "start_line": 1,
                            "end_line": 18,
                            "label": "Filled primary button component",
                        },
                        {
                            "path": "django-material/material/templates/cotton/button/fab.html",
                            "start_line": 1,
                            "end_line": 43,
                            "label": "Floating action button component",
                        },
                        {
                            "path": "django-material/material/templates/cotton/card/elevated.html",
                            "start_line": 1,
                            "end_line": 35,
                            "label": "Elevated card component",
                        },
                    ],
                },
                {
                    "title": "Layout API",
                    "sources": [
                        {
                            "path": "django-material/tests/test_views_base.py",
                            "start_line": 1,
                            "end_line": 166,
                            "label": "Layout, Row, Column, FieldSet, Span, Action, and BulkActionForm tests",
                        },
                    ],
                },
                {
                    "title": "Create/update form behavior",
                    "sources": [
                        {
                            "path": "django-material/tests/test_views_create.py",
                            "start_line": 10,
                            "end_line": 259,
                            "label": "CreateModelView form-class, widgets, template, and success-url behavior",
                        },
                    ],
                },
                {
                    "title": "Cookbook page examples",
                    "sources": [
                        {
                            "path": "cookbook/crud101/atlas/viewset.py",
                            "start_line": 17,
                            "end_line": 101,
                            "label": "CRUD viewset configuration with icons and layouts",
                        },
                        {
                            "path": "cookbook/workflow101/shipment/views.py",
                            "start_line": 1,
                            "end_line": 50,
                            "label": "Workflow task views using built-in workflow templates",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/viewflow-forms-layout-composition",
            "name": "viewflow-forms-layout-composition",
            "description": "Layout-driven form composition with Viewflow forms and cookbook examples.",
            "tags": [
                "viewflow",
                "forms",
                "layout",
                "fieldset",
                "responsive-grid",
                "local",
                "knowledge-src",
            ],
            "requires": ["viewflow/viewflow/forms/renderers.py"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Build complex forms with `Layout`, `FieldSet`, `Row`, `Column`, and `Span` instead of custom HTML tables or div grids.
- Keep form structure declarative on the form or viewset so create/update screens can reuse the same composition logic.
- Use responsive span sizing when field density matters; use `FieldSet` for semantic grouping and readable forms.
- Prefer widget configuration and layout composition over per-form template overrides.
""".strip(),
                },
                {
                    "title": "Renderer and widget foundations",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/forms/renderers.py",
                            "start_line": 31,
                            "end_line": 235,
                            "label": "Widget renderers and field metadata propagation",
                        },
                    ],
                },
                {
                    "title": "Cookbook layout example",
                    "sources": [
                        {
                            "path": "cookbook/forms101/forms/bank_form.py",
                            "start_line": 1,
                            "end_line": 193,
                            "label": "Large multi-section bank form with FieldSet, Row, Column, and Span",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/viewflow-crud-scaffolding",
            "name": "viewflow-crud-scaffolding",
            "description": "Scaffold-first CRUD composition with Site, Application, ModelViewset, and layout-driven forms.",
            "tags": [
                "viewflow",
                "crud",
                "site",
                "application",
                "modelviewset",
                "local",
                "knowledge-src",
            ],
            "requires": ["viewflow/viewflow/urls/model.py", "viewflow/viewflow/urls/sites.py"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Package CRUD modules as `ModelViewset` or `ReadonlyModelViewset` instances and mount them inside `Application(...)`.
- Add `Application(...)` instances to a top-level `Site(...)` to get navigation, theme colors, URL scoping, and menu generation.
- Keep form customization in `form_layout`, `create_form_class`, `update_form_class`, `form_widgets`, filters, and list configuration before reaching for custom templates.
- Define extra object routes on the viewset via `urlpatterns` when behavior truly needs bespoke endpoints.
""".strip(),
                },
                {
                    "title": "Site and application APIs",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/urls/sites.py",
                            "start_line": 16,
                            "end_line": 175,
                            "label": "AppMenuMixin, Application, and Site",
                        },
                        {
                            "path": "cookbook/crud101/config/urls.py",
                            "start_line": 1,
                            "end_line": 32,
                            "label": "Cookbook Site/Application assembly",
                        },
                    ],
                },
                {
                    "title": "ModelViewset API",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/urls/model.py",
                            "start_line": 24,
                            "end_line": 220,
                            "label": "BaseModelViewset, CreateViewMixin, UpdateViewMixin, and ModelViewset",
                        },
                    ],
                },
                {
                    "title": "Cookbook CRUD examples",
                    "sources": [
                        {
                            "path": "cookbook/crud101/staff/viewset.py",
                            "start_line": 1,
                            "end_line": 88,
                            "label": "Employee and department CRUD viewsets",
                        },
                        {
                            "path": "cookbook/crud101/atlas/viewset.py",
                            "label": "Atlas CRUD example",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/viewflow-auth-account-scaffolding",
            "name": "viewflow-auth-account-scaffolding",
            "description": "Authentication, login form, and profile/account scaffolding guidance for Viewflow applications.",
            "tags": [
                "viewflow",
                "auth",
                "accounts",
                "profile",
                "login",
                "local",
                "knowledge-src",
            ],
            "requires": ["viewflow/viewflow/contrib/auth.py"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Register `AuthViewset()` in URL configuration instead of wiring every auth route manually.
- Customize authentication UX through `AuthenticationForm` widget attributes and `AuthViewset` configuration before forking auth templates.
- Treat profile rendering and avatar upload as account-scaffolding concerns, not page-specific business logic.
- Keep account management in the shared site shell so auth, profile, and password management remain consistent across apps.
""".strip(),
                },
                {
                    "title": "AuthViewset and profile APIs",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/contrib/auth.py",
                            "start_line": 32,
                            "end_line": 220,
                            "label": "AuthenticationForm, ProfileView, avatar helpers, and AuthViewset",
                        },
                        {
                            "path": "viewflow/README.md",
                            "start_line": 112,
                            "end_line": 135,
                            "label": "AuthViewset site registration example",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/viewflow-dashboard-composition",
            "name": "viewflow-dashboard-composition",
            "description": "Dashboard composition guidance using cookbook dashboard samples, Material icons, and Viewflow site shells.",
            "tags": [
                "viewflow",
                "dashboard",
                "material",
                "plotly",
                "icons",
                "local",
                "knowledge-src",
            ],
            "requires": ["cookbook/dashboard/config/urls.py"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Treat dashboards as first-class apps inside `Application(...)`/`Site(...)`, not isolated pages with their own shell conventions.
- Reuse Material icon names and cookbook indigo colors so dashboards visually align with CRUD and workflow apps.
- Prefer grid/card composition for metrics, filters, and charts; make filters explicit and colocated with the dashboard layout.
""".strip(),
                },
                {
                    "title": "Cookbook dashboard shell",
                    "sources": [
                        {
                            "path": "cookbook/dashboard/config/urls.py",
                            "start_line": 1,
                            "end_line": 32,
                            "label": "Dashboard site registration and colors",
                        },
                    ],
                },
                {
                    "title": "Dashboard layout and widget example",
                    "sources": [
                        {
                            "path": "cookbook/dashboard/oilngas/dashboard.py",
                            "start_line": 1,
                            "end_line": 220,
                            "label": "Material cards, page grid, filters, and dashboard callbacks",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/knowledge-source-maintenance",
            "name": "knowledge-source-maintenance",
            "description": "How to extend and refresh the local knowledge-src skillset without reworking the generator from scratch.",
            "tags": [
                "knowledge-src",
                "maintenance",
                "workflow",
                "generator",
                "local",
                "skills",
            ],
            "requires": [],
            "sections": [
                {
                    "title": "Update workflow",
                    "body": """
- The local skill generator is intentionally domain-spec driven. Add or refine domain skills in `.github/scripts/configure_knowledge_sources.py` by editing the `domain_specs` list inside `generate_domain_skill_entries(...)`.
- Each domain skill should define: `entry_id`, `name`, `description`, `tags`, optional `requires`, and ordered `sections`.
- Each section can include prose in `body` plus curated source excerpts in `sources` with `path`, `label`, `start_line`, and `end_line`.
- Prefer a small number of high-signal source snippets that teach architecture, API shape, and composition conventions over dumping entire repositories.
- When the framework provides composable APIs, capture those APIs first and document template overrides only as exceptions.
""".strip(),
                },
                {
                    "title": "Refresh commands",
                    "body": """
Run the generator and rebuild the local Context Hub bundle after changing the curated specs:

```bash
python3 .github/scripts/configure_knowledge_sources.py --source-root /home/jmduda/KodeX.2026/knowledge-src
chub update
```

Then verify the new or updated entries with:

```bash
chub search workflow
chub get knowledge-src/viewflow-crud-scaffolding
```
""".strip(),
                },
            ],
        },
    ]

    for spec in domain_specs:
        required_paths = [source_root / relative for relative in spec["requires"]]
        if required_paths and not all(path.exists() for path in required_paths):
            continue

        sections: list[tuple[str, str]] = []
        for section_spec in spec["sections"]:
            content = build_section_content(source_root, section_spec)
            if content:
                sections.append((section_spec["title"], content))

        if not sections:
            continue

        target = entries_root / spec["name"] / "SKILL.md"
        write_text(
            target,
            build_composite_skill(
                name=spec["name"],
                description=spec["description"],
                sections=sections,
                tags=spec["tags"],
            ),
        )
        generated.append(
            {
                "repo": spec["name"],
                "entry_type": "skill",
                "entry_id": spec["entry_id"],
            }
        )

    return generated


def iter_repo_dirs(source_root: Path) -> list[Path]:
    return sorted(
        path
        for path in source_root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def generate_content(source_root: Path, content_root: Path) -> list[dict[str, str]]:
    generated: list[dict[str, str]] = []
    author_root = content_root / "knowledge-src"
    for repo_dir in iter_repo_dirs(source_root):
        readme = repo_dir / "README.md"
        if not readme.exists():
            continue
        readme_text = read_text(readme)
        repo_name = slugify(repo_dir.name)
        version = detect_version(repo_dir, readme_text)
        if version:
            language = detect_language(repo_name, readme_text)
            target = author_root / "docs" / repo_name / "DOC.md"
            write_text(target, build_doc(repo_name, readme_text, version, language))
            generated.append({"repo": repo_dir.name, "entry_type": "doc", "entry_id": f"knowledge-src/{repo_name}"})
        else:
            target = author_root / "skills" / repo_name / "SKILL.md"
            write_text(target, build_skill(repo_name, readme_text))
            generated.append({"repo": repo_dir.name, "entry_type": "skill", "entry_id": f"knowledge-src/{repo_name}"})
    generated.extend(generate_cookbook_entries(source_root, content_root))
    generated.extend(generate_django_material_entries(source_root, content_root))
    generated.extend(generate_admin_shell_skill_entries(source_root, content_root))
    generated.extend(generate_domain_skill_entries(source_root, content_root))
    return generated


def run_chub_build(content_root: Path, dist_root: Path) -> None:
    subprocess.run(
        ["chub", "build", str(content_root), "-o", str(dist_root)],
        check=True,
        capture_output=True,
        text=True,
    )


def write_chub_config(dist_root: Path, config_path: Path) -> None:
    config = "\n".join(
        [
            "sources:",
            f"  - name: {COMMUNITY_SOURCE['name']}",
            f"    url: {COMMUNITY_SOURCE['url']}",
            "  - name: knowledge-src",
            f"    path: {dist_root}",
            'source: "official,maintainer,community"',
            "refresh_interval: 86400",
            "telemetry: false",
            "",
        ]
    )
    write_text(config_path, config)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, help="Directory containing cloned knowledge repositories.")
    parser.add_argument("--content-root", help="Generated Context Hub content root. Defaults to <source-root>/.chub/content")
    parser.add_argument("--dist-root", help="Built Context Hub dist root. Defaults to <source-root>/.chub/dist")
    parser.add_argument("--config-path", help="chub config file path. Defaults to ~/.chub/config.yaml")
    args = parser.parse_args()

    source_root = Path(args.source_root).expanduser().resolve()
    content_root = Path(args.content_root).expanduser().resolve() if args.content_root else source_root / ".chub" / "content"
    dist_root = Path(args.dist_root).expanduser().resolve() if args.dist_root else source_root / ".chub" / "dist"
    config_path = Path(args.config_path).expanduser().resolve() if args.config_path else Path.home() / ".chub" / "config.yaml"

    generated = generate_content(source_root, content_root)
    run_chub_build(content_root, dist_root)
    write_chub_config(dist_root, config_path)

    print(json.dumps({"generated": generated, "content_root": str(content_root), "dist_root": str(dist_root), "config_path": str(config_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
