# DownloadManagerLocal Plugin Standard Completion Phased Plan

## Goal

Finish the full DownloadManagerLocal plugin refactor so the whole plugin matches
the MoviePilot plugin maintenance standard, while keeping the current UI
visually and behaviorally unchanged.

The existing 2026-07-02 backend refactor is treated as useful prior work, not as
proof of completion. This plan closes the remaining gaps found in the current
state:

- `plugins.v2/downloadmanagerlocal/__init__.py` still contains non-trivial
  business logic and is about 739 lines.
- Static AST audit found public docstring gaps in the plugin package.
- The current service layer still contains facade-style boundaries over legacy
  `modules/` implementations.
- Frontend standardization has already landed and must be preserved, not
  redesigned.
- MP local repository install/reload/runtime validation must be part of the
  completion evidence.

## Source Documents

- `D:/AIGC/MoviePilot/AGENTS.md`
- `D:/AIGC/MoviePilot/.agents/docs/moviepilot-plugin-maintenance-standard.md`
- `D:/AIGC/MoviePilot/.agents/skills/create-moviepilot-plugin/SKILL.md`
- `D:/AIGC/MoviePilot/.agents/skills/moviepilot-plugin-ui-design/SKILL.md`
- `D:/AIGC/.cc-switch/skills/spec-to-goal-plan/SKILL.md`
- `D:/AIGC/.cc-switch/skills/test-driven-development/SKILL.md`
- `docs/plans/2026-07-02-downloadmanagerlocal-backend-refactor-phased-plan.md`
- `docs/plans/2026-07-02-downloadmanagerlocal-backend-refactor-progress.json`
- Current user direction: complete the whole plugin refactor by plugin standard;
  keep UI visually and behaviorally unchanged.

## Execution Rules

- Work from:
  `C:/Users/ZhaoYu/.config/superpowers/worktrees/MoviePilot-Plugins/downloadmanagerlocal-backend-standard`
- Use the current long-lived branch `worldlinefix/downloadmanagerlocal`.
- Run baseline smoke checks before each work unit.
- Work only on the current task in this plan and progress file.
- Follow TDD for implementation changes: add or tighten a failing static/runtime
  check before changing production code.
- Commit each verified work unit and record the commit hash in the progress
  file. Never commit when required verification fails.
- Never push, merge, amend, release, or restart MoviePilot.
- Advance after verified phases without asking the user.
- Preserve unrelated user changes. If unrelated changes cannot be separated,
  stop and report.

## Progress File

`docs/plans/2026-07-04-downloadmanagerlocal-plugin-standard-completion-progress.json`

The executing agent may only update status, verification, commit, decision log,
turn log, and residual risk fields. It must not rewrite task definitions or
acceptance criteria while executing.

## Hard UI-Invariance Gate

Allowed UI-related activity:

- Run frontend build commands.
- Verify generated federation assets and remoteEntry references.
- Sync already-built assets to the MP local plugin repository.

Forbidden without explicit new user direction:

- Changing visible UI text, layout, styling, component behavior, or interactions.
- Changing `frontend/src/**`, `frontend/index.html`, `frontend/vite.config.js`,
  `frontend/package.json`, lock files, or frontend dependency declarations.
- Changing Vue exposes or `get_render_mode()` semantics.

Every implementation task must run this gate:

```powershell
git diff --name-only -- plugins.v2/downloadmanagerlocal/frontend/src plugins.v2/downloadmanagerlocal/frontend/index.html plugins.v2/downloadmanagerlocal/frontend/vite.config.js plugins.v2/downloadmanagerlocal/frontend/package.json plugins.v2/downloadmanagerlocal/frontend/package-lock.json plugins.v2/downloadmanagerlocal/frontend/pnpm-lock.yaml
```

The command must print no paths.

## Baseline Smoke Checks

Use the bundled Python runtime when `python` points to the Windows Store alias:

```powershell
git status --short --branch
& 'C:/Users/ZhaoYu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m compileall plugins.v2/downloadmanagerlocal
$files = Get-ChildItem -LiteralPath 'tests/static' -Filter 'test_downloadmanagerlocal_*.py' | ForEach-Object { $_.FullName }; & 'C:/Users/ZhaoYu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m pytest --confcutdir=tests/static @files
```

