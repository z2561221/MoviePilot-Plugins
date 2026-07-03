# DownloadManagerLocal Backend Refactor Phased Plan

## Goal

Refactor the DownloadManagerLocal plugin backend to match the MoviePilot plugin maintenance standard while preserving existing runtime behavior and leaving the UI untouched.

This plan is intentionally backend-only. It must not change Vue components, built federation assets, Vite configuration, frontend package metadata, UI text, layout, styling, or interaction behavior.

## Source Documents

- `D:/AIGC/MoviePilot/AGENTS.md`
- `D:/AIGC/MoviePilot/.agents/docs/moviepilot-plugin-maintenance-standard.md`
- `D:/AIGC/MoviePilot/.agents/skills/create-moviepilot-plugin/SKILL.md`
- `D:/AIGC/MoviePilot/MoviePilot-Plugins/docs/Repository_Guide.md`
- `D:/AIGC/MoviePilot/MoviePilot-Plugins/docs/V2_Plugin_Development.md`
- `D:/AIGC/MoviePilot/MoviePilot-Plugins/tests/README.md`
- `D:/AIGC/MoviePilot/MoviePilot-Plugins/plugins.v2/downloadmanagerlocal/__init__.py`
- Latest user constraint: do not touch UI.

## Execution Rules

- Work from `D:/AIGC/MoviePilot/MoviePilot-Plugins`.
- Before execution starts, create a dedicated branch from latest `main`: `codex/refactor/downloadmanagerlocal-backend-standard`.
- Make a clean-start commit before task work if the branch contains only the plan/progress files.
- Commit each verified work unit and record the commit hash in the progress file.
- Never commit when required verification fails.
- Never push, merge, or amend automatically.
- Merging into `main` requires user review and explicit confirmation.
- Advance after each verified task and phase without asking for user confirmation.
- If unrelated worktree changes cannot be separated from this work, stop and report.

## Hard No-UI Gate

The executing agent must not modify these paths:

- `plugins.v2/downloadmanagerlocal/src/**`
- `plugins.v2/downloadmanagerlocal/dist/**`
- `plugins.v2/downloadmanagerlocal/index.html`
- `plugins.v2/downloadmanagerlocal/vite.config.js`
- `plugins.v2/downloadmanagerlocal/package.json`
- `plugins.v2/downloadmanagerlocal/package-lock.json`
- `plugins.v2/downloadmanagerlocal/pnpm-lock.yaml`

The executing agent must not change any UI text, layout, style, component behavior, remote expose, frontend dependency, or built asset. If a backend change appears to require UI changes, stop and report the product/technical decision gap.

Every task acceptance includes this check:

```powershell
git diff --name-only -- plugins.v2/downloadmanagerlocal/src plugins.v2/downloadmanagerlocal/dist plugins.v2/downloadmanagerlocal/index.html plugins.v2/downloadmanagerlocal/vite.config.js plugins.v2/downloadmanagerlocal/package.json plugins.v2/downloadmanagerlocal/package-lock.json plugins.v2/downloadmanagerlocal/pnpm-lock.yaml
```

The command must print no paths.

## Progress File

Progress ledger:

```text
docs/plans/2026-07-02-downloadmanagerlocal-backend-refactor-progress.json
```

The executing agent may only update task status, phase status, verification evidence, commit hashes, decision log entries, turn log entries, and residual risk fields. It must not add, remove, or rewrite tasks, phase goals, acceptance criteria, no-UI gates, or execution rules.

## Baseline Smoke Checks

Run these before starting new backend work in each turn:

```powershell
git status --short --branch
python -m compileall plugins.v2/downloadmanagerlocal
python -m pytest tests/static/test_downloadmanagerlocal_private_helpers.py tests/static/test_downloadmanagerlocal_stability_baseline.py
```

If the Python environment cannot import MoviePilot dependencies, run the static tests that do not require the full host and record the exact blocker. Do not claim backend verification passed without naming the commands that exited 0.

