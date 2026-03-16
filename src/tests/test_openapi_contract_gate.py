import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "check_openapi_contract.py"


def _load_gate_module():
    spec = importlib.util.spec_from_file_location("check_openapi_contract", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_openapi_contract_gate_script_passes_for_current_repo():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_normalize_django_path_converts_path_parameters():
    module = _load_gate_module()
    assert (
        module.normalize_django_path(
            "api/v1/orchestration/runs/<uuid:run_id>/transition"
        )
        == "/api/v1/orchestration/runs/{run_id}/transition"
    )


def test_extract_openapi_paths_and_schemas_from_snippet():
    module = _load_gate_module()
    snippet = """
paths:
  /api/v1/assets:
    get: {}
  /api/v1/assets/{asset_id}:
    get: {}
components:
  schemas:
    DataAsset:
      type: object
    Error:
      type: object
"""
    assert module.extract_openapi_paths(snippet) == {
        "/api/v1/assets",
        "/api/v1/assets/{asset_id}",
    }
    assert module.extract_schema_names(snippet) == {"DataAsset", "Error"}
