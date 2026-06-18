from pathlib import Path


def test_downloadmanagerlocal_modules_do_not_call_plugin_private_members():
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
            if "plugin.__" in line and "plugin.__class__" not in line:
                offenders.append(f"{path.relative_to(repo)}:{line_no}:{line.strip()}")

    assert offenders == []