## Implementation Surface Map

Primary plugin source:

- `plugins.v2/downloadmanagerlocal/__init__.py`: current `_PluginBase` entry, config state, lifecycle, API route declarations, services, event hooks, and many delegating wrappers.
- `plugins.v2/downloadmanagerlocal/api.py`: current API handler functions.
- `plugins.v2/downloadmanagerlocal/modules/transfer.py`: transfer, fallback, delayed transfer, pending rename retry, dirty rename scan.
- `plugins.v2/downloadmanagerlocal/modules/iyuu.py`: IYUU service lookup, auto seed, torrent download, URL extraction, cache updates.
- `plugins.v2/downloadmanagerlocal/modules/rename.py`: torrent rename, original-name candidate scoring, retry logic, IYUU source rename reuse.
- `plugins.v2/downloadmanagerlocal/modules/rename_archive.py`: failed rename classification, archive persistence, restore/delete/list/stats.
- `plugins.v2/downloadmanagerlocal/modules/recheck.py`: seed recheck queue persistence, worker loop, seed state predicates.
- `plugins.v2/downloadmanagerlocal/modules/site_tag.py`: tracker/site mapping and tag writes.
- `plugins.v2/downloadmanagerlocal/modules/diagnostics.py`: runtime diagnostics summary.
- `plugins.v2/downloadmanagerlocal/utils/*.py`: pure helpers for config, paths, tracker mapping, sensitive URL masking, torrent adapter access, and name cleanup.
- `plugins.v2/downloadmanagerlocal/iyuu_helper.py`: IYUU API helper.

Backend artifacts that may be created:

- `plugins.v2/downloadmanagerlocal/controller/api.py`
- `plugins.v2/downloadmanagerlocal/service/*.py`
- `plugins.v2/downloadmanagerlocal/adapter/*.py`
- `plugins.v2/downloadmanagerlocal/model/*.py`
- `plugins.v2/downloadmanagerlocal/ai_spec/plugin_context.md`

Tests:

- Existing static regression tests under `tests/static/test_downloadmanagerlocal_*.py`.
- If adding runtime-style tests, prefer `tests/v2/downloadmanagerlocal/` and follow `tests/README.md`.

Metadata:

- `package.v2.json` and `plugins.v2/downloadmanagerlocal/plugin.json` may be updated only in a later release-preparation task, not during pure refactor tasks.
- `plugin_version` may be bumped only once in the release-preparation task if the user asks to publish or merge this cycle.

## Current Observations

- The plugin is V2-only source under `plugins.v2/downloadmanagerlocal`.
- Current `__init__.py` is about 954 lines and still owns many responsibilities beyond `_PluginBase` lifecycle and extension-point declarations.
- Existing backend modules already cover transfer, IYUU, rename, archive, recheck, site tag, diagnostics, and utility helpers.
- Existing tests include static safety and regression coverage for helper privacy, diagnostics, rename archive, seed recheck, transfer retry hook, IYUU regressions, manual retry API, and stability baseline.
- Current Vue federation files exist and are explicitly out of scope.

## Architecture Target

```text
_PluginBase entry (__init__.py)
  -> controller/api.py
       -> service layer
            -> adapter layer for MoviePilot helpers, downloaders, IYUU HTTP, site lookup
            -> model layer for structured payloads and persisted state keys
  -> service scheduler/event hooks
       -> transfer / iyuu / rename / recheck / archive services
  -> utils
       -> stateless parsing, masking, path, tracker, torrent adapter helpers
```

Ownership rules:

- `__init__.py` owns plugin identity, lifecycle, config snapshot, extension-point declarations, service registration, event registration, and thin delegation only.
- `controller/` owns API route lists and response shaping.
- `service/` owns business decisions and orchestration.
- `adapter/` owns MoviePilot helper calls, downloader clients, HTTP, SDK, and site/config lookups.
- `model/` owns structured payloads, constants, enums, and data key definitions.
- `utils/` stays stateless and must not become a second service layer.

