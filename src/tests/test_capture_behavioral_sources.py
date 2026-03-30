import importlib.util
import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "capture_behavioral_sources.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _FixtureHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        return


def test_capture_behavioral_source_creates_summary_and_page_models(tmp_path):
    module = _load_module(SCRIPT_PATH, "capture_behavioral_sources")

    site_root = tmp_path / "site"
    site_root.mkdir()
    (site_root / "index.html").write_text(
        """
        <html>
          <head><title>Home</title></head>
          <body>
            <header><nav><a href=\"/workflow/\">Workflow</a></nav></header>
            <main>
              <h1>Home Dashboard</h1>
              <section><a href=\"https://example.com/offsite\">External</a></section>
            </main>
          </body>
        </html>
        """.strip(),
        encoding="utf-8",
    )
    workflow_dir = site_root / "workflow"
    workflow_dir.mkdir()
    (workflow_dir / "index.html").write_text(
        """
        <html>
          <head><title>Workflow</title></head>
          <body>
            <main>
              <h1>Shipment Workflow</h1>
              <form action=\"/submit/\" method=\"post\">
                <input name=\"sample_id\" type=\"text\" />
                <button type=\"submit\">Start</button>
              </form>
            </main>
          </body>
        </html>
        """.strip(),
        encoding="utf-8",
    )

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        lambda *args, **kwargs: _FixtureHandler(
            *args, directory=str(site_root), **kwargs
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        source_config = {
            "name": "demo-site",
            "url": f"http://127.0.0.1:{server.server_port}/",
            "capture_seed_paths": ["/"],
            "same_origin_only": True,
            "max_capture_pages": 5,
        }
        output_root = tmp_path / "captures"
        summary = module.capture_behavioral_source(
            source_config,
            output_root,
            run_label="run-a",
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    capture_root = output_root / "demo-site"
    assert summary["page_count"] == 2
    assert (capture_root / "summary.json").exists()
    assert (capture_root / "report.md").exists()

    report = (capture_root / "report.md").read_text(encoding="utf-8")
    assert "Home Dashboard" in report
    assert "Shipment Workflow" in report
    assert (capture_root / "patterns.json").exists()
    assert (capture_root / "ontology-candidates.json").exists()
    assert (capture_root / "runs" / "run-a" / "summary.json").exists()
    assert (capture_root / "latest-run.txt").read_text(
        encoding="utf-8"
    ).strip() == "run-a"

    workflow_model = json.loads(
        (capture_root / "pages" / "workflow.json").read_text(encoding="utf-8")
    )
    assert workflow_model["route"] == "/workflow/"
    assert workflow_model["forms"][0]["method"] == "post"
    assert workflow_model["interaction_flow"][0]["type"] == "form-submit"

    patterns = json.loads((capture_root / "patterns.json").read_text(encoding="utf-8"))
    assert any(
        item["layout_type"] == "workflow_form" for item in patterns["page_patterns"]
    )
    assert any(
        item["to"] == "/workflow/"
        for item in patterns["ontology_candidates"]["navigation"]
    )


def test_load_manifest_and_select_source(tmp_path):
    module = _load_module(SCRIPT_PATH, "capture_behavioral_sources")
    manifest_root = tmp_path / ".mtafiti"
    manifest_root.mkdir(parents=True)
    manifest_path = manifest_root / "viewflow-stack-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "behavioral_sources": [
                    {
                        "name": "demo-site",
                        "url": "https://demo.example.test/",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    manifest = module.load_framework_stack_manifest(tmp_path)
    source = module.select_behavioral_source(manifest, "demo-site")
    assert source["url"] == "https://demo.example.test/"


def test_fetch_html_browser_uses_external_command(monkeypatch, tmp_path):
    module = _load_module(SCRIPT_PATH, "capture_behavioral_sources")

    def fake_run(command, capture_output, text, timeout, check):
        assert "http://demo.test/" in command
        return SimpleNamespace(
            returncode=0,
            stdout="<html><head><title>Browser</title></head><body><h1>Rendered</h1></body></html>",
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    html, final_url = module.fetch_html(
        "http://demo.test/",
        fetch_mode="browser",
        browser_command="fake-browser --dump-dom {url}",
    )
    assert "Rendered" in html
    assert final_url == "http://demo.test/"


def test_import_promoted_patterns_copies_latest_capture_into_repo(tmp_path):
    module = _load_module(SCRIPT_PATH, "capture_behavioral_sources")
    source_root = tmp_path / "knowledge-src"
    capture_root = source_root / ".mtafiti" / "behavioral-captures" / "demo-site"
    capture_root.mkdir(parents=True)
    (capture_root / "patterns.json").write_text(
        json.dumps({"page_patterns": [], "ontology_candidates": {}}),
        encoding="utf-8",
    )
    (capture_root / "ontology-candidates.json").write_text(
        json.dumps({"ui": []}),
        encoding="utf-8",
    )
    (capture_root / "latest-run.txt").write_text("run-a\n", encoding="utf-8")

    repo_root = tmp_path / "repo"
    imported = module.import_promoted_patterns(
        source_root,
        {
            "name": "demo-site",
            "url": "https://demo.example.test/",
            "type": "demo-site",
            "frameworks": ["viewflow", "django-material"],
        },
        repo_root,
    )

    imported_root = repo_root / "analysis" / "behavioral_patterns" / "demo-site"
    assert imported["latest_run"] == "run-a"
    assert (imported_root / "patterns.json").exists()
    assert (imported_root / "ontology-candidates.json").exists()
    manifest = json.loads(
        (imported_root / "source-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["frameworks"] == ["viewflow", "django-material"]
    assert manifest["source_name"] == "demo-site"


def test_diff_capture_runs_detects_route_and_component_changes(tmp_path):
    module = _load_module(SCRIPT_PATH, "capture_behavioral_sources")
    source_root = tmp_path / "knowledge-src"
    target_root = source_root / ".mtafiti" / "behavioral-captures" / "demo-site"
    baseline_root = target_root / "runs" / "run-a"
    candidate_root = target_root / "runs" / "run-b"
    (baseline_root / "pages").mkdir(parents=True)
    (candidate_root / "pages").mkdir(parents=True)

    baseline_summary = {
        "source_name": "demo-site",
        "page_count": 1,
        "pages": [
            {
                "route": "/workflow/",
                "page_model_path": "pages/workflow.json",
            }
        ],
    }
    candidate_summary = {
        "source_name": "demo-site",
        "page_count": 2,
        "pages": [
            {
                "route": "/workflow/",
                "page_model_path": "pages/workflow.json",
            },
            {
                "route": "/new/",
                "page_model_path": "pages/new.json",
            },
        ],
    }
    (baseline_root / "summary.json").write_text(
        json.dumps(baseline_summary), encoding="utf-8"
    )
    (candidate_root / "summary.json").write_text(
        json.dumps(candidate_summary), encoding="utf-8"
    )
    (baseline_root / "pages" / "workflow.json").write_text(
        json.dumps(
            {
                "route": "/workflow/",
                "title": "Workflow",
                "headings": [{"level": "h1", "text": "Before"}],
                "visible_components": ["main"],
                "interaction_flow": [],
            }
        ),
        encoding="utf-8",
    )
    (candidate_root / "pages" / "workflow.json").write_text(
        json.dumps(
            {
                "route": "/workflow/",
                "title": "Workflow Updated",
                "headings": [{"level": "h1", "text": "After"}],
                "visible_components": ["form", "main"],
                "interaction_flow": [{"type": "form-submit"}],
            }
        ),
        encoding="utf-8",
    )
    (candidate_root / "pages" / "new.json").write_text(
        json.dumps(
            {
                "route": "/new/",
                "title": "New",
                "headings": [],
                "visible_components": ["main"],
                "interaction_flow": [],
            }
        ),
        encoding="utf-8",
    )

    diff = module.diff_capture_runs(source_root, "demo-site", "run-a", "run-b")
    assert diff["added_routes"] == ["/new/"]
    assert diff["changed_pages"][0]["route"] == "/workflow/"
    assert diff["changed_pages"][0]["components_added"] == ["form"]
    assert diff["changed_pages"][0]["interactions_added"] == ["form-submit"]
    assert (target_root / "diffs" / "run-a-to-run-b.json").exists()
