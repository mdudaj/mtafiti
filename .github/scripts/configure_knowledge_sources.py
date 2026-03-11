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