## Phase 1: Baseline And Guardrails

Goal: Capture current behavior and harden test gates before refactoring.

Surfaces:

- `tests/static/test_downloadmanagerlocal_*.py`
- `plugins.v2/downloadmanagerlocal/ai_spec/plugin_context.md`
- This progress file

Tasks:

1.1 Record baseline status and no-UI guard.

- Acceptance:
  - `git status --short --branch` output is recorded.
  - Current branch decision is recorded in the progress file.
  - No-UI gate command prints no paths.
  - No plugin source files are changed by this task except optional `ai_spec/plugin_context.md`.
- Verification:
  - `git status --short --branch`
  - no-UI gate command
- Commit boundary: commit baseline docs only if files changed.

1.2 Add or update static guard tests for backend-only refactor boundaries.

- Acceptance:
  - Tests assert DownloadManagerLocal route paths/auth/methods are preserved or explicitly inventoried.
  - Tests assert modules do not call double-underscore plugin private helpers.
  - Tests assert forbidden UI paths are not required by backend checks and remain untouched in the diff.
- Verification:
  - `python -m pytest tests/static/test_downloadmanagerlocal_private_helpers.py tests/static/test_downloadmanagerlocal_stability_baseline.py`
  - no-UI gate command
- Commit boundary: commit guard test updates.

1.3 Create backend context document.

- Acceptance:
  - `plugins.v2/downloadmanagerlocal/ai_spec/plugin_context.md` documents plugin purpose, extension points, API routes, services, event hooks, persisted data keys, critical flows, forbidden UI areas, and validation commands.
  - The context document agrees with this plan and does not mention UI refactor work.
- Verification:
  - `python -m compileall plugins.v2/downloadmanagerlocal`
  - no-UI gate command
- Commit boundary: commit context documentation.

Phase acceptance:

- All Phase 1 tasks are complete.
- Baseline compile and selected static tests exit 0 or exact environment blocker is recorded.
- No forbidden UI path appears in diff.

## Phase 2: Entry Point Slimming

Goal: Reduce `__init__.py` to plugin identity, lifecycle, configuration state, extension-point declarations, and thin delegation without behavior changes.

Surfaces:

- `plugins.v2/downloadmanagerlocal/__init__.py`
- `plugins.v2/downloadmanagerlocal/model/config.py` or equivalent
- `plugins.v2/downloadmanagerlocal/service/lifecycle.py` or equivalent
- Existing backend modules as delegation targets
- Existing tests

Tasks:

2.1 Extract config parsing/default normalization.

- Acceptance:
  - `init_plugin()` delegates config defaulting, safe integer parsing, tracker mapping parsing, and runtime flag normalization to a backend module.
  - Config field names and defaults remain compatible with the current frontend payload.
  - No UI/config form schema changes are made.
- Verification:
  - `python -m compileall plugins.v2/downloadmanagerlocal`
  - `python -m pytest tests/static/test_downloadmanagerlocal_stability_baseline.py tests/static/test_downloadmanagerlocal_iyuu_regressions.py`
  - no-UI gate command
- Commit boundary: commit config extraction.

2.2 Extract service registration construction.

- Acceptance:
  - `get_service()` remains behavior-compatible and still registers the transfer fallback and IYUU service under the same effective conditions.
  - Service IDs, names, triggers, and callable targets remain compatible unless a test proves a bug and the change is documented.
  - `stop_service()` behavior remains compatible.
- Verification:
  - `python -m compileall plugins.v2/downloadmanagerlocal`
  - `python -m pytest tests/static/test_downloadmanagerlocal_seed_recheck.py tests/static/test_downloadmanagerlocal_transfer_retry_hook.py`
  - no-UI gate command
- Commit boundary: commit service registration extraction.

2.3 Reduce wrapper clutter while keeping public compatibility.

