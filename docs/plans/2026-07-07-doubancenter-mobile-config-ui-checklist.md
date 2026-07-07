# DoubanCenter Mobile Config UI Checklist

Branch: `worldlinefix/doubancenter`
Verification baseline: `pnpm build` from `plugins.v2/doubancenter`
MP local repository: offline; do not sync, install, reload, or call MP runtime validation APIs.

## Execution Rules

- Work only on `worldlinefix/doubancenter`; never edit on `main`.
- Keep unrelated untracked files out of commits.
- Commit each verified work unit and record the hash below.
- Never commit when required verification fails.
- Never push, merge, amend, change version metadata, or sync to the MP local repository.

## Checklist

- [x] 1. Prepare branch and boundaries
  - accept: current branch is `worldlinefix/doubancenter`; unrelated untracked files are identified and excluded from this work.
  - verify: `git branch --show-current`; `git status --short`
  - evidence: branch switched to `worldlinefix/doubancenter`; status only shows pre-existing untracked docs/plans entries.
  - commit: `329c80c`

- [x] 2. Capture the mobile shell mismatch before editing
  - accept: static check reports DoubanCenter mobile config still contains full-screen shell overrides that Download Center does not use.
  - verify: `Select-String -Path plugins.v2/doubancenter/src/components/Config.vue -Pattern "width: 100%; height: 100%; padding: 0|height: 100dvh|border-radius: 0|border: none|min-width: 86px|min-width: 80px"`
  - evidence: pre-fix check matched `width: 100%; height: 100%; padding: 0`, `height: 100dvh`, `border-radius: 0`, `border: none`, `min-width: 86px`, and `min-width: 80px` in `Config.vue`.
  - commit:

- [x] 3. Align DoubanCenter mobile config shell with Download Center
  - accept: `@media (max-width: 760px)` keeps the standard modal shell: `width: min(100%, calc(100vw - 16px)); padding: 4px`, `height: min(860px, calc(100dvh - 16px))`, 96px nav items, 8px/12px nav padding, 6px/12px subtab padding; no full-screen `100dvh`, no `border-radius: 0`, no `border: none`, no extra 480px nav shrink.
  - verify: `git diff -- plugins.v2/doubancenter/src/components/Config.vue`
  - evidence: post-fix static check found no full-screen shell overrides; matched the standard modal width, modal height, 96px nav items, 8px/12px nav padding, and 6px/12px subtab padding.
  - commit:

- [x] 4. Build DoubanCenter frontend assets
  - accept: build exits 0 and `plugins.v2/doubancenter/dist/assets/remoteEntry.js` exists after the build.
  - verify: `pnpm build` from `plugins.v2/doubancenter`; `Test-Path plugins.v2/doubancenter/dist/assets/remoteEntry.js`
  - evidence: bundled `pnpm.cmd build` exited 0 with Vite `built in 1.17s`; `Test-Path plugins.v2/doubancenter/dist/assets/remoteEntry.js` returned `True`. First plain `pnpm build` failed because shell PATH did not contain `node`; rerun used the Codex bundled Node/Pnpm path.
  - commit:

- [ ] 5. Final offline diff review
  - accept: diff contains only this checklist, DoubanCenter `Config.vue`, and necessary DoubanCenter build assets; no version metadata, no MP local repository sync, no push, no merge.
  - verify: `git diff --stat`; `git diff --name-only`; `git status --short`
  - evidence:
  - commit:
