from pathlib import Path


def test_downloadmanagerlocal_modules_do_not_call_private_helpers():
    repo = Path(__file__).resolve().parents[2]
    plugin_dir = repo / "plugins.v2" / "downloadmanagerlocal"
    module_paths = [
        plugin_dir / "modules" / "transfer.py",
        plugin_dir / "modules" / "iyuu.py",
        plugin_dir / "modules" / "recheck.py",
    ]

    offenders = []
    for path in module_paths:
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            if "plugin.__get_" in line:
                offenders.append(f"{path.relative_to(repo)}:{line_no}:{line.strip()}")

    assert offenders == []