- Acceptance:
  - Public/static compatibility helpers currently used by modules or tests remain available.
  - Delegating wrappers that must stay for external compatibility are grouped and documented.
  - `__init__.py` no longer imports unused heavy dependencies made unnecessary by extracted modules.
- Verification:
  - `python -m compileall plugins.v2/downloadmanagerlocal`
  - `python -m pytest tests/static/test_downloadmanagerlocal_private_helpers.py tests/static/test_downloadmanagerlocal_stability_baseline.py`
  - no-UI gate command
- Commit boundary: commit entry slimming.

Phase acceptance:

- `__init__.py` owns only plugin contract and thin delegation.
- Existing API paths, service behavior, and event hook behavior remain compatible.
- No forbidden UI path appears in diff.

## Phase 3: API Controller Boundary

Goal: Move API route declaration and response shaping into a controller boundary while preserving all paths, auth modes, methods, summaries, and response schemas.

Surfaces:

- `plugins.v2/downloadmanagerlocal/__init__.py`
- `plugins.v2/downloadmanagerlocal/api.py`
- `plugins.v2/downloadmanagerlocal/controller/api.py`
- `tests/static/test_downloadmanagerlocal_manual_retry_api.py`
- `tests/static/test_downloadmanagerlocal_diagnostics.py`
- `tests/static/test_downloadmanagerlocal_rename_archive.py`

Tasks:

3.1 Introduce API route builder.

- Acceptance:
  - `get_api()` delegates to a route builder.
  - Routes are exactly preserved for:
    - `/downloaders`
    - `/rename_history`
    - `/overview`
    - `/diagnostics`
    - `/retry_renames`
    - `/retry_rename`
    - `/delete_rename_history`
    - `/rename_archive`
    - `/restore_rename_archive`
    - `/delete_rename_archive`
    - `/recovery_torrent`
    - `/sites`
  - All frontend-facing routes keep `auth: "bear"`.
- Verification:
  - `python -m compileall plugins.v2/downloadmanagerlocal`
  - `python -m pytest tests/static/test_downloadmanagerlocal_manual_retry_api.py tests/static/test_downloadmanagerlocal_diagnostics.py`
  - no-UI gate command
- Commit boundary: commit route builder.

3.2 Move API handlers into controller while keeping compatibility imports.

- Acceptance:
  - Handler functions continue to return the same status/data/message shapes.
  - Existing imports from `api.py` continue to work or are updated with compatibility shim tests.
  - Pagination defaults remain `page=1`, `page_size=15`.
- Verification:
  - `python -m compileall plugins.v2/downloadmanagerlocal`
  - `python -m pytest tests/static/test_downloadmanagerlocal_manual_retry_api.py tests/static/test_downloadmanagerlocal_rename_archive.py tests/static/test_downloadmanagerlocal_diagnostics.py`
  - no-UI gate command
- Commit boundary: commit controller migration.

3.3 Add API response regression inventory.

- Acceptance:
  - Tests or static assertions cover route metadata and representative handler response keys for overview, diagnostics, rename history, archive list, retry actions, and delete/restore operations.
  - No route is silently removed or renamed.
- Verification:
  - `python -m pytest tests/static/test_downloadmanagerlocal_manual_retry_api.py tests/static/test_downloadmanagerlocal_diagnostics.py tests/static/test_downloadmanagerlocal_rename_archive.py`
  - no-UI gate command
- Commit boundary: commit API regression tests.

Phase acceptance:

- API route metadata is preserved.
- API implementation has a clear controller boundary.
- No forbidden UI path appears in diff.

## Phase 4: Service, Adapter, And Model Boundaries

Goal: Split business orchestration, external access, and structured state so backend responsibilities match the standard plugin layout.

Surfaces:

