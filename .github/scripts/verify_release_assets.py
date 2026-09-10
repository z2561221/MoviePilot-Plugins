#!/usr/bin/env python3
"""Verify a published plugin ZIP; exit 3 only for an explicitly allowed 404."""

from __future__ import annotations

import argparse
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class VerificationError(ValueError):
    """A release cannot be treated as complete or safely absent."""


def request_json(path: str, token: str, *, allow_missing: bool = False):
    """Read GitHub metadata, distinguishing an absent release from API errors."""
    request = Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "MoviePilot-Plugin-Release",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except HTTPError as error:
        status = error.code
        error.close()
        if status == 404 and allow_missing:
            return None
        raise VerificationError(f"GitHub API returned HTTP {status}") from None
    except (URLError, TimeoutError):
        raise VerificationError("GitHub API request did not complete") from None
    except (ValueError, UnicodeError):
        raise VerificationError("GitHub API returned invalid JSON") from None


def validate_release(release: dict, assets: list, tag: str, asset_name: str) -> None:
    """Require the published tag/title and one fully uploaded, nonempty ZIP."""
    if (
        release.get("tag_name") != tag
        or release.get("name") != tag
        or release.get("draft") is not False
        or release.get("prerelease") is not False
    ):
        raise VerificationError("Release tag, title or publication state is invalid")
    if not isinstance(assets, list) or len(assets) != 1:
        raise VerificationError("Release must contain exactly one ZIP asset")
    asset = assets[0]
    if not isinstance(asset, dict):
        raise VerificationError("Release asset metadata is invalid")
    size = asset.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise VerificationError("Release ZIP size is invalid")
    if (
        asset.get("name") != asset_name
        or not asset_name.endswith(".zip")
        or asset.get("state") != "uploaded"
    ):
        raise VerificationError("Release ZIP name or upload state is invalid")


def verify(repo: str, tag: str, asset_name: str, token: str) -> bool:
    """Return false only when the release is absent; reject incomplete releases."""
    base = f"/repos/{repo}"
    release = request_json(
        f"{base}/releases/tags/{quote(tag, safe='')}", token, allow_missing=True
    )
    if release is None:
        return False
    if (
        not isinstance(release, dict)
        or not isinstance(release.get("id"), int)
        or isinstance(release.get("id"), bool)
    ):
        raise VerificationError("Release metadata is invalid")
    # Two returned assets already violate the one-ZIP contract. A single
    # returned asset proves this native GitHub page has no further entries.
    assets = request_json(f"{base}/releases/{release['id']}/assets?per_page=2", token)
    validate_release(release, assets, tag, asset_name)
    return True


def main(argv: list[str] | None = None) -> int:
    """Use the workflow token without exposing it in output or command arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--asset", required=True)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args(argv)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Release verification failed: workflow token is not configured")
        return 1
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", args.repo):
        print("Release verification failed: invalid repository")
        return 1
    try:
        if verify(args.repo, args.tag, args.asset, token):
            print(f"Verified {args.tag}: {args.asset}")
            return 0
    except VerificationError as error:
        print(f"Release verification failed: {error}")
        return 1
    print(f"Release {args.tag} does not exist")
    return 3 if args.allow_missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
