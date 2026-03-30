#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import date
from pathlib import Path

COMMUNITY_SOURCE = {"name": "community", "url": "https://cdn.aichub.org/v1"}
FRAMEWORK_STACK_MANIFEST = {
    "repositories": [
        {
            "name": "viewflow",
            "clone": "git@github.com:viewflow/viewflow.git",
            "type": "source",
        },
        {
            "name": "django-material",
            "clone": "git@github.com:viewflow/django-material.git",
            "type": "source",
        },
        {
            "name": "cookbook",
            "clone": "git@github.com:viewflow/cookbook.git",
            "type": "source",
        },
    ],
    "behavioral_sources": [
        {
            "name": "viewflow-demo-site",
            "url": "https://demo.viewflow.io/",
            "type": "demo-site",
            "frameworks": ["viewflow", "django-material"],
            "capture_seed_paths": ["/"],
            "same_origin_only": True,
            "max_capture_pages": 25,
            "preferred_capture_mode": "http",
            "browser_dump_commands": [
                "chromium --headless --dump-dom {url}",
                "google-chrome --headless --dump-dom {url}",
                "microsoft-edge --headless --dump-dom {url}",
            ],
            "playwright_browser_executables": [
                "google-chrome",
                "chromium",
                "microsoft-edge",
            ],
            "playwright_wait_until": "networkidle",
            "playwright_wait_ms": 1000,
            "capture_expectations": [
                "atlas-crud-ui",
                "workflow-examples",
                "hybrid-forms-and-flows",
                "navigation-patterns",
                "permission-driven-variations",
            ],
        }
    ],
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_framework_stack_manifest(source_root: Path) -> Path:
    manifest_path = source_root / ".mtafiti" / "viewflow-stack-manifest.json"
    write_text(manifest_path, json.dumps(FRAMEWORK_STACK_MANIFEST, indent=2) + "\n")
    return manifest_path


def write_framework_stack_guide(source_root: Path) -> Path:
    guide_path = source_root / ".mtafiti" / "VIEWFLOW_STACK.md"
    guide = "\n".join(
        [
            "# Viewflow Stack Acquisition Guide",
            "",
            "Clone the required source repositories into the source root:",
            "",
            "```bash",
            "git clone git@github.com:viewflow/viewflow.git viewflow",
            "git clone git@github.com:viewflow/django-material.git django-material",
            "git clone git@github.com:viewflow/cookbook.git cookbook",
            "```",
            "",
            "Capture behavioral evidence from the demo site separately and store snapshots, route notes, or page models under a dedicated workspace folder before generating generalized skills.",
            "",
            "Demo site:",
            "- https://demo.viewflow.io/",
            "",
            "Minimum demo coverage:",
            "- Atlas CRUD/admin UI",
            "- workflow examples",
            "- hybrid UI mixing forms and flows",
            "- navigation patterns",
            "- permission-driven UI variations",
            "",
            "Capture the demo into normalized page models and reports with:",
            "",
            "```bash",
            "python .github/scripts/capture_behavioral_sources.py \\",
            "  --source-root <source-root> \\",
            "  --source-name viewflow-demo-site",
            "```",
            "",
            "The capture script reads `.mtafiti/viewflow-stack-manifest.json`, crawls same-origin demo routes, and writes raw HTML, normalized page-model JSON, a summary JSON file, and a markdown report under `.mtafiti/behavioral-captures/`.",
            "Each capture also stores a timestamped run under `.mtafiti/behavioral-captures/<source>/runs/`, promotes page models into pattern and ontology-candidate artifacts, and keeps latest summary files at the source root for quick inspection.",
            "",
            "If the demo requires JavaScript rendering, request browser-backed capture:",
            "",
            "```bash",
            "python .github/scripts/capture_behavioral_sources.py \\",
            "  --source-root <source-root> \\",
            "  --source-name viewflow-demo-site \\",
            "  --fetch-mode browser",
            "```",
            "",
            "For a richer JavaScript-aware capture path using Playwright and a real browser session, use:",
            "",
            "```bash",
            "python .github/scripts/capture_behavioral_sources.py \\",
            "  --source-root <source-root> \\",
            "  --source-name viewflow-demo-site \\",
            "  --fetch-mode playwright",
            "```",
            "",
            "To diff two stored capture runs, use:",
            "",
            "```bash",
            "python .github/scripts/capture_behavioral_sources.py diff \\",
            "  --source-root <source-root> \\",
            "  --source-name viewflow-demo-site \\",
            "  --baseline-run <run-a> \\",
            "  --candidate-run <run-b>",
            "```",
            "",
            "To import the latest promoted patterns into the repository so the canonical generator can ingest them into committed ontology and skill outputs, use:",
            "",
            "```bash",
            "python .github/scripts/capture_behavioral_sources.py import \\",
            "  --source-root <source-root> \\",
            "  --source-name viewflow-demo-site \\",
            "  --repo-root <repo-root>",
            "```",
            "",
            "After sources are present, run:",
            "",
            "```bash",
            "python .github/scripts/configure_knowledge_sources.py --source-root <source-root>",
            "```",
            "",
        ]
    )
    write_text(guide_path, guide)
    return guide_path


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

    readme_match = re.search(
        r"^##\s+(\d+\.\d+\.\d+)\b", readme_text, flags=re.MULTILINE
    )
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
    description = (
        f"Local knowledge source generated from the {repo_name} repository README."
    )
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


def read_snippet(
    path: Path, start_line: int | None = None, end_line: int | None = None
) -> str:
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


def build_composite_skill(
    name: str, description: str, sections: list[tuple[str, str]], tags: list[str]
) -> str:
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


def generate_cookbook_entries(
    source_root: Path, content_root: Path
) -> list[dict[str, str]]:
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
                tags=[
                    "cookbook",
                    sample_dir.name,
                    "local",
                    "knowledge-src",
                    "viewflow",
                ],
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
            if (
                "migrations" in rel.parts
                or "__pycache__" in rel.parts
                or path in collected
            ):
                continue
            collected.append(path)
            if len(collected) >= 12:
                return collected
    return collected[:12]


def generate_django_material_entries(
    source_root: Path, content_root: Path
) -> list[dict[str, str]]:
    generated: list[dict[str, str]] = []
    material_root = source_root / "django-material"
    if not material_root.exists():
        return generated

    colors = material_root / "material" / "assets" / "colors.css"
    if colors.exists():
        target = (
            content_root
            / "knowledge-src"
            / "skills"
            / "django-material-theme-customization"
            / "SKILL.md"
        )
        write_text(
            target,
            build_composite_skill(
                name="django-material-theme-customization",
                description="Local theming skill generated from django-material design token sources.",
                sections=[
                    (
                        "Theme customization guidance",
                        read_text(material_root / "README.md"),
                    ),
                    ("Color token file", read_text(colors)),
                ],
                tags=[
                    "django-material",
                    "theme",
                    "colors",
                    "design-tokens",
                    "local",
                    "knowledge-src",
                ],
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


def generate_admin_shell_skill_entries(
    source_root: Path, content_root: Path
) -> list[dict[str, str]]:
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

    target = (
        content_root
        / "knowledge-src"
        / "skills"
        / "crud-admin-shell-layout"
        / "SKILL.md"
    )
    write_text(
        target,
        build_composite_skill(
            name="crud-admin-shell-layout",
            description="Opinionated admin CRUD shell guidance derived from cookbook CRUD samples and django-material theme tokens.",
            sections=sections,
            tags=[
                "crud",
                "admin",
                "shell",
                "sidebar",
                "topbar",
                "fab",
                "local",
                "knowledge-src",
                "viewflow",
            ],
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


def generate_domain_skill_entries(
    source_root: Path, content_root: Path
) -> list[dict[str, str]]:
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
                        {
                            "path": "viewflow/README.md",
                            "start_line": 55,
                            "end_line": 143,
                            "label": "README quickstart",
                        },
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
- Detail page recipe: add `DetailViewMixin` when an object needs a dedicated read screen, then drive page/object actions from the viewset instead of hand-wiring template links.
- Delete page recipe: add `DeleteViewMixin` when users need single-object delete confirmation or list bulk delete actions from the stock shell.
- Form page recipe: mount `generic.FormView` or `generic.CreateView` inside an `Application` with `template_name="forms/form.html"` or `viewflow/views/form.html`, then keep titles/buttons in `extra_context`.
- Field recipe: prefer outlined text/select patterns with floating labels, placeholder-free inputs, help text, and explicit error state wiring.
- Input adornment recipe: use widget attrs and component props for `leading-icon`, `trailing_icon`, `trailing_button`, or `trailing_link` rather than custom input wrappers.
- Primary action recipe: use filled buttons for main submit actions and icon FABs for context-specific creation/launch actions.
- Card recipe: use elevated cards with title, subtitle, content slot, and footer slot to package forms and table sections.
- Theme recipe: prefer blue `primary` tokens, `surface`/`surface-container-*` backgrounds, and `on-surface-variant` text for supporting labels and hints.
""".strip(),
                },
                {
                    "title": "Component and base-template primitives",
                    "sources": [
                        {
                            "path": "django-material/README.md",
                            "start_line": 23,
                            "end_line": 62,
                            "label": "README usage and base template",
                        },
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
                        {
                            "path": "django-material/material/templates/cotton/forms/calendar/date.html",
                            "start_line": 1,
                            "end_line": 40,
                            "label": "Trailing button input pattern",
                        },
                    ],
                },
                {
                    "title": "Cookbook widget and icon patterns",
                    "sources": [
                        {
                            "path": "cookbook/forms101/custom_widget/forms.py",
                            "start_line": 15,
                            "end_line": 72,
                            "label": "Custom widget forms with leading-icon attrs and computed tags",
                        },
                        {
                            "path": "cookbook/forms101/forms/order_form.py",
                            "start_line": 1,
                            "end_line": 48,
                            "label": "Cookbook order form with leading-icon text inputs",
                        },
                        {
                            "path": "django-material/demo/templates/demo/widgets.html",
                            "start_line": 1,
                            "end_line": 31,
                            "label": "Widget demo page using nav icons, elevated card, and filled button",
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
            "entry_id": "knowledge-src/viewflow-view-recipes",
            "name": "viewflow-view-recipes",
            "description": "Concrete recipes for list, detail, delete, create/update, and generic form views using Viewflow scaffolding and cookbook examples.",
            "tags": [
                "viewflow",
                "views",
                "list",
                "detail",
                "delete",
                "formview",
                "crud",
                "local",
                "knowledge-src",
            ],
            "requires": ["viewflow/viewflow/urls/model.py"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Prefer `ModelViewset` for the default list/create/update flow; add `DetailViewMixin` and `DeleteViewMixin` explicitly when the specification calls for dedicated detail or delete confirmation pages.
- Keep list/detail/delete/create/update behavior on the viewset through `list_columns`, `list_filter_fields`, `form_layout`, `form_class`, `form_widgets`, `urlpatterns`, and page-action hooks before forking templates.
- For non-model forms, mount `generic.FormView` or `generic.CreateView` inside an `Application` and reuse a shared form template such as `forms/form.html` so agents only provide the form, title, button text, and success URL.
- Follow cookbook page separation: use launchpad/list pages to navigate, but route user-input work to a dedicated create/update/task page with one primary form or wizard instead of mixing several create panels and summary tables on one screen.
- Use inline related-object cards or inline formsets on detail/edit pages only when they support the parent object transaction (for example, object-specific change actions or child records attached to one parent), not as a substitute for separate operator workflows.
- Let the stock template fallback chain work first: `<app>/<model>_list.html`, `<app>/<model>_detail.html`, `<app>/<model>_form.html`, `<app>/<model>_delete.html`, then `viewflow/views/*.html`.
- Use Material icons on the viewset (`Icon("group_work")`, `Icon("engineering")`, etc.) so list navigation, object actions, and app menus stay visually consistent.
""".strip(),
                },
                {
                    "title": "Viewset mixin APIs",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/urls/model.py",
                            "start_line": 107,
                            "end_line": 358,
                            "label": "CreateViewMixin, UpdateViewMixin, DeleteViewMixin, DetailViewMixin, and ReadonlyModelViewset",
                        },
                    ],
                },
                {
                    "title": "Underlying view classes",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/views/list.py",
                            "start_line": 309,
                            "end_line": 454,
                            "label": "ListModelView columns, object links, actions, and template resolution",
                        },
                        {
                            "path": "viewflow/viewflow/views/create.py",
                            "start_line": 25,
                            "end_line": 126,
                            "label": "CreateModelView form-class, widgets, messages, and template fallback",
                        },
                        {
                            "path": "viewflow/viewflow/views/update.py",
                            "start_line": 26,
                            "end_line": 145,
                            "label": "UpdateModelView form/layout overrides and page actions",
                        },
                        {
                            "path": "viewflow/viewflow/views/detail.py",
                            "start_line": 18,
                            "end_line": 97,
                            "label": "DetailModelView object data, actions, and template fallback",
                        },
                        {
                            "path": "viewflow/viewflow/views/delete.py",
                            "start_line": 23,
                            "end_line": 95,
                            "label": "DeleteModelView confirmation flow and success messaging",
                        },
                    ],
                },
                {
                    "title": "Cookbook CRUD recipes",
                    "sources": [
                        {
                            "path": "cookbook/crud101/staff/viewset.py",
                            "start_line": 12,
                            "end_line": 88,
                            "label": "Department and employee viewsets with DetailViewMixin and custom urlpatterns",
                        },
                        {
                            "path": "cookbook/crud101/atlas/viewset.py",
                            "start_line": 17,
                            "end_line": 207,
                            "label": "Atlas CRUD app with DetailViewMixin, DeleteViewMixin, readonly viewsets, icons, and layouts",
                        },
                    ],
                },
                {
                    "title": "Cookbook FormView recipes",
                    "sources": [
                        {
                            "path": "cookbook/forms101/forms/viewset.py",
                            "start_line": 23,
                            "end_line": 153,
                            "label": "Application-mounted FormView and CreateView routes with titles/buttons",
                        },
                        {
                            "path": "cookbook/forms101/forms/views.py",
                            "start_line": 10,
                            "end_line": 106,
                            "label": "Checkout FormView options endpoint and CreateUserView mixin composition",
                        },
                        {
                            "path": "cookbook/forms101/forms/templates/forms/form.html",
                            "start_line": 1,
                            "end_line": 50,
                            "label": "Shared form template with render form form.layout and action footer",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/viewflow-crud-page-templates",
            "name": "viewflow-crud-page-templates",
            "description": "Stock Viewflow page templates for list, detail, form, delete confirmation, and transition pages, including the card and breadcrumb contract they share.",
            "tags": [
                "viewflow",
                "templates",
                "crud",
                "detail",
                "delete",
                "transition",
                "local",
                "knowledge-src",
            ],
            "requires": ["viewflow/viewflow/templates/viewflow/views/list.html"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Reuse the stock `viewflow/views/*.html` templates first; they already encode the standard card header, breadcrumbs, action menu, and footer-button structure.
- Keep page identity in the header (`vf-card__title`, `vf-card__breadcrumbs`, `vf-card__menu`) and put row/object actions into `view.get_page_actions()` or `view.get_object_actions()` instead of hard-coding loose buttons in page bodies.
- Let forms provide `form.media`, `form.layout`, and `view.layout` so templates stay thin and layout decisions remain in view or form code.
- Treat delete and transition pages as detail-plus-confirm patterns: show object context first, then render the confirmation form with an explicit destructive or transition-specific button label.
""".strip(),
                },
                {
                    "title": "List page contract",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/templates/viewflow/views/list.html",
                            "start_line": 1,
                            "end_line": 108,
                            "label": "List page shell with header, filter trigger, bulk actions, table, and pagination",
                        },
                    ],
                },
                {
                    "title": "Detail and object card contract",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/templates/viewflow/views/detail.html",
                            "start_line": 1,
                            "end_line": 12,
                            "label": "Detail page delegating to object_detail_card",
                        },
                        {
                            "path": "viewflow/viewflow/templates/viewflow/includes/object_detail_card.html",
                            "start_line": 1,
                            "end_line": 46,
                            "label": "Object detail card header, breadcrumbs, data table, and actions",
                        },
                    ],
                },
                {
                    "title": "Form page contract",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/templates/viewflow/views/form.html",
                            "start_line": 1,
                            "end_line": 72,
                            "label": "Create/update form card with breadcrumbs, form.media, layout rendering, and footer actions",
                        },
                    ],
                },
                {
                    "title": "Delete and transition confirmation contracts",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/templates/viewflow/views/confirm_delete.html",
                            "start_line": 1,
                            "end_line": 53,
                            "label": "Delete confirmation page with related-object summary and destructive action footer",
                        },
                        {
                            "path": "viewflow/viewflow/templates/viewflow/views/transition.html",
                            "start_line": 1,
                            "end_line": 38,
                            "label": "Transition page layering object data over the shared form template",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/viewflow-navigation-feedback-includes",
            "name": "viewflow-navigation-feedback-includes",
            "description": "Reusable Viewflow include templates for menus, list filters, bulk actions, pagination, page actions, and snackbar feedback.",
            "tags": [
                "viewflow",
                "templates",
                "navigation",
                "feedback",
                "snackbar",
                "pagination",
                "local",
                "knowledge-src",
            ],
            "requires": ["viewflow/viewflow/templates/viewflow/includes/app_menu.html"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Drive site and application navigation from `site.menu_template_name`, `app.menu_template_name`, menu items, and permission checks instead of copying sidebars into each page.
- Use include templates for list interactions (`list_filter`, `list_bulk_actions`, `list_pagination`) so selection state, sort order, filters, and paging remain coordinated.
- Expose page-level actions through `view.get_page_actions()` and render them with the shared action-menu include for consistent iconography and menu behavior.
- Surface feedback through the shared snackbar include so only the latest message is rendered and message placement stays stable across all pages.
""".strip(),
                },
                {
                    "title": "Menu includes",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/templates/viewflow/includes/app_menu.html",
                            "start_line": 1,
                            "end_line": 28,
                            "label": "Application menu with back links, permission-aware viewset entries, and icon fallbacks",
                        },
                        {
                            "path": "viewflow/viewflow/templates/viewflow/includes/site_menu.html",
                            "start_line": 1,
                            "end_line": 30,
                            "label": "Site menu with parent navigation and application entries",
                        },
                    ],
                },
                {
                    "title": "List interaction includes",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/templates/viewflow/includes/list_filter.html",
                            "start_line": 1,
                            "end_line": 15,
                            "label": "Dismissible filter drawer preserving list sort order",
                        },
                        {
                            "path": "viewflow/viewflow/templates/viewflow/includes/list_bulk_actions.html",
                            "start_line": 1,
                            "end_line": 62,
                            "label": "Bulk action chooser with select-all affordance and GO submit button",
                        },
                        {
                            "path": "viewflow/viewflow/templates/viewflow/includes/list_pagination.html",
                            "start_line": 1,
                            "end_line": 29,
                            "label": "Previous/next pagination summary and disabled-state navigation",
                        },
                    ],
                },
                {
                    "title": "Action menu and feedback includes",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/templates/viewflow/includes/view_action_menu.html",
                            "start_line": 1,
                            "end_line": 17,
                            "label": "Page action menu rendering get_page_actions() into a shared menu surface",
                        },
                        {
                            "path": "viewflow/viewflow/templates/viewflow/includes/snackbar.html",
                            "start_line": 1,
                            "end_line": 5,
                            "label": "Snackbar rendering the latest framework message",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/viewflow-base-template-composition",
            "name": "viewflow-base-template-composition",
            "description": "Base template, page shell, block override, and application menu guidance for Viewflow-powered UIs.",
            "tags": [
                "viewflow",
                "templates",
                "base",
                "shell",
                "navigation",
                "local",
                "knowledge-src",
            ],
            "requires": ["viewflow/viewflow/templates/viewflow/base_page.html"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Extend `viewflow/base_page.html` or the app-specific `base_template_name` first so page chrome, menus, and toolbar behavior stay consistent.
- Override `page-menu`, `page-menu-app`, `page-toolbar`, `page-toolbar-actions`, and `content` blocks before copying the whole shell into app-local templates.
- Let `Application(...)`, `Site(...)`, `site.menu_template_name`, and `app.menu_template_name` drive navigation instead of hard-coding sidebars inside every page.
- Prefer template fallback chains from the view classes (`<app>/<model>_form.html`, `<app>/<model>_list.html`, then `viewflow/views/*.html`) before introducing bespoke shells.
""".strip(),
                },
                {
                    "title": "Base template hierarchy",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/templates/viewflow/base.html",
                            "start_line": 1,
                            "end_line": 32,
                            "label": "Global base template with CSS/JS includes and theme variables",
                        },
                        {
                            "path": "viewflow/viewflow/templates/viewflow/base_page.html",
                            "start_line": 1,
                            "end_line": 115,
                            "label": "Page shell with menu, toolbar, content, and navigation blocks",
                        },
                    ],
                },
                {
                    "title": "Page-level extension examples",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/templates/viewflow/views/list.html",
                            "start_line": 1,
                            "end_line": 108,
                            "label": "List page extending base_page with toolbar search and action menu blocks",
                        },
                        {
                            "path": "viewflow/viewflow/views/create.py",
                            "start_line": 93,
                            "end_line": 109,
                            "label": "Create view template fallback chain",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/viewflow-custom-field-renderers",
            "name": "viewflow-custom-field-renderers",
            "description": "Custom field, widget renderer, and Ajax autocomplete patterns for Viewflow forms and CRUD views.",
            "tags": [
                "viewflow",
                "forms",
                "widgets",
                "autocomplete",
                "renderers",
                "local",
                "knowledge-src",
            ],
            "requires": ["viewflow/viewflow/forms/renderers.py"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Build custom field behavior by subclassing `WidgetRenderer` or `InputRenderer`, overriding `create_root(...)`, and registering the widget-to-renderer mapping in `VIEWFLOW['WIDGET_RENDERERS']`.
- Keep submitted values and human-readable labels separate for async selectors; Viewflow's autocomplete renderers use hidden values plus a `value-label` or `initial` payload for display state.
- Pass custom widgets through `form_widgets`, `create_form_widgets`, or `update_form_widgets` on the view/viewset rather than hand-writing field HTML in templates.
- Reuse `FormAjaxCompleteMixin` and `FormDependentSelectMixin` when a form needs async completion or dependent select behavior, then provide the endpoint logic in application code.
""".strip(),
                },
                {
                    "title": "Renderer registry and base classes",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/forms/renderers.py",
                            "start_line": 31,
                            "end_line": 92,
                            "label": "WidgetRenderer registry, InputRenderer, and field metadata propagation",
                        },
                    ],
                },
                {
                    "title": "Autocomplete renderer patterns",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/forms/renderers.py",
                            "start_line": 467,
                            "end_line": 504,
                            "label": "AjaxModelSelectRenderer and AjaxMultipleModelSelectRenderer",
                        },
                    ],
                },
                {
                    "title": "View and viewset wiring",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/views/create.py",
                            "start_line": 25,
                            "end_line": 109,
                            "label": "CreateModelView with FormAjaxCompleteMixin, FormDependentSelectMixin, and form_widgets propagation",
                        },
                        {
                            "path": "viewflow/viewflow/urls/model.py",
                            "start_line": 116,
                            "end_line": 189,
                            "label": "CreateViewMixin and UpdateViewMixin passing layout and form_widgets into view classes",
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
- When the screen is a standalone form workflow rather than CRUD, mount the form through `generic.FormView.as_view(...)` inside an `Application` and reuse one shared form template.
- Compose input affordances through widget attrs such as `leading-icon` and through component trailing actions before writing custom field HTML.
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
                        {
                            "path": "cookbook/forms101/forms/viewset.py",
                            "start_line": 23,
                            "end_line": 153,
                            "label": "FormView registration inside an Application",
                        },
                        {
                            "path": "cookbook/forms101/custom_widget/forms.py",
                            "start_line": 15,
                            "end_line": 72,
                            "label": "Leading-icon and custom widget attribute examples",
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
            "requires": [
                "viewflow/viewflow/urls/model.py",
                "viewflow/viewflow/urls/sites.py",
            ],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Package CRUD modules as `ModelViewset` or `ReadonlyModelViewset` instances and mount them inside `Application(...)`.
- Add `Application(...)` instances to a top-level `Site(...)` to get navigation, theme colors, URL scoping, and menu generation.
- Keep form customization in `form_layout`, `create_form_class`, `update_form_class`, `form_widgets`, filters, and list configuration before reaching for custom templates.
- Define extra object routes on the viewset via `urlpatterns` when behavior truly needs bespoke endpoints.
- Organize CRUD by object boundary: one viewset per core object/aggregate for list/create/update/delete/detail, with related-object maintenance exposed either as object-specific `urlpatterns` or inline cards on the parent detail page.
- Keep workflow/operator actions that are not plain CRUD out of the object list screen; mount them as dedicated `FormView`/wizard routes inside the same `Application` so the user sees one primary task per page.
- Treat dashboards as launchpads and status views, not as mixed CRUD workbenches.
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
            "entry_id": "knowledge-src/lims-operator-ui-patterns",
            "name": "lims-operator-ui-patterns",
            "description": "Launchpad-plus-task-page patterns for operator/admin LIMS workflows built from CRUD and forms cookbook guidance.",
            "tags": [
                "viewflow",
                "crud",
                "forms",
                "lims",
                "operator-ui",
                "application",
                "local",
                "knowledge-src",
            ],
            "requires": [
                "cookbook/crud101/config/urls.py",
                "cookbook/crud101/atlas/viewset.py",
                "cookbook/forms101/forms/viewset.py",
            ],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Treat setup dashboards as launchpads: action cards plus status tables, not mixed multi-form workbenches.
- Put each operator setup task on its own dedicated page with one primary submit action and a clear back link to the launchpad.
- Organize CRUD by object boundary first, then expose non-CRUD operator flows as dedicated `FormView`/wizard routes inside the same `Application(...)`.
- Keep list/detail/review screens separate from create/update forms so operators do not scan past unrelated tables while entering data.
- Prefer declarative form configuration and shared shell/menu scaffolding over page-specific bespoke layouts.
""".strip(),
                },
                {
                    "title": "Cookbook assembly patterns",
                    "sources": [
                        {
                            "path": "cookbook/crud101/config/urls.py",
                            "start_line": 1,
                            "end_line": 32,
                            "label": "Site and Application assembly",
                        },
                        {
                            "path": "cookbook/crud101/atlas/viewset.py",
                            "start_line": 17,
                            "end_line": 101,
                            "label": "Object-scoped CRUD viewsets and app menu structure",
                        },
                        {
                            "path": "cookbook/forms101/forms/viewset.py",
                            "start_line": 23,
                            "end_line": 153,
                            "label": "Dedicated form pages mounted inside an Application",
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
            "entry_id": "knowledge-src/viewflow-advanced-flow-topologies",
            "name": "viewflow-advanced-flow-topologies",
            "description": "Advanced Viewflow control-flow patterns for parallel work, split-first race patterns, switch gateways, and subprocess orchestration.",
            "tags": [
                "viewflow",
                "workflow",
                "parallel",
                "split",
                "join",
                "subprocess",
                "switch",
                "local",
                "knowledge-src",
            ],
            "requires": ["viewflow/viewflow/workflow/flow/nodes.py"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Use `Split` and `Join` when multiple branches must run concurrently and later synchronize.
- Use `SplitFirst` when several alternatives race and the first completed branch should cancel the rest.
- Use `Switch` or `If` for mutually exclusive routing; do not fake gateway behavior with ad hoc conditionals inside views.
- Reach for `Subprocess` / `NSubprocess` when a repeated or nested workflow deserves its own reusable flow definition and lifecycle.
- Prefer data-driven fan-out (`data_source=` / iterable subprocess items) over hand-unrolled duplicated task nodes when the branch count is variable.
""".strip(),
                },
                {
                    "title": "Advanced flow node APIs",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/workflow/flow/nodes.py",
                            "start_line": 324,
                            "end_line": 520,
                            "label": "Split, SplitFirst, Subprocess, NSubprocess, and Switch nodes",
                        },
                    ],
                },
                {
                    "title": "Cookbook branching and synchronization example",
                    "sources": [
                        {
                            "path": "cookbook/workflow101/shipment/flows.py",
                            "start_line": 27,
                            "end_line": 146,
                            "label": "Shipment flow with clerk/warehouse split, conditional insurance branch, and joins",
                        },
                        {
                            "path": "cookbook/patterns/README.md",
                            "start_line": 1,
                            "end_line": 46,
                            "label": "Pattern catalog for sequence, choice, parallel split/join, partial joins, multiple instances, and task distribution",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/viewflow-assignment-permission-patterns",
            "name": "viewflow-assignment-permission-patterns",
            "description": "Assignment, permission, and task-ownership patterns for Viewflow workflows using built-in APIs and django-guardian-style object checks.",
            "tags": [
                "viewflow",
                "workflow",
                "assignment",
                "permissions",
                "guardian",
                "rbac",
                "local",
                "knowledge-src",
            ],
            "requires": ["viewflow/tests/workflow/test_managers_perms.py"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Prefer `Assign(...)` and `Permission(...)` on flow nodes instead of burying routing and authorization logic in view code.
- Use object-aware permission callables when task access depends on a project, department, specimen, or tenant-scoped artifact.
- Treat workflow assignment metadata as part of orchestration design: direct user assignment, permission-driven inbox visibility, and ownership handoff should be explicit in the flow.
- Keep separation-of-duties rules in flow declarations so reviewers can audit who may start, approve, validate, or complete a task.
""".strip(),
                },
                {
                    "title": "Built-in assignment and permission examples",
                    "sources": [
                        {
                            "path": "viewflow/tests/workflow/test_managers_perms.py",
                            "start_line": 27,
                            "end_line": 60,
                            "label": "StartHandle, Assign, and Permission(auto_create=True) examples",
                        },
                        {
                            "path": "viewflow/viewflow/utils.py",
                            "start_line": 81,
                            "end_line": 104,
                            "label": "Model and object permission helper",
                        },
                    ],
                },
                {
                    "title": "Cookbook object-permission flow example",
                    "sources": [
                        {
                            "path": "cookbook/guardian_perms/bills/flows.py",
                            "start_line": 8,
                            "end_line": 94,
                            "label": "Guardian-backed department bill approval flow",
                        },
                        {
                            "path": "cookbook/workflow101/shipment/flows.py",
                            "start_line": 41,
                            "end_line": 143,
                            "label": "Mixed Assign(...) and Permission(...) workflow example",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/django-material-advanced-ux-patterns",
            "name": "django-material-advanced-ux-patterns",
            "description": "Advanced django-material and Cotton UX primitives for menus, tables, floating actions, accessible interactions, and progressive enhancement.",
            "tags": [
                "django-material",
                "ux",
                "cotton",
                "components",
                "table",
                "menu",
                "fab",
                "accessibility",
                "local",
                "knowledge-src",
            ],
            "requires": ["django-material/material/templates/cotton/CLAUDE.md"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Build advanced UX by composing Cotton components and behavior scripts, not by scattering bespoke HTML/JS fragments across pages.
- Keep interactive state explicit through ARIA attributes, `data-*` flags, and Unpoly compiler cleanup patterns.
- Prefer reusable menu, table, FAB, button, card, and calendar primitives so admin shells, workflow inboxes, and dashboards stay visually coherent.
- Treat keyboard handling, focus return, and screen-reader cues as part of the component contract, not optional polish.
""".strip(),
                },
                {
                    "title": "Component system and accessibility guidance",
                    "sources": [
                        {
                            "path": "django-material/material/templates/cotton/CLAUDE.md",
                            "start_line": 1,
                            "end_line": 220,
                            "label": "Cotton component architecture, interactivity, and accessibility rules",
                        },
                    ],
                },
                {
                    "title": "Advanced UI building blocks",
                    "sources": [
                        {
                            "path": "django-material/material/templates/cotton/table/container.html",
                            "start_line": 1,
                            "end_line": 25,
                            "label": "Table container contract with caption, header, body, and footer slots",
                        },
                        {
                            "path": "django-material/material/templates/cotton/button/fab.html",
                            "start_line": 1,
                            "end_line": 43,
                            "label": "Floating action button primitive",
                        },
                        {
                            "path": "django-material/material/templates/cotton/forms/select/outlined.html",
                            "start_line": 1,
                            "end_line": 97,
                            "label": "Outlined select component with trigger and supporting text",
                        },
                        {
                            "path": "django-material/material/templates/cotton/forms/calendar/date.html",
                            "start_line": 1,
                            "end_line": 40,
                            "label": "Date field with trailing action/button pattern",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/viewflow-configurable-metadata-forms",
            "name": "viewflow-configurable-metadata-forms",
            "description": "Patterns for schema-driven metadata capture UIs using Viewflow layouts, field groups, dependent selects, Ajax completion, and nested formsets.",
            "tags": [
                "viewflow",
                "forms",
                "metadata",
                "schema",
                "fieldsets",
                "ajax",
                "dependent-select",
                "local",
                "knowledge-src",
            ],
            "requires": ["cookbook/forms101/forms/views.py"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Model configurable workflow metadata as declarative field/schema definitions, then project them into Viewflow `Layout(...)`, `FieldSet(...)`, `FormSetField(...)`, and widget attrs instead of hand-coding every step form.
- Reuse the same form composition primitives for receiving metadata, archival metadata, storage metadata, and QC annotations so configuration stays consistent across lab workflows.
- Use dependent selects and Ajax completion when later fields depend on tenant reference data, controlled vocabularies, or prior answers.
- Keep computed or read-only operational values in widget attrs / client-side tags rather than mixing derived UI state into persistence logic.
""".strip(),
                },
                {
                    "title": "Dynamic form endpoints and mixins",
                    "sources": [
                        {
                            "path": "cookbook/forms101/forms/views.py",
                            "start_line": 1,
                            "end_line": 106,
                            "label": "FormDependentSelectMixin and FormAjaxCompleteMixin on CreateUserView",
                        },
                    ],
                },
                {
                    "title": "Metadata grouping and dependent field composition",
                    "sources": [
                        {
                            "path": "cookbook/forms101/forms/checkout_form.py",
                            "start_line": 1,
                            "end_line": 83,
                            "label": "Dependent country/city/post code form with Layout, Row, Span, and FieldSet",
                        },
                        {
                            "path": "cookbook/forms101/forms/hospital_form.py",
                            "start_line": 1,
                            "end_line": 77,
                            "label": "Large grouped registration form with clinical FieldSets and FormSetField",
                        },
                        {
                            "path": "cookbook/forms101/custom_widget/forms.py",
                            "start_line": 1,
                            "end_line": 72,
                            "label": "Inline attachments and computed widget tag pattern",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/viewflow-configurable-workflow-runtime-patterns",
            "name": "viewflow-configurable-workflow-runtime-patterns",
            "description": "Patterns for mapping configurable workflow templates to Viewflow runtime constructs, including parallel fan-out, role-based routing, and reusable task metadata.",
            "tags": [
                "viewflow",
                "workflow",
                "designer",
                "runtime",
                "parallel",
                "roles",
                "permissions",
                "metadata",
                "local",
                "knowledge-src",
            ],
            "requires": ["cookbook/patterns/README.md"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Treat workflow templates as declarative node/edge metadata that compile into a bounded set of supported Viewflow patterns: sequence, exclusive choice, split/join, multiple instances, role-based distribution, and guarded approvals.
- Keep template design-time metadata separate from runtime `Process` / `Task` state so versioning, activation, and historical execution stay auditable.
- Store task title, description, assignment, permission, and summary text as template metadata so lab-specific workflows can be configured without rewriting flow code for every study.
- Use multiple-instance and split/join patterns for batch-oriented lab work such as aliquots, plates, parallel QC, and per-sample review branches.
- Pair routing metadata with permission bundles so workflow designer choices stay compatible with guardian-backed object access and role-specific inboxes.
""".strip(),
                },
                {
                    "title": "Pattern catalog for supported workflow designer primitives",
                    "sources": [
                        {
                            "path": "cookbook/patterns/README.md",
                            "start_line": 1,
                            "end_line": 46,
                            "label": "Control-flow and task-distribution pattern inventory",
                        },
                    ],
                },
                {
                    "title": "Configurable fan-out and repeated-task example",
                    "sources": [
                        {
                            "path": "cookbook/patterns/flows/multiple_instances.py",
                            "start_line": 15,
                            "end_line": 105,
                            "label": "FormSet-driven multiple instances using Split and task_data_source",
                        },
                    ],
                },
                {
                    "title": "Role and permission driven routing examples",
                    "sources": [
                        {
                            "path": "cookbook/patterns/flows/role_based.py",
                            "start_line": 38,
                            "end_line": 131,
                            "label": "Role-based approval flow with Permission(...) and runtime assignment",
                        },
                        {
                            "path": "cookbook/workflow101/shipment/flows.py",
                            "start_line": 17,
                            "end_line": 146,
                            "label": "Shipment flow with process metadata, split/join coordination, Assign(...), and Permission(...)",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/viewflow-governed-workflow-definition-patterns",
            "name": "viewflow-governed-workflow-definition-patterns",
            "description": "Research-backed patterns for compiling governed operation/workflow templates into Viewflow flows with explicit process/task state, bounded nodes, assignment, and permissions.",
            "tags": [
                "viewflow",
                "workflow",
                "process",
                "task",
                "assignment",
                "permissions",
                "local",
                "knowledge-src",
            ],
            "requires": ["viewflow/README.md"],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Anchor runtime execution in explicit `Process` and `Task` state; do not bury workflow status inside arbitrary business records.
- Keep configurable workflow builders bounded to supported Viewflow node families: `Start`, `StartHandle`, `View`, `Function`, `Handle`, `If`, `Switch`, `Split`, `SplitFirst`, `Join`, and `End`.
- Put routing, ownership, and authorization on node metadata using `Assign(...)` and `Permission(...)` semantics rather than scattering them across view code.
- Use `If` / `Switch` for exclusive routing, `Split` / `Join` for coordinated parallel work, and split data sources for repeated per-item tasks.
- Register approved flows through `FlowAppViewset`, `Application`, and `Site` so workflow execution, inboxes, and operator navigation stay aligned.
""".strip(),
                },
                {
                    "title": "Quickstart and Process model baseline",
                    "sources": [
                        {
                            "path": "viewflow/README.md",
                            "start_line": 55,
                            "end_line": 143,
                            "label": "README quickstart with Process model, Flow, and Site registration",
                        },
                        {
                            "path": "viewflow/viewflow/workflow/models.py",
                            "start_line": 1,
                            "end_line": 120,
                            "label": "Process and Task base models",
                        },
                    ],
                },
                {
                    "title": "Bounded node palette and task actions",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/workflow/flow/nodes.py",
                            "start_line": 1,
                            "end_line": 226,
                            "label": "Start, StartHandle, View, If, and function/handle nodes",
                        },
                        {
                            "path": "viewflow/viewflow/workflow/flow/nodes.py",
                            "start_line": 280,
                            "end_line": 430,
                            "label": "Split, SplitFirst, Join, and Switch nodes",
                        },
                    ],
                },
                {
                    "title": "Activation and permission behavior",
                    "sources": [
                        {
                            "path": "viewflow/viewflow/workflow/activation.py",
                            "start_line": 1,
                            "end_line": 220,
                            "label": "Activation lifecycle and status transitions",
                        },
                        {
                            "path": "viewflow/tests/workflow/test_managers_perms.py",
                            "start_line": 20,
                            "end_line": 60,
                            "label": "Assign and Permission examples in tests",
                        },
                    ],
                },
            ],
        },
        {
            "entry_id": "knowledge-src/openclinica-odm-form-engine-patterns",
            "name": "openclinica-odm-form-engine-patterns",
            "description": "Research-backed form-engine patterns inspired by OpenClinica for spreadsheet-authored, versioned CRF/form packages with ODM-aligned artifacts.",
            "tags": [
                "openclinica",
                "odm",
                "cdisc",
                "xlsx",
                "form-engine",
                "crf",
                "local",
                "knowledge-src",
            ],
            "requires": [],
            "sections": [
                {
                    "title": "Architecture rules",
                    "body": """
- Treat authored forms as governed versioned packages; once a published version is in use, future changes create a new version rather than mutating the original.
- Support both a visual designer path and a spreadsheet-template path, but keep the spreadsheet path available for advanced logic such as cascading selects, hard edit checks, and long controlled lists.
- Model forms explicitly as package metadata plus sections/pages, item groups including repeats, items/questions, and choice lists with stable identifiers suitable for ODM/XML interchange.
- Keep a canonical relational representation for runtime queryability, while generating lossless ODM/XML and XLSX artifacts for import/export and regulated interchange.
- Preserve historical submissions against the exact published form version, including revision notes and stable identifiers, so rendering and audits remain reproducible.
- Treat large choice sets and hierarchical choice filters as first-class design concerns instead of forcing every enumeration into a flat inline list.

Reference research:
- OpenClinica OC4 Using the Form Template: spreadsheet-based form definition with settings, choices, and survey sheets, plus advanced logic such as cascading selects and long-list files.
- OpenClinica CRF specifications: each CRF version lives in its own spreadsheet/version definition and preserves historical version context.
- OpenClinica XML import guidance: ODM 1.3 hierarchy around study event, form, item group, and item data supports interchange but does not require ODM XML to be the only application persistence model.
""".strip(),
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
            generated.append(
                {
                    "repo": repo_dir.name,
                    "entry_type": "doc",
                    "entry_id": f"knowledge-src/{repo_name}",
                }
            )
        else:
            target = author_root / "skills" / repo_name / "SKILL.md"
            write_text(target, build_skill(repo_name, readme_text))
            generated.append(
                {
                    "repo": repo_dir.name,
                    "entry_type": "skill",
                    "entry_id": f"knowledge-src/{repo_name}",
                }
            )
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


def has_candidate_repositories(source_root: Path) -> bool:
    return any(iter_repo_dirs(source_root))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        required=True,
        help="Directory containing cloned knowledge repositories.",
    )
    parser.add_argument(
        "--content-root",
        help="Generated Context Hub content root. Defaults to <source-root>/.chub/content",
    )
    parser.add_argument(
        "--dist-root",
        help="Built Context Hub dist root. Defaults to <source-root>/.chub/dist",
    )
    parser.add_argument(
        "--config-path", help="chub config file path. Defaults to ~/.chub/config.yaml"
    )
    parser.add_argument(
        "--bootstrap-viewflow-stack",
        action="store_true",
        help="Write a source-acquisition manifest and guide for the Viewflow, django-material, cookbook, and demo-site analysis stack.",
    )
    args = parser.parse_args()

    source_root = Path(args.source_root).expanduser().resolve()
    content_root = (
        Path(args.content_root).expanduser().resolve()
        if args.content_root
        else source_root / ".chub" / "content"
    )
    dist_root = (
        Path(args.dist_root).expanduser().resolve()
        if args.dist_root
        else source_root / ".chub" / "dist"
    )
    config_path = (
        Path(args.config_path).expanduser().resolve()
        if args.config_path
        else Path.home() / ".chub" / "config.yaml"
    )

    bootstrap_outputs: dict[str, str] = {}
    if args.bootstrap_viewflow_stack:
        bootstrap_outputs = {
            "manifest": str(write_framework_stack_manifest(source_root)),
            "guide": str(write_framework_stack_guide(source_root)),
        }

    if args.bootstrap_viewflow_stack and not has_candidate_repositories(source_root):
        print(
            json.dumps(
                {
                    "generated": [],
                    "content_root": str(content_root),
                    "dist_root": str(dist_root),
                    "config_path": str(config_path),
                    "bootstrap": bootstrap_outputs,
                    "note": "Bootstrap artifacts written; skipping Context Hub generation because no source repositories were found.",
                },
                indent=2,
            )
        )
        return 0

    generated = generate_content(source_root, content_root)
    run_chub_build(content_root, dist_root)
    write_chub_config(dist_root, config_path)

    print(
        json.dumps(
            {
                "generated": generated,
                "content_root": str(content_root),
                "dist_root": str(dist_root),
                "config_path": str(config_path),
                "bootstrap": bootstrap_outputs,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