- `plugins.v2/downloadmanagerlocal/service/*.py`
- `plugins.v2/downloadmanagerlocal/adapter/*.py`
- `plugins.v2/downloadmanagerlocal/model/*.py`
- `plugins.v2/downloadmanagerlocal/modules/*.py`
- `plugins.v2/downloadmanagerlocal/utils/*.py`
- Existing tests

Tasks:

4.1 Introduce model constants and structured state helpers.

- Acceptance:
  - Persisted data keys for rename history, rename archive/retry state, IYUU caches/history, and seed recheck queue are centralized or documented in `model/`.
  - Existing saved data keys remain backward compatible.
  - No migration is required for existing plugin data.
- Verification:
  - `python -m compileall plugins.v2/downloadmanagerlocal`
  - `python -m pytest tests/static/test_downloadmanagerlocal_rename_archive.py tests/static/test_downloadmanagerlocal_seed_recheck.py`
  - no-UI gate command
- Commit boundary: commit model constants/state helpers.

4.2 Extract MoviePilot/downloader adapter calls.

- Acceptance:
  - Direct calls to `DownloaderHelper`, `SitesHelper`, `SiteOper`, `SystemConfigOper`, `RequestUtils`, `Qbittorrent`, and `Transmission` are concentrated in adapter modules where practical.
  - Service modules consume adapter functions/classes instead of duplicating external access.
  - Behavior and log-sensitive masking remain compatible.
- Verification:
  - `python -m compileall plugins.v2/downloadmanagerlocal`
  - `python -m pytest tests/static/test_downloadmanagerlocal_iyuu_regressions.py tests/static/test_downloadmanagerlocal_transfer_retry_hook.py tests/static/test_downloadmanagerlocal_stability_baseline.py`
  - no-UI gate command
- Commit boundary: commit adapter extraction.

4.3 Promote orchestration modules into service boundaries.

- Acceptance:
  - Transfer, IYUU, rename, recheck, archive, site tag, and diagnostics each have clear service ownership or documented module ownership.
  - `modules/` does not contain controller/API response shaping.
  - `utils/` contains only stateless helpers.
  - Cross-module calls are acyclic or explicitly documented if legacy compatibility requires an exception.
- Verification:
  - `python -m compileall plugins.v2/downloadmanagerlocal`
  - `python -m pytest tests/static/test_downloadmanagerlocal_*.py`
  - no-UI gate command
- Commit boundary: commit service boundary cleanup.

4.4 Remove dead imports and add docstrings for new backend public surfaces.

- Acceptance:
  - New public classes, public functions, and public methods have Chinese docstrings.
  - Unused imports introduced by refactoring are removed.
  - Existing behavior tests still pass.
- Verification:
  - `python -m compileall plugins.v2/downloadmanagerlocal`
  - `python -m pytest tests/static/test_downloadmanagerlocal_*.py`
  - `git diff --check`
  - no-UI gate command
- Commit boundary: commit cleanup.

Phase acceptance:

- Backend directory shape follows standard responsibilities.
- Existing persisted state remains compatible.
- No forbidden UI path appears in diff.

## Phase 5: Final Regression And Release Preparation Boundary

Goal: Verify the backend refactor end to end, document residual risk, and prepare metadata only if the user explicitly asks for merge/publish.

Surfaces:

- `plugins.v2/downloadmanagerlocal/ai_spec/plugin_context.md`
- `tests/static/test_downloadmanagerlocal_*.py`
- Optional release metadata only after user confirmation:
  - `plugins.v2/downloadmanagerlocal/__init__.py`
  - `plugins.v2/downloadmanagerlocal/plugin.json`
  - `package.v2.json`

Tasks:

5.1 Run full backend regression.

- Acceptance:
  - `python -m compileall plugins.v2/downloadmanagerlocal` exits 0.
  - `python -m pytest tests/static/test_downloadmanagerlocal_*.py` exits 0.
  - `git diff --check` exits 0.
  - No-UI gate command prints no paths.
- Verification:
  - The four commands above.