If a command is unavailable, record the exact blocker and run the closest
available narrower check. Do not claim completion from a skipped broad check.

## Implementation Surface Map

Primary backend:

- `plugins.v2/downloadmanagerlocal/__init__.py`
- `plugins.v2/downloadmanagerlocal/controller/*.py`
- `plugins.v2/downloadmanagerlocal/service/*.py`
- `plugins.v2/downloadmanagerlocal/adapter/*.py`
- `plugins.v2/downloadmanagerlocal/model/*.py`
- `plugins.v2/downloadmanagerlocal/modules/*.py`
- `plugins.v2/downloadmanagerlocal/utils/*.py`
- `plugins.v2/downloadmanagerlocal/iyuu_helper.py`
- `plugins.v2/downloadmanagerlocal/ai_spec/plugin_context.md`

Frontend/runtime assets to preserve:

- `plugins.v2/downloadmanagerlocal/frontend/**`
- `plugins.v2/downloadmanagerlocal/dist/assets/**`

Tests:

- `tests/static/test_downloadmanagerlocal_*.py`
- New static tests may be added under `tests/static/`.

MP local validation:

- Source sync script: `scripts/sync_to_mp_local.py`
- MP local plugin repository:
  `Z:/moviepilot-v2/config/local plugins`
- Runtime API host/key are read from:
  `D:/AIGC/MoviePilot/.agents/.local/moviepilot_cli/config`

## Architecture Target

```text
DownloadManagerLocal (_PluginBase entry)
  -> controller/
       route declaration and API response shaping
  -> service/
       lifecycle, scheduler, event, transfer, iyuu, rename, recheck,
       archive, site-tag, diagnostics orchestration
  -> adapter/
       MoviePilot helpers, downloader access, site/config/database lookup,
       HTTP and external APIs
  -> model/
       config defaults, state keys, DTO-style structures, enums/constants
  -> utils/
       stateless parsing, masking, path, tracker, torrent helper functions
  -> frontend/ and dist/
       Vue federation source and built assets, unchanged in behavior
```

`modules/` must not remain a second service layer. By the end of this plan it
must either be removed where safe or reduced to documented compatibility shims
that re-export service implementations without business decisions.

## Phase 1: Completion Baseline And Failing Gates

Goal: Prove the remaining standard gaps with executable checks before changing
implementation code.

Surfaces:

- `tests/static/test_downloadmanagerlocal_standard_completion.py`
- `docs/plans/2026-07-04-downloadmanagerlocal-plugin-standard-completion-progress.json`
- `plugins.v2/downloadmanagerlocal/ai_spec/plugin_context.md`

Tasks:

1.1 Record baseline and create standard-completion audit tests.

- Acceptance:
  - A static test records and enforces the target standard gates:
    public docstring gaps must be zero, entrypoint business-heavy methods must
    be thin or extracted, and `modules/` must not own service decisions at the
    final state.
  - The test is first run and fails for the current known standard gap.
  - Baseline smoke checks are recorded in the progress file.
  - UI-invariance gate prints no paths.
- Verification:
  - Red run:
    `pytest --confcutdir=tests/static tests/static/test_downloadmanagerlocal_standard_completion.py`
  - Baseline smoke checks.
  - UI-invariance gate.
- Commit boundary: commit the failing-gate tests and progress evidence after the
  red failure is recorded.

1.2 Update plugin context with final-standard target.

- Acceptance:
  - `ai_spec/plugin_context.md` documents the final target boundaries,
    remaining gaps, no-UI invariant, and MP local validation chain.
  - The document does not claim completion before implementation evidence.
- Verification:
  - `compileall` exits 0.
  - UI-invariance gate prints no paths.
- Commit boundary: commit context update.

Phase acceptance:

- Standard gaps are represented by tests or explicit progress evidence.
- No UI source path is modified.

## Phase 2: Entrypoint Standardization

Goal: Make `__init__.py` a plugin contract entrypoint with lifecycle,
extension points, event registration, and thin delegation only.

Surfaces:

