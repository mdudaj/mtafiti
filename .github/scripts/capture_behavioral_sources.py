#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen

_PLAYWRIGHT_NODE_PATH_CACHE: str | None | bool = None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def load_framework_stack_manifest(source_root: Path) -> dict[str, object]:
    manifest_path = source_root / ".mtafiti" / "viewflow-stack-manifest.json"
    return json.loads(read_text(manifest_path))


def select_behavioral_source(
    manifest: dict[str, object], source_name: str
) -> dict[str, object]:
    for item in manifest.get("behavioral_sources", []):
        if isinstance(item, dict) and item.get("name") == source_name:
            return item
    raise ValueError(f"Behavioral source not found: {source_name}")


def slugify_url(url: str) -> str:
    parsed = urlparse(url)
    base = parsed.path.strip("/") or "root"
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "root"
    if parsed.query:
        digest = hashlib.sha1(parsed.query.encode("utf-8")).hexdigest()[:8]
        slug = f"{slug}-{digest}"
    return slug


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def normalize_link(base_url: str, href: str, *, same_origin_only: bool) -> str | None:
    cleaned = href.strip()
    if not cleaned or cleaned.startswith("#"):
        return None
    if cleaned.startswith(("mailto:", "javascript:", "tel:")):
        return None

    absolute = urldefrag(urljoin(base_url, cleaned)).url
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None

    if same_origin_only:
        base = urlparse(base_url)
        if (parsed.scheme, parsed.netloc) != (base.scheme, base.netloc):
            return None
    return absolute


def detect_browser_dump_command(candidates: list[str]) -> str | None:
    for command in candidates:
        tokens = shlex.split(command)
        if tokens and shutil.which(tokens[0]):
            return command
    return None


def detect_browser_executable(candidates: list[str]) -> str | None:
    for executable in candidates:
        resolved = shutil.which(executable)
        if resolved:
            return resolved
    return None