- Commit boundary: commit only if verification-related files changed.

5.2 Update backend context and residual risk.

- Acceptance:
  - `ai_spec/plugin_context.md` reflects final backend boundaries and validation commands.
  - Progress file records residual risks, including any tests skipped because the host environment is unavailable.
  - No UI work is described as completed.
- Verification:
  - `python -m compileall plugins.v2/downloadmanagerlocal`
  - no-UI gate command
- Commit boundary: commit context update.

5.3 Release-preparation gate, only if explicitly requested.

- Acceptance:
  - This task is skipped unless the user explicitly asks to merge, publish, release, or prepare PR metadata.
  - If requested, query remote `main` version baseline first.
  - Increment version once for this cycle and keep `plugin_version`, `plugin.json`, and `package.v2.json` synchronized.
  - `history` uses short result phrases and does not mention implementation trivia.
  - No push, merge, or release is performed without explicit user confirmation.
- Verification:
  - `python -m compileall plugins.v2/downloadmanagerlocal`
  - `python -m pytest tests/static/test_downloadmanagerlocal_*.py`
  - `git diff --check`
  - no-UI gate command
- Commit boundary: commit release metadata only if this gate is explicitly entered.

Phase acceptance:

- Backend refactor is verified.
- UI paths remain untouched.
- Progress file records final status and residual risk.
- Release metadata remains unchanged unless the user explicitly requested release preparation.

## Failure Modes And Required Recovery

- API route silently changes: user sees broken Vue API calls. Recovery: route metadata tests must fail; restore path/method/auth/summary compatibility.
- UI path is modified: user constraint violated. Recovery: stop, report, and revert only the agent-made UI-path changes.
- Existing plugin data key changes: users lose history or caches. Recovery: preserve keys or add backward-compatible read fallback with tests.
- Adapter extraction changes downloader/IYUU behavior: transfer or seeding fails silently. Recovery: keep existing logs, run regression tests, and add focused tests for changed adapters.
- Full MoviePilot runtime unavailable locally: do not claim runtime validation. Record the blocker and run compile/static tests that are available.

## Decision Log

- Decision: Backend-only phased refactor.
  Reason: User explicitly said not to touch UI, and current plugin has large backend responsibility spread.
  Rejected alternatives: UI standardization, Vue federation rebuild, direct one-shot rewrite.
  Source: Latest user constraint and MoviePilot plugin maintenance standard.

- Decision: Preserve existing `modules/` behavior during extraction.
  Reason: Existing tests already cover many regression-prone flows; moving all code at once would raise risk.
  Rejected alternatives: Replace modules with brand-new classes in one commit.
  Source: Existing DownloadManagerLocal tests and current module layout.

- Decision: Version metadata is not part of pure refactor execution.
  Reason: Project rules say version bump happens during release preparation based on remote `main`.
  Rejected alternatives: Bump version at plan start.
  Source: `AGENTS.md` repository workflow rules.

## /goal Starter

```text
/goal Implement D:/AIGC/MoviePilot/MoviePilot-Plugins/docs/plans/2026-07-02-downloadmanagerlocal-backend-refactor-phased-plan.md by following its execution ledger.

Each turn:
1. Read D:/AIGC/MoviePilot/MoviePilot-Plugins/docs/plans/2026-07-02-downloadmanagerlocal-backend-refactor-progress.json, then the current task in the plan.
2. Run `git status --short --branch` and the baseline smoke checks named in the plan; repair a broken state before starting new work.
3. Work only on the current backend work unit. Do not modify UI/front-end paths listed in the hard no-UI gate.
4. After verification passes: update the progress JSON status/evidence/log fields only, commit that unit, and record the hash. Never commit on failed verification.
5. Continue through verified phases without asking for approval. Never push, merge, amend, or prepare release metadata unless explicitly requested.

Done when every task is complete, every acceptance check is proven, UI paths remain untouched, and the progress file records final residual risk.
```