- `plugins.v2/downloadmanagerlocal/__init__.py`
- `plugins.v2/downloadmanagerlocal/service/lifecycle.py`
- `plugins.v2/downloadmanagerlocal/service/events.py`
- `plugins.v2/downloadmanagerlocal/service/recheck.py`
- Existing service modules as appropriate
- `tests/static/test_downloadmanagerlocal_standard_completion.py`

Tasks:

2.1 Extract recheck runtime business logic.

- Acceptance:
  - `check_recheck`, paused seed sweep, and seed-ready predicates are owned by
    `service/recheck.py` or an equivalent service module.
  - The entrypoint exposes only thin compatibility delegation for scheduler
    targets if required.
  - Existing seed recheck and transfer retry behavior tests pass.
- Verification:
  - Standard completion test moves past the recheck entrypoint assertions.
  - Baseline smoke checks.
  - UI-invariance gate.
- Commit boundary: commit recheck extraction.

2.2 Extract event-delay scheduling logic.

- Acceptance:
  - `TransferComplete` handling delegates decision and scheduler setup to a
    service boundary.
  - The entrypoint event method contains only guard/delegation code.
  - Delayed transfer behavior remains compatible.
- Verification:
  - Baseline smoke checks.
  - Focused transfer retry/event static tests.
  - UI-invariance gate.
- Commit boundary: commit event scheduling extraction.

2.3 Slim entrypoint imports and compatibility wrappers.

- Acceptance:
  - `__init__.py` line count is at or below 520 lines unless progress records a
    justified compatibility exception.
  - Public wrappers that remain are documented and thin.
  - The entrypoint no longer imports external clients or helpers that belong in
    adapter/service modules.
- Verification:
  - Standard completion test passes its entrypoint section.
  - Baseline smoke checks.
  - `git diff --check` exits 0.
  - UI-invariance gate.
- Commit boundary: commit entrypoint slimming.

Phase acceptance:

- `__init__.py` owns plugin contract and thin delegation only.
- Runtime API route, service, and event behavior remain compatible.

## Phase 3: Service And Module Boundary Completion

Goal: Finish the backend layer split so service owns orchestration, adapter owns
external calls, model owns structured state, and modules are no longer a legacy
business layer.

Surfaces:

- `plugins.v2/downloadmanagerlocal/service/*.py`
- `plugins.v2/downloadmanagerlocal/modules/*.py`
- `plugins.v2/downloadmanagerlocal/adapter/*.py`
- `plugins.v2/downloadmanagerlocal/model/*.py`
- `tests/static/test_downloadmanagerlocal_service_boundaries.py`
- `tests/static/test_downloadmanagerlocal_standard_completion.py`

Tasks:

3.1 Move remaining orchestration from `modules/transfer.py` and related rename
helpers into service-owned modules.

- Acceptance:
  - Transfer orchestration and post-transfer rename/tag/recheck coordination
    live under `service/`.
  - Any retained `modules/transfer.py` code is a compatibility shim.
  - Transfer and rename regression tests pass.
- Verification:
  - Red/green evidence from standard boundary tests.
  - Baseline smoke checks.
  - UI-invariance gate.
- Commit boundary: commit transfer service migration.

3.2 Move remaining IYUU orchestration into service-owned modules.

- Acceptance:
  - IYUU auto seed, torrent URL resolution orchestration, cache/history writes,
    and post-download rename coordination live under `service/`.
  - External HTTP/site/downloader calls remain behind adapter helpers.
  - IYUU regression tests pass.
- Verification:
  - IYUU focused tests.
  - Baseline smoke checks.
  - UI-invariance gate.
- Commit boundary: commit IYUU service migration.

3.3 Move archive, diagnostics, site-tag, and seed recheck residual logic into
service-owned modules or documented compatibility shims.

- Acceptance:
  - `modules/` contains no unowned business decisions.
  - `utils/` remains stateless.
  - `adapter/` remains the only boundary for MoviePilot/downloader/HTTP access
    where practical.
- Verification:
  - Standard completion test passes service/module boundary section.
  - Baseline smoke checks.
  - `git diff --check` exits 0.
  - UI-invariance gate.
- Commit boundary: commit remaining boundary cleanup.

