"""构建清理必须只作用于 Vite 实际输出目录。"""

import shutil
import subprocess
from pathlib import Path

import pytest


_NODE_CHECK = r"""
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const [configFile, sandbox, root, outDir] = process.argv.slice(1);
const source = fs.readFileSync(configFile, 'utf8');
const start = source.indexOf('function cleanFederationArtifacts()');
const end = source.indexOf('\n\nexport default', start);
assert(start >= 0 && end > start);
const guard = value => {
  const relative = path.relative(sandbox, path.resolve(value));
  assert(!path.isAbsolute(relative) && relative !== '..' && !relative.startsWith('..' + path.sep));
};
const context = {resolve: path.resolve};
for (const name of ['rmSync', 'readFileSync', 'writeFileSync', 'existsSync']) {
  context[name] = (value, ...args) => { guard(value); return fs[name](value, ...args); };
}
const plugin = vm.runInNewContext('(' + source.slice(start, end) + ')()', context);
plugin.configResolved({root, build: {outDir}});
plugin.closeBundle();
"""


@pytest.mark.parametrize("absolute", [False, True])
def test_cleanup_follows_the_resolved_output_directory(tmp_path, absolute):
    """相对或绝对 outDir 都只清理自身生成物，保留默认目录与正常资源。"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the build-hook contract")
    project = tmp_path / "project"
    original = project / "dist"
    output = tmp_path / "artifacts"
    for folder in (original, output):
        shared = folder / "assets" / "__federation_shared_vuetify"
        shared.mkdir(parents=True)
        (shared / "sentinel.css").write_text("sentinel", encoding="utf-8")
        (folder / "index.html").write_text("index", encoding="utf-8")
        (folder / "assets" / "remoteEntry.js").write_text("entry  \n", encoding="utf-8")
        (folder / "assets" / "keep.js").write_text("keep", encoding="utf-8")
    repo = Path(__file__).resolve().parents[3]
    config = repo / "plugins.v3/downloadmanagerlocal/frontend/vite.config.js"
    out_dir = str(output) if absolute else "../artifacts"
    subprocess.run(
        [node, "-e", _NODE_CHECK, str(config), str(tmp_path), str(project), out_dir],
        check=True, capture_output=True, text=True,
    )
    assert (original / "assets/__federation_shared_vuetify/sentinel.css").read_text() == "sentinel"
    assert (original / "assets/remoteEntry.js").read_text() == "entry  \n"
    assert (original / "index.html").is_file()
    assert not (output / "assets/__federation_shared_vuetify").exists()
    assert (output / "assets/keep.js").read_text() == "keep"
    assert (output / "index.html").is_file()
    assert (output / "assets/remoteEntry.js").read_text() == "entry\n"