def detect_playwright_node_path() -> str | None:
    global _PLAYWRIGHT_NODE_PATH_CACHE
    if _PLAYWRIGHT_NODE_PATH_CACHE is False:
        return None
    if isinstance(_PLAYWRIGHT_NODE_PATH_CACHE, str):
        return _PLAYWRIGHT_NODE_PATH_CACHE
    if not shutil.which("npx") or not shutil.which("node"):
        _PLAYWRIGHT_NODE_PATH_CACHE = False
        return None

    completed = subprocess.run(
        [
            "npx",
            "--yes",
            "-p",
            "playwright",
            "-c",
            'dirname "$(dirname "$(command -v playwright)")"',
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        _PLAYWRIGHT_NODE_PATH_CACHE = False
        return None

    node_path = completed.stdout.strip()
    if not node_path or not (Path(node_path) / "playwright").exists():
        _PLAYWRIGHT_NODE_PATH_CACHE = False
        return None
    _PLAYWRIGHT_NODE_PATH_CACHE = node_path
    return node_path


def build_playwright_capture_script() -> str:
    return """
const fs = require('fs');
const { chromium } = require('playwright');

(async () => {
  const launchOptions = { headless: true };
  if (process.env.MTAFITI_EXECUTABLE_PATH) {
    launchOptions.executablePath = process.env.MTAFITI_EXECUTABLE_PATH;
  }
  const browser = await chromium.launch(launchOptions);
  const page = await browser.newPage();
  await page.goto(process.env.MTAFITI_URL, {
    waitUntil: process.env.MTAFITI_WAIT_UNTIL || 'networkidle',
    timeout: Number(process.env.MTAFITI_GOTO_TIMEOUT_MS || '30000'),
  });
  const waitMs = Number(process.env.MTAFITI_WAIT_MS || '0');
  if (waitMs > 0) {
    await page.waitForTimeout(waitMs);
  }
  const html = await page.content();
  fs.writeFileSync(process.env.MTAFITI_OUTPUT, html, 'utf8');
  process.stdout.write(JSON.stringify({ final_url: page.url() }));
  await browser.close();
})().catch((error) => {
  process.stderr.write(String(error && error.stack ? error.stack : error));
  process.exit(1);
});
""".strip()


class BehavioralPageParser(HTMLParser):
    def __init__(self, page_url: str):
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.title_parts: list[str] = []
        self.current_heading: str | None = None
        self.current_link_href: str | None = None
        self.current_button_type = "button"
        self.current_form: dict[str, object] | None = None
        self.current_title = False
        self.headings: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.buttons: list[dict[str, str]] = []
        self.forms: list[dict[str, object]] = []
        self.landmarks: set[str] = set()
        self.components: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        tag_name = tag.lower()
        if tag_name in {
            "header",
            "nav",
            "main",
            "aside",
            "footer",
            "section",
            "article",
        }:
            self.landmarks.add(tag_name)
            self.components.add(tag_name)
        if tag_name == "title":
            self.current_title = True
        if tag_name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.current_heading = tag_name
        if tag_name == "a":
            self.current_link_href = attr_map.get("href", "")
        if tag_name == "button":
            self.current_button_type = attr_map.get("type", "button")
        if tag_name == "form":
            self.current_form = {
                "action": attr_map.get("action", "") or self.page_url,
                "method": (attr_map.get("method", "get") or "get").lower(),
                "inputs": [],
            }
            self.components.add("form")
        if (
            tag_name in {"input", "select", "textarea"}
            and self.current_form is not None
        ):
            inputs = self.current_form.setdefault("inputs", [])
            if isinstance(inputs, list):
                inputs.append(
                    {
                        "name": attr_map.get("name", ""),
                        "type": attr_map.get("type", tag_name),
                    }
                )
        if tag_name in {"table", "ul", "ol", "dialog"}:
            self.components.add(tag_name)

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name == "title":
            self.current_title = False
        if self.current_heading == tag_name:
            self.current_heading = None
        if tag_name == "a":
            self.current_link_href = None
        if tag_name == "form" and self.current_form is not None:
            self.forms.append(self.current_form)
            self.current_form = None

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        if self.current_title:
            self.title_parts.append(cleaned)
        if self.current_heading:
            self.headings.append({"level": self.current_heading, "text": cleaned})
        if self.current_link_href:
            self.links.append({"href": self.current_link_href, "text": cleaned})

    def page_model(self) -> dict[str, object]:
        title = " ".join(self.title_parts).strip()
        interactions = []
        for form in self.forms:
            interactions.append(
                {
                    "type": "form-submit",
                    "method": form.get("method", "get"),
                    "action": form.get("action", self.page_url),
                    "input_count": len(form.get("inputs", [])),
                }
            )
        if self.links:
            interactions.append({"type": "link-navigation", "count": len(self.links)})
        return {
            "route": urlparse(self.page_url).path or "/",
            "title": title,
            "headings": self.headings,
            "links": self.links,
            "forms": self.forms,
            "visible_components": sorted(self.components),
            "landmarks": sorted(self.landmarks),
            "interaction_flow": interactions,
        }


def fetch_html_http(url: str, timeout: int = 20) -> tuple[str, str]:
    request = Request(url, headers={"User-Agent": "mtafiti-behavioral-capture/1.0"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        content_type = response.headers.get("Content-Type", "")
        final_url = response.geturl()
        if "html" not in content_type.lower():
            raise ValueError(
                f"Unsupported content type for {final_url}: {content_type}"
            )
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace"), final_url


def fetch_html_browser(
    url: str, browser_command: str, timeout: int = 20
) -> tuple[str, str]:
    command_template = (
        browser_command if "{url}" in browser_command else f"{browser_command} {{url}}"
    )
    rendered_command = command_template.format(url=url)
    completed = subprocess.run(  # noqa: S603
        shlex.split(rendered_command),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"Browser capture failed for {url}: {stderr}")
    html = completed.stdout
    if "<html" not in html.lower():
        raise ValueError(f"Browser capture returned non-HTML output for {url}")
    return html, url


def fetch_html_playwright(
    url: str,
    *,
    executable_path: str | None,
    wait_until: str,
    wait_ms: int,
    timeout: int = 20,
) -> tuple[str, str]:
    node_path = detect_playwright_node_path()
    if not node_path:
        raise ValueError(
            "Playwright capture requested but no runnable Playwright package is available via npx"
        )

    with tempfile.TemporaryDirectory(prefix="mtafiti-playwright-") as temp_dir:
        temp_root = Path(temp_dir)
        script_path = temp_root / "capture.js"
        output_path = temp_root / "page.html"
        write_text(script_path, build_playwright_capture_script() + "\n")

        environment = dict(os.environ)
        environment["NODE_PATH"] = (
            f"{node_path}:{environment['NODE_PATH']}"
            if environment.get("NODE_PATH")
            else node_path
        )
        environment["MTAFITI_URL"] = url
        environment["MTAFITI_OUTPUT"] = str(output_path)
        environment["MTAFITI_WAIT_UNTIL"] = wait_until
        environment["MTAFITI_WAIT_MS"] = str(wait_ms)
        environment["MTAFITI_GOTO_TIMEOUT_MS"] = str(timeout * 1000)
        if executable_path:
            environment["MTAFITI_EXECUTABLE_PATH"] = executable_path

        completed = subprocess.run(
            ["node", str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=environment,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip()
            raise ValueError(f"Playwright capture failed for {url}: {stderr}")
        if not output_path.exists():
            raise ValueError(f"Playwright capture produced no HTML output for {url}")
        html = read_text(output_path)
        if "<html" not in html.lower():
            raise ValueError(f"Playwright capture returned non-HTML output for {url}")
        stdout = completed.stdout.strip()
        final_url = url
        if stdout:
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError:
                payload = {}
            final_url = str(payload.get("final_url") or url)
        return html, final_url


def fetch_html(
    url: str,
    *,
    fetch_mode: str,
    browser_command: str | None,
    playwright_executable_path: str | None = None,
    playwright_wait_until: str = "networkidle",
    playwright_wait_ms: int = 1000,
    timeout: int = 20,
) -> tuple[str, str]:
    if fetch_mode == "http":
        return fetch_html_http(url, timeout=timeout)
    if fetch_mode == "browser":
        if not browser_command:
            raise ValueError(
                "Browser capture requested but no browser dump command is available"
            )
        return fetch_html_browser(url, browser_command, timeout=timeout)
    if fetch_mode == "playwright":
        return fetch_html_playwright(
            url,
            executable_path=playwright_executable_path,
            wait_until=playwright_wait_until,
            wait_ms=playwright_wait_ms,
            timeout=timeout,
        )
    raise ValueError(f"Unsupported fetch mode: {fetch_mode}")


def infer_layout_type(page_model: dict[str, object]) -> str:
    route = str(page_model.get("route", "")).lower()
    title = str(page_model.get("title", "")).lower()
    headings = " ".join(
        item.get("text", "")
        for item in page_model.get("headings", [])
        if isinstance(item, dict)
    ).lower()
    components = {str(item) for item in page_model.get("visible_components", [])}
    if page_model.get("forms"):
        if "workflow" in route or "workflow" in title or "workflow" in headings:
            return "workflow_form"
        return "form"
    if "table" in components:
        return "table_list"
    if "nav" in components and "main" in components:
        return "dashboard"
    if "workflow" in route or "workflow" in title or "workflow" in headings:
        return "workflow_page"
    return "content_page"


def promote_patterns(
    summary: dict[str, object], target_root: Path
) -> dict[str, object]:
    pages_root = target_root / "pages"
    page_patterns: list[dict[str, object]] = []
    navigation_edges: list[dict[str, str]] = []
    workflow_pages: list[dict[str, object]] = []
    permission_hints: list[dict[str, str]] = []

    for page in summary.get("pages", []):
        if not isinstance(page, dict):
            continue
        model_path = target_root / str(page.get("page_model_path", ""))
        if not model_path.exists():
            continue
        model = json.loads(read_text(model_path))
        route = str(model.get("route", ""))
        layout_type = infer_layout_type(model)
        internal_routes = []
        for link in model.get("links", []):
            if not isinstance(link, dict):
                continue
            href = str(link.get("href", ""))
            normalized = normalize_link(
                str(page.get("url", "")), href, same_origin_only=True
            )
            if normalized:
                linked_route = urlparse(normalized).path or "/"
                internal_routes.append(linked_route)
                navigation_edges.append({"from": route, "to": linked_route})
        pattern = {
            "route": route,
            "title": model.get("title", ""),
            "primary_heading": page.get("primary_heading", ""),
            "layout_type": layout_type,
            "visible_components": model.get("visible_components", []),
            "interaction_types": [
                item.get("type", "")
                for item in model.get("interaction_flow", [])
                if isinstance(item, dict)
            ],
            "internal_navigation": sorted(set(internal_routes)),
        }
        page_patterns.append(pattern)

        if layout_type.startswith("workflow"):
            workflow_pages.append(
                {
                    "route": route,
                    "title": model.get("title", ""),
                    "form_actions": [
                        form.get("action", "")
                        for form in model.get("forms", [])
                        if isinstance(form, dict)
                    ],
                }
            )

        combined_text = " ".join(
            [str(model.get("title", "")), str(page.get("primary_heading", "")), route]
        ).lower()
        if any(
            token in combined_text
            for token in ["login", "sign in", "account", "admin", "staff"]
        ):
            permission_hints.append({"route": route, "signal": combined_text.strip()})

    promoted = {
        "page_patterns": sorted(page_patterns, key=lambda item: str(item["route"])),
        "ontology_candidates": {
            "ui": [
                {
                    "route": item["route"],
                    "layout_type": item["layout_type"],
                    "components": item["visible_components"],
                }
                for item in page_patterns
            ],
            "navigation": sorted(
                navigation_edges, key=lambda item: (item["from"], item["to"])
            ),
            "workflow": workflow_pages,
            "state": [
                {
                    "route": item["route"],
                    "interaction_types": item["interaction_types"],
                }
                for item in page_patterns
                if item["interaction_types"]
            ],
            "permission": permission_hints,
            "cross_layer": [
                {
                    "route": item["route"],
                    "layout_type": item["layout_type"],
                    "workflow_bound": item["layout_type"].startswith("workflow"),
                }
                for item in page_patterns
            ],
        },
    }
    write_text(target_root / "patterns.json", json.dumps(promoted, indent=2) + "\n")
    write_text(
        target_root / "ontology-candidates.json",
        json.dumps(promoted["ontology_candidates"], indent=2) + "\n",
    )
    write_text(target_root / "patterns.md", render_patterns_report(promoted))
    return promoted


def render_patterns_report(promoted: dict[str, object]) -> str:
    lines = [
        "# Promoted Behavioral Patterns",
        "",
        "## Page Patterns",
        "",
    ]
    for pattern in promoted.get("page_patterns", []):
        if not isinstance(pattern, dict):
            continue
        lines.append(
            f"### {pattern.get('primary_heading') or pattern.get('title') or pattern.get('route')}"
        )
        lines.append("")
        lines.append(f"- route: `{pattern.get('route')}`")
        lines.append(f"- layout_type: `{pattern.get('layout_type')}`")
        components = pattern.get("visible_components", [])
        if components:
            lines.append(f"- components: `{', '.join(components)}`")
        interactions = pattern.get("interaction_types", [])
        if interactions:
            lines.append(f"- interactions: `{', '.join(interactions)}`")
        routes = pattern.get("internal_navigation", [])
        if routes:
            lines.append(f"- internal_navigation: `{', '.join(routes)}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_capture_report(summary: dict[str, object]) -> str:
    lines = [
        "# Behavioral Capture Report",
        "",
        f"- source: `{summary['source_name']}`",
        f"- base_url: `{summary['base_url']}`",
        f"- captured_at: `{summary['captured_at']}`",
        f"- page_count: `{summary['page_count']}`",
        "",
        "## Pages",
        "",
    ]
    for page in summary.get("pages", []):
        if not isinstance(page, dict):
            continue
        lines.append(f"### {page.get('title') or page.get('route')}")
        lines.append("")
        lines.append(f"- route: `{page.get('route')}`")
        primary_heading = page.get("primary_heading")
        if primary_heading:
            lines.append(f"- primary_heading: `{primary_heading}`")
        lines.append(f"- headings: `{page.get('heading_count', 0)}`")
        lines.append(f"- links: `{page.get('link_count', 0)}`")
        lines.append(f"- forms: `{page.get('form_count', 0)}`")
        components = page.get("visible_components", [])
        if components:
            lines.append(f"- components: `{', '.join(components)}`")
        interactions = page.get("interaction_types", [])
        if interactions:
            lines.append(f"- interactions: `{', '.join(interactions)}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def load_summary(path: Path) -> dict[str, object]:
    return json.loads(read_text(path))


def load_page_models(run_root: Path) -> dict[str, dict[str, object]]:
    models: dict[str, dict[str, object]] = {}
    for path in sorted((run_root / "pages").glob("*.json")):
        model = json.loads(read_text(path))
        route = str(model.get("route", ""))
        if route:
            models[route] = model
    return models


def diff_capture_runs(
    source_root: Path, source_name: str, baseline_run: str, candidate_run: str
) -> dict[str, object]:
    target_root = source_root / ".mtafiti" / "behavioral-captures" / source_name
    baseline_root = target_root / "runs" / baseline_run
    candidate_root = target_root / "runs" / candidate_run
    baseline_summary = load_summary(baseline_root / "summary.json")
    candidate_summary = load_summary(candidate_root / "summary.json")
    baseline_models = load_page_models(baseline_root)
    candidate_models = load_page_models(candidate_root)

    baseline_routes = set(baseline_models)
    candidate_routes = set(candidate_models)
    changed_pages: list[dict[str, object]] = []
    for route in sorted(baseline_routes & candidate_routes):
        before = baseline_models[route]
        after = candidate_models[route]
        component_delta = sorted(
            set(after.get("visible_components", []))
            - set(before.get("visible_components", []))
        )
        removed_components = sorted(
            set(before.get("visible_components", []))
            - set(after.get("visible_components", []))
        )
        interaction_before = {
            item.get("type", "")
            for item in before.get("interaction_flow", [])
            if isinstance(item, dict)
        }
        interaction_after = {
            item.get("type", "")
            for item in after.get("interaction_flow", [])
            if isinstance(item, dict)
        }
        interaction_added = sorted(interaction_after - interaction_before)
        interaction_removed = sorted(interaction_before - interaction_after)
        title_changed = before.get("title") != after.get("title")
        heading_changed = before.get("headings") != after.get("headings")
        if (
            component_delta
            or removed_components
            or interaction_added
            or interaction_removed
            or title_changed
            or heading_changed
        ):
            changed_pages.append(
                {
                    "route": route,
                    "title_before": before.get("title", ""),
                    "title_after": after.get("title", ""),
                    "components_added": component_delta,
                    "components_removed": removed_components,
                    "interactions_added": interaction_added,
                    "interactions_removed": interaction_removed,
                    "heading_changed": heading_changed,
                }
            )

    diff = {
        "source_name": source_name,
        "baseline_run": baseline_run,
        "candidate_run": candidate_run,
        "baseline_page_count": baseline_summary.get("page_count", 0),
        "candidate_page_count": candidate_summary.get("page_count", 0),
        "added_routes": sorted(candidate_routes - baseline_routes),
        "removed_routes": sorted(baseline_routes - candidate_routes),
        "changed_pages": changed_pages,
    }
    diffs_root = target_root / "diffs"
    diff_id = f"{baseline_run}-to-{candidate_run}"
    write_text(diffs_root / f"{diff_id}.json", json.dumps(diff, indent=2) + "\n")
    write_text(diffs_root / f"{diff_id}.md", render_diff_report(diff))
    return diff


def render_diff_report(diff: dict[str, object]) -> str:
    lines = [
        "# Behavioral Capture Diff",
        "",
        f"- source: `{diff['source_name']}`",
        f"- baseline_run: `{diff['baseline_run']}`",
        f"- candidate_run: `{diff['candidate_run']}`",
        f"- added_routes: `{len(diff['added_routes'])}`",
        f"- removed_routes: `{len(diff['removed_routes'])}`",
        f"- changed_pages: `{len(diff['changed_pages'])}`",
        "",
    ]
    if diff.get("added_routes"):
        lines.extend(["## Added Routes", ""])
        lines.extend([f"- `{route}`" for route in diff["added_routes"]])
        lines.append("")
    if diff.get("removed_routes"):
        lines.extend(["## Removed Routes", ""])
        lines.extend([f"- `{route}`" for route in diff["removed_routes"]])
        lines.append("")
    if diff.get("changed_pages"):
        lines.extend(["## Changed Pages", ""])
        for page in diff["changed_pages"]:
            if not isinstance(page, dict):
                continue
            lines.append(f"### {page.get('route')}")
            lines.append("")
            if page.get("title_before") != page.get("title_after"):
                lines.append(
                    f"- title: `{page.get('title_before')}` -> `{page.get('title_after')}`"
                )
            for key in [
                "components_added",
                "components_removed",
                "interactions_added",
                "interactions_removed",
            ]:
                values = page.get(key, [])
                if values:
                    lines.append(f"- {key}: `{', '.join(values)}`")
            if page.get("heading_changed"):
                lines.append("- heading_changed: `true`")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def infer_source_frameworks(source_config: dict[str, object]) -> list[str]:
    frameworks = [str(item) for item in source_config.get("frameworks", [])]
    if frameworks:
        return frameworks
    source_name = str(source_config.get("name", "")).lower()
    inferred: list[str] = []
    if "viewflow" in source_name:
        inferred.append("viewflow")
    if "material" in source_name or "viewflow" in source_name:
        inferred.append("django-material")
    return inferred


def import_promoted_patterns(
    source_root: Path, source_config: dict[str, object], repo_root: Path
) -> dict[str, object]:
    source_name = str(source_config["name"])
    capture_root = source_root / ".mtafiti" / "behavioral-captures" / source_name
    patterns_path = capture_root / "patterns.json"
    ontology_path = capture_root / "ontology-candidates.json"
    if not patterns_path.exists() or not ontology_path.exists():
        raise ValueError(
            f"Promoted artifacts are missing for {source_name}. Run a capture first so patterns.json and ontology-candidates.json exist."
        )

    destination_root = (
        repo_root / "analysis" / "behavioral_patterns" / slugify(source_name)
    )
    remove_path(destination_root)
    destination_root.mkdir(parents=True, exist_ok=True)

    copied_files: list[str] = []
    for filename in [
        "patterns.json",
        "ontology-candidates.json",
        "patterns.md",
        "summary.json",
        "report.md",
        "latest-run.txt",
    ]:
        source_path = capture_root / filename
        if source_path.exists():
            write_text(destination_root / filename, read_text(source_path))
            copied_files.append(filename)

    latest_run = (
        (capture_root / "latest-run.txt").read_text(encoding="utf-8").strip()
        if (capture_root / "latest-run.txt").exists()
        else ""
    )
    manifest = {
        "source_name": source_name,
        "source_slug": slugify(source_name),
        "source_url": str(source_config.get("url", "")),
        "source_type": str(source_config.get("type", "behavioral-source")),
        "frameworks": infer_source_frameworks(source_config),
        "capture_expectations": [
            str(item) for item in source_config.get("capture_expectations", [])
        ],
        "latest_run": latest_run,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "repo_relative_root": str(destination_root.relative_to(repo_root)),
    }
    write_text(
        destination_root / "source-manifest.json", json.dumps(manifest, indent=2) + "\n"
    )
    copied_files.append("source-manifest.json")
    return {
        "source_name": source_name,
        "destination": str(destination_root),
        "latest_run": latest_run,
        "copied_files": copied_files,
    }


def capture_behavioral_source(
    source_config: dict[str, object],
    output_root: Path,
    *,
    fetch_mode: str | None = None,
    browser_command: str | None = None,
    run_label: str | None = None,
) -> dict[str, object]:
    source_name = str(source_config["name"])
    base_url = str(source_config["url"])
    same_origin_only = bool(source_config.get("same_origin_only", True))
    max_capture_pages = int(source_config.get("max_capture_pages", 25))
    seed_paths = [str(item) for item in source_config.get("capture_seed_paths", ["/"])]
    selected_fetch_mode = fetch_mode or str(
        source_config.get("preferred_capture_mode", "http")
    )
    playwright_executable_path = None
    playwright_wait_until = str(
        source_config.get("playwright_wait_until", "networkidle")
    )
    playwright_wait_ms = int(source_config.get("playwright_wait_ms", 1000))

    if selected_fetch_mode == "browser" and not browser_command:
        browser_command = detect_browser_dump_command(
            [str(item) for item in source_config.get("browser_dump_commands", [])]
        )
    if selected_fetch_mode == "playwright":
        playwright_executable_path = detect_browser_executable(
            [
                str(item)
                for item in source_config.get("playwright_browser_executables", [])
            ]
        )

    target_root = output_root / source_name
    resolved_run_label = run_label or datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    run_root = target_root / "runs" / resolved_run_label
    pages_root = run_root / "pages"
    pages_root.mkdir(parents=True, exist_ok=True)

    queue = deque(urljoin(base_url, path) for path in seed_paths)
    visited: set[str] = set()
    captured_pages: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []

    while queue and len(captured_pages) < max_capture_pages:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        try:
            html, final_url = fetch_html(
                current,
                fetch_mode=selected_fetch_mode,
                browser_command=browser_command,
                playwright_executable_path=playwright_executable_path,
                playwright_wait_until=playwright_wait_until,
                playwright_wait_ms=playwright_wait_ms,
            )
            parser = BehavioralPageParser(final_url)
            parser.feed(html)
            model = parser.page_model()
            slug = slugify_url(final_url)
            write_text(pages_root / f"{slug}.html", html)
            write_text(pages_root / f"{slug}.json", json.dumps(model, indent=2) + "\n")

            captured_pages.append(
                {
                    "url": final_url,
                    "route": model["route"],
                    "title": model["title"],
                    "primary_heading": (
                        model["headings"][0]["text"] if model["headings"] else ""
                    ),
                    "heading_count": len(model["headings"]),
                    "link_count": len(model["links"]),
                    "form_count": len(model["forms"]),
                    "visible_components": model["visible_components"],
                    "interaction_types": [
                        item["type"] for item in model["interaction_flow"]
                    ],
                    "page_model_path": str(
                        (pages_root / f"{slug}.json").relative_to(run_root)
                    ),
                    "html_path": str(
                        (pages_root / f"{slug}.html").relative_to(run_root)
                    ),
                }
            )

            for link in model["links"]:
                normalized = normalize_link(
                    final_url,
                    str(link.get("href", "")),
                    same_origin_only=same_origin_only,
                )
                if normalized and normalized not in visited:
                    queue.append(normalized)
        except (
            Exception
        ) as exc:  # pragma: no cover - exercised in integration-style usage
            errors.append({"url": current, "error": str(exc)})

    summary = {
        "source_name": source_name,
        "base_url": base_url,
        "run_label": resolved_run_label,
        "fetch_mode": selected_fetch_mode,
        "browser_command": browser_command or "",
        "playwright_executable_path": playwright_executable_path or "",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "page_count": len(captured_pages),
        "pages": captured_pages,
        "errors": errors,
    }
    write_text(run_root / "summary.json", json.dumps(summary, indent=2) + "\n")
    write_text(run_root / "report.md", render_capture_report(summary))
    promoted = promote_patterns(summary, run_root)

    latest_pages_root = target_root / "pages"
    remove_path(latest_pages_root)
    shutil.copytree(pages_root, latest_pages_root)
    for name in [
        "summary.json",
        "report.md",
        "patterns.json",
        "patterns.md",
        "ontology-candidates.json",
    ]:
        source_path = run_root / name
        if source_path.exists():
            write_text(target_root / name, read_text(source_path))
    write_text(target_root / "latest-run.txt", resolved_run_label + "\n")
    summary["promoted_patterns"] = promoted
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture and compare behavioral evidence from configured framework demo sources."
    )
    parser.add_argument(
        "action", nargs="?", choices=["capture", "diff", "import"], default="capture"
    )
    parser.add_argument(
        "--source-root",
        required=True,
        help="Knowledge source root containing .mtafiti/viewflow-stack-manifest.json",
    )
    parser.add_argument(
        "--source-name", required=True, help="Behavioral source name from the manifest."
    )
    parser.add_argument(
        "--fetch-mode",
        choices=["http", "browser", "playwright"],
        help="Capture via direct HTTP, an external headless browser dump command, or a Playwright-backed browser session.",
    )
    parser.add_argument(
        "--browser-command",
        help="Explicit browser dump command template. Use {url} where the URL should be inserted.",
    )
    parser.add_argument(
        "--run-label", help="Optional run label. Defaults to a UTC timestamp."
    )
    parser.add_argument("--baseline-run", help="Baseline run label for diff mode.")
    parser.add_argument("--candidate-run", help="Candidate run label for diff mode.")
    parser.add_argument(
        "--repo-root",
        help="Repository root used by import mode. Defaults to this repository.",
    )
    args = parser.parse_args()

    source_root = Path(args.source_root).expanduser().resolve()
    manifest = load_framework_stack_manifest(source_root)
    source_config = select_behavioral_source(manifest, args.source_name)
    output_root = source_root / ".mtafiti" / "behavioral-captures"

    if args.action == "diff":
        if not args.baseline_run or not args.candidate_run:
            parser.error("diff mode requires --baseline-run and --candidate-run")
        diff = diff_capture_runs(
            source_root, args.source_name, args.baseline_run, args.candidate_run
        )
        print(json.dumps(diff, indent=2))
        return 0

    if args.action == "import":
        repo_root = (
            Path(args.repo_root).expanduser().resolve()
            if args.repo_root
            else Path(__file__).resolve().parents[2]
        )
        imported = import_promoted_patterns(source_root, source_config, repo_root)
        print(json.dumps(imported, indent=2))
        return 0

    summary = capture_behavioral_source(
        source_config,
        output_root,
        fetch_mode=args.fetch_mode,
        browser_command=args.browser_command,
        run_label=args.run_label,
    )
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k != "promoted_patterns"}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