Phase acceptance:

- The backend directory shape matches the standard responsibilities.
- Legacy compatibility exceptions are documented and tested.

## Phase 4: Docstrings And Static Quality Hard Gate

Goal: Make the plugin pass the docstring and static quality bar required by the
MoviePilot plugin standard.

Surfaces:

- All Python files under `plugins.v2/downloadmanagerlocal`
- `tests/static/test_downloadmanagerlocal_standard_completion.py`

Tasks:

4.1 Add Chinese docstrings to all public classes, public functions, and public
methods.

- Acceptance:
  - AST audit reports `missing_public_docstrings = 0` for plugin package Python
    files, excluding `__pycache__`.
  - Docstrings describe purpose and boundary; they do not narrate trivial
    assignment details.
- Verification:
  - Standard completion docstring test passes public-docstring assertions.
  - Baseline smoke checks.
  - UI-invariance gate.
- Commit boundary: commit public docstrings.

4.2 Add docstrings to all newly introduced or changed private helpers and remove
dead code/imports.

- Acceptance:
  - Newly introduced or changed private helpers have Chinese docstrings.
  - Dead imports and unreachable statements introduced or exposed by this work
    are removed.
  - `git diff --check` exits 0.
- Verification:
  - Baseline smoke checks.
  - Static cleanup tests.
  - UI-invariance gate.
- Commit boundary: commit static cleanup.

Phase acceptance:

- Public docstring gaps are zero.
- Changed private helper documentation is complete.
- Compile/static tests pass.

## Phase 5: Frontend Invariance And Runtime Asset Verification

Goal: Verify the Vue federation frontend remains standard and unchanged in user
experience.

Surfaces:

- `plugins.v2/downloadmanagerlocal/frontend`
- `plugins.v2/downloadmanagerlocal/dist/assets`
- `plugins.v2/downloadmanagerlocal/__init__.py`

Tasks:

5.1 Verify frontend source and federation contract.

- Acceptance:
  - `frontend/src/components/Config.vue`, `Page.vue`, and `api.js` still exist.
  - Frontend uses injected `api` helpers and no direct fallback API token.
  - `get_render_mode()` returns `("vue", "dist/assets")`.
  - Frontend source diff gate prints no paths.
- Verification:
  - Static grep/AST checks recorded in progress.
  - UI-invariance gate.
- Commit boundary: commit only if verification tests/docs changed.

5.2 Run frontend build and asset reference check.

- Acceptance:
  - `pnpm build` in `plugins.v2/downloadmanagerlocal/frontend` exits 0.
  - `dist/assets/remoteEntry.js` exists.
  - Every JS/CSS file referenced by `remoteEntry.js` exists.
  - If `dist/assets` changes, progress records that the change is generated
    build output from unchanged source.
- Verification:
  - `pnpm build`
  - remoteEntry reference check command.
  - UI-invariance gate.
- Commit boundary: commit generated asset changes only if any appear and the
  build evidence proves they are generated.

Phase acceptance:

- Frontend source and visible behavior remain unchanged.
- Federation assets are buildable and internally consistent.

## Phase 6: MP Local Repository Runtime Closure

Goal: Sync the completed plugin to the MP local repository, reinstall/reload,
and prove the running MoviePilot instance is using the completed plugin.

Surfaces:

- `scripts/sync_to_mp_local.py`
- `Z:/moviepilot-v2/config/local plugins/plugins.v2/downloadmanagerlocal`
- MoviePilot API endpoints
- `Z:/moviepilot-v2/config/logs/moviepilot.log`

Tasks:

6.1 Sync to MP local repository.

- Acceptance:
  - `sync_to_mp_local.py --plugin DownloadManagerLocal --dry-run` lists only
    DownloadManagerLocal, its icon, and package entry.
  - Actual sync exits 0.
  - MP local plugin directory has `frontend/`, `dist/assets/remoteEntry.js`,
    and no stale root `src`, root `vite.config.js`, root `index.html`, or root
    `package.json`.
- Verification:
  - Dry-run output.
  - Sync output.
  - MP local file checks.
- Commit boundary: no repository commit is required for MP local copied files;
  progress evidence must be recorded.

