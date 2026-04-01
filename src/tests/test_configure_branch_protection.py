import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "configure_branch_protection.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "configure_branch_protection",
        SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules["configure_branch_protection"] = module
    spec.loader.exec_module(module)
    return module


def test_build_branch_protection_payload_uses_required_checks_contract():
    module = _load_module()

    payload = module.build_branch_protection_payload(
        [
            "docs-gate",
            "src-tests (shard 0/4)",
            "performance-baseline-tests",
        ]
    )

    assert payload["required_status_checks"] == {
        "strict": True,
        "contexts": [
            "docs-gate",
            "src-tests (shard 0/4)",
            "performance-baseline-tests",
        ],
    }
    assert payload["enforce_admins"] is True
    reviews = payload["required_pull_request_reviews"]

    assert reviews["required_approving_review_count"] == 0
    assert reviews["dismiss_stale_reviews"] is False
    assert payload["required_conversation_resolution"] is False


def test_build_repository_settings_payload_enforces_auto_squash_contract():
    module = _load_module()

    payload = module.build_repository_settings_payload()

    assert payload == {
        "allow_squash_merge": True,
        "allow_merge_commit": False,
        "allow_rebase_merge": False,
        "allow_auto_merge": True,
        "delete_branch_on_merge": True,
    }
