"""Release recovery must distinguish absent versions from incomplete uploads."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / ".github/scripts/verify_release_assets.py"
SPEC = importlib.util.spec_from_file_location("verify_release_assets", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)
TAG = "Example_v3.0.1"
ASSET = "example_v3.0.1.zip"
RELEASE = {"id": 12, "tag_name": TAG, "name": TAG, "draft": False, "prerelease": False}
UPLOADED = {"name": ASSET, "state": "uploaded", "size": 1024}


def test_accepts_complete_immutable_release():
    """A valid historical release is safe to skip without rewriting it."""
    checker.validate_release(RELEASE, [UPLOADED], TAG, ASSET)


@pytest.mark.parametrize(
    "assets",
    [[], [UPLOADED, UPLOADED], [{**UPLOADED, "size": 0}],
     [{**UPLOADED, "state": "starter"}], [{**UPLOADED, "name": "wrong.zip"}],
     [{**UPLOADED, "size": True}], [None]],
)
def test_rejects_incomplete_or_wrong_assets(assets):
    """Partial uploads and extra or mismatched assets cannot produce a green run."""
    with pytest.raises(checker.VerificationError):
        checker.validate_release(RELEASE, assets, TAG, ASSET)


@pytest.mark.parametrize(
    "change", [{"draft": True}, {"prerelease": True}, {"tag_name": "wrong"},
               {"name": "wrong"}],
)
def test_rejects_unpublished_or_mismatched_release(change):
    """Drafts and wrong identities are failures, not missing releases."""
    with pytest.raises(checker.VerificationError):
        checker.validate_release({**RELEASE, **change}, [UPLOADED], TAG, ASSET)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_api_errors_never_become_missing(monkeypatch, status):
    """Authentication, rate limits and server failures must block publication."""
    def fail(*_args, **_kwargs):
        raise HTTPError("https://api.github.com/test", status, "failure", {}, None)

    monkeypatch.setattr(checker, "urlopen", fail)
    with pytest.raises(checker.VerificationError, match=f"HTTP {status}"):
        checker.request_json("/test", "test-token", allow_missing=True)


def test_only_explicit_release_404_is_missing(monkeypatch):
    """A missing asset endpoint is not permission to create another release."""
    def fail(*_args, **_kwargs):
        raise HTTPError("https://api.github.com/test", 404, "missing", {}, None)

    monkeypatch.setattr(checker, "urlopen", fail)
    assert checker.request_json("/test", "test-token", allow_missing=True) is None
    with pytest.raises(checker.VerificationError, match="HTTP 404"):
        checker.request_json("/test", "test-token")


@pytest.mark.parametrize("error", [URLError("private-route"), TimeoutError()])
def test_network_errors_are_sanitized(monkeypatch, error):
    """Transport failures cannot expose connection details or allow a release."""
    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(checker, "urlopen", fail)
    with pytest.raises(checker.VerificationError, match="did not complete"):
        checker.request_json("/test", "test-token", allow_missing=True)


def test_reads_asset_endpoint_with_a_bounded_count(monkeypatch):
    """Use the asset endpoint, even if embedded release assets are absent."""
    paths = []

    def respond(request, **_kwargs):
        paths.append(request.full_url)
        data = [UPLOADED] if "/assets?" in request.full_url else RELEASE
        return io.BytesIO(json.dumps(data).encode())

    monkeypatch.setattr(checker, "urlopen", respond)
    assert checker.verify("owner/repo", TAG, ASSET, "test-token") is True
    assert paths[-1].endswith("/releases/12/assets?per_page=2")


@pytest.mark.parametrize("allow_missing, expected", [(False, 1), (True, 3)])
def test_cli_distinguishes_preflight_from_post_upload(monkeypatch, allow_missing, expected):
    """Only the preflight may return the workflow's explicit missing sentinel."""
    monkeypatch.setenv("GH_TOKEN", "test-token")
    monkeypatch.setattr(checker, "verify", lambda *_args: False)
    arguments = ["--repo", "owner/repo", "--tag", TAG, "--asset", ASSET]
    if allow_missing:
        arguments.append("--allow-missing")
    assert checker.main(arguments) == expected


def test_incomplete_release_is_fatal_even_during_preflight(monkeypatch):
    """An existing release missing its ZIP must never take the creation branch."""
    def fail(*_args):
        raise checker.VerificationError("Release ZIP is missing")

    monkeypatch.setenv("GH_TOKEN", "test-token")
    monkeypatch.setattr(checker, "verify", fail)
    assert checker.main([
        "--repo", "owner/repo", "--tag", TAG, "--asset", ASSET, "--allow-missing"
    ]) == 1