6.2 Install/reload and runtime API validation.

- Acceptance:
  - `GET /api/v1/plugin/install/DownloadManagerLocal` with local repo URL and
    `force=true` returns success.
  - `GET /api/v1/plugin/reload/DownloadManagerLocal` returns success.
  - `/api/v1/plugin/history/DownloadManagerLocal?force=true` reports
    `version=3.2.4`, `plugin_version=3.2.4`, and `history` contains `v3.2.4`
    unless a later explicit release-preparation task changed the version.
  - `/api/v1/plugin/remotes?token=moviepilot` contains
    `/plugin/file/downloadmanagerlocal/dist/assets/remoteEntry.js`.
  - `/api/v1/plugin/form/DownloadManagerLocal` reports `render_mode=vue`.
  - `/api/v1/plugin/DownloadManagerLocal/overview` returns data.
  - Recent `moviepilot.log` has no DownloadManagerLocal-related ERROR or
    Traceback entries after reload.
- Verification:
  - API command outputs recorded in progress without exposing API keys.
  - Log grep output recorded in progress.
- Commit boundary: commit only progress evidence if required; never restart MP.

6.3 Final completion audit.

- Acceptance:
  - All phases and tasks are complete or explicitly skipped by rule.
  - Baseline smoke checks pass.
  - Standard completion tests pass.
  - Frontend source diff gate prints no paths.
  - MP runtime validation is recorded.
  - Residual risks are limited to publish/merge/release actions not requested by
    the user.
- Verification:
  - Baseline smoke checks.
  - `git diff --check`
  - UI-invariance gate.
  - Runtime evidence from 6.2.
- Commit boundary: commit final progress/context updates.

Phase acceptance:

- Win local repository, MP local repository, and running MoviePilot all reflect
  the completed standard refactor.
- No push, merge, release, or restart was performed.

## Failure Modes And Recovery

- Entrypoint extraction changes runtime behavior: restore compatibility wrappers
  and add focused regression tests before continuing.
- Docstring audit is gamed with meaningless text: rewrite docstrings so they
  describe boundary/purpose and rerun the audit.
- `modules/` remains a hidden service layer: keep moving orchestration into
  `service/` or record a narrow compatibility exception with tests.
- UI source changes appear in diff: stop, revert only agent-made UI source
  changes, rerun UI-invariance gate.
- MP API key/auth fails: record the exact non-secret failure and keep working on
  local evidence until API access is available.

## Decision Log

- Decision: Continue on `worldlinefix/downloadmanagerlocal`.
  Reason: Project rules use long-lived per-plugin branches.
  Rejected alternatives: creating a new `codex/*` branch for the same plugin.
  Source: `AGENTS.md` repository workflow.

- Decision: Treat the 2026-07-02 backend plan as prior work, not completion.
  Reason: Current audit still shows entrypoint and docstring gaps.
  Rejected alternatives: declaring backend refactor complete from old progress.
  Source: current AST and entrypoint audit.

- Decision: Keep UI source immutable and verify build/runtime assets.
  Reason: User asked to keep UI unchanged while completing plugin standards.
  Rejected alternatives: UI redesign or text/layout cleanup during backend
  standardization.
  Source: latest user direction and plugin UI design standard.

## /goal Starter

```text
/goal Implement C:/Users/ZhaoYu/.config/superpowers/worktrees/MoviePilot-Plugins/downloadmanagerlocal-backend-standard/docs/plans/2026-07-04-downloadmanagerlocal-plugin-standard-completion-phased-plan.md by following its execution ledger.

Each turn:
1. Read C:/Users/ZhaoYu/.config/superpowers/worktrees/MoviePilot-Plugins/downloadmanagerlocal-backend-standard/docs/plans/2026-07-04-downloadmanagerlocal-plugin-standard-completion-progress.json, then the current task in the plan.
2. Run git status and the baseline smoke checks named in the plan.
3. Work only on the current work unit; keep UI visually and behaviorally unchanged.
4. After verification passes: update progress status/evidence/log only, commit that unit, and record the hash. Never commit on failed verification.
5. Continue through verified phases without asking. Never push, merge, amend, release, or restart MoviePilot.
```
