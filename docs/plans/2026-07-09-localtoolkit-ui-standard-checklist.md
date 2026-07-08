# LocalToolkit UI Standard Execution Checklist

Branch: `worldlinefix/localtoolkit`
Target plugin: `plugins.v2/localtoolkit` (`LocalToolkit`, display name `工具中心`)
Verification baseline: `& 'C:\Users\ZhaoYu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest --confcutdir=tests/static tests/static/test_localtoolkit_standard_completion.py -q`

## Scope

Unify the Tool Center plugin UI with the MoviePilot plugin UI standard for desktop and mobile. Work only in `D:\AIGC\MoviePilot\MoviePilot-Plugins`; do not touch `D:\AIGC\MoviePilot\tmp\MoviePilot-Frontend-v2`, do not recreate `worldlinefix/toolcenter-ui`, and do not push, merge, amend, or publish.

## Source Of Truth

- `D:\AIGC\MoviePilot\.agents\skills\moviepilot-plugin-ui-design\SKILL.md`
- `D:\AIGC\MoviePilot\.agents\skills\create-moviepilot-plugin\SKILL.md`
- `D:\AIGC\MoviePilot\AGENTS.md`

## Execution Rules

- Before each work unit, confirm `git status --short --branch` shows `worldlinefix/localtoolkit`.
- Run the verification baseline before new UI edits in a fresh turn.
- Work only on the next pending item.
- After a work unit passes its named verification, update only `Status`, `Evidence`, `Notes`, and `Commit` fields for that item, then create a commit for that verified unit.
- Never commit failed verification.
- Never push, merge, or amend automatically.

## Checklist

### 1. Baseline And Ledger

Status: completed

Acceptance:
- This checklist exists at `docs/plans/2026-07-09-localtoolkit-ui-standard-checklist.md`.
- Current branch is `worldlinefix/localtoolkit`.
- Static baseline test exits 0.

Verify:
- `git status --short --branch`
- `& 'C:\Users\ZhaoYu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest --confcutdir=tests/static tests/static/test_localtoolkit_standard_completion.py -q`

Evidence:
- `Test-Path` for `docs/plans/2026-07-09-localtoolkit-ui-standard-checklist.md` was false before creation and the file now exists.
- `git status --short --branch` returned `## worldlinefix/localtoolkit...origin/worldlinefix/localtoolkit`.
- Baseline command returned `9 passed in 0.04s`.

Notes:
- Checklist was created because the active goal referenced this path but the file had not yet been written.

Commit:
- `1d1cc47` (`docs(localtoolkit): add ui standard checklist`)

### 2. Config.vue Desktop And Mobile Shell

Status: pending

Acceptance:
- `frontend/src/components/Config.vue` desktop `.plugin-nav` width and flex basis are exactly `160px`.
- Config responsive breakpoint uses the standard `@media (max-width: 760px)` for mobile layout.
- Mobile primary nav and subtabs are horizontal, non-wrapping, and horizontally scrollable.
- Overview remains the first primary tab with key `overview` and default active state.

Verify:
- Update or add static assertions in `tests/static/test_localtoolkit_standard_completion.py`.
- Run the verification baseline.

Evidence:
- 

Notes:
- 

Commit:
- 

### 3. Page.vue Standard Detail Layout

Status: pending

Acceptance:
- `frontend/src/components/Page.vue` uses a standard `VToolbar` top bar rather than a hero-style `VCard` header.
- The toolbar exposes refresh and close actions with standard Vuetify buttons/icons.
- History uses backend pagination with `page` and `page_size`.
- Mobile history cards are shown on narrow screens and the desktop table is hidden there.

Verify:
- Static assertions cover `VToolbar`, no hero header for the top shell, backend pagination request, and mobile history/table rules.
- Run the verification baseline.

Evidence:
- 

Notes:
- 

Commit:
- 

### 4. AppPage.vue Standard Main Page Layout

Status: pending

Acceptance:
- `frontend/src/components/AppPage.vue` interaction and history behavior match `Page.vue`.
- History no longer depends on frontend-only full-list slicing.
- It requests history with `page` and `page_size`.
- Mobile history cards and desktop table switch cleanly with no horizontal overflow.

Verify:
- Static assertions cover backend pagination request and absence of frontend-only slicing.
- Run the verification baseline.

Evidence:
- 

Notes:
- 

Commit:
- 

### 5. Dashboard.vue Standard Card Controls

Status: pending

Acceptance:
- `frontend/src/components/Dashboard.vue` keeps `VCard variant="flat"`, 16px radius, border, `VCardItem`, `VCardTitle`, and `VCardSubtitle`.
- It accepts `allowRefresh` and shows a refresh action in the `VCardItem` append slot only when refresh is allowed.
- Refresh action reloads status through the injected API.

Verify:
- Static assertions cover `allowRefresh`, append refresh control, and standard card structure.
- Run the verification baseline.

Evidence:
- 

Notes:
- 

Commit:
- 

### 6. Federation Build Assets

Status: pending

Acceptance:
- `pnpm run build` succeeds in `plugins.v2/localtoolkit/frontend`.
- `dist/assets/remoteEntry.js` exposes `./Config`, `./Page`, `./AppPage`, and `./Dashboard`.
- Every JS/CSS asset referenced by `remoteEntry.js` exists.
- Old stale Config/Page/AppPage/Dashboard hash assets are not left behind by the build.

Verify:
- `& 'C:\Users\ZhaoYu\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd' run build`
- PowerShell asset reference check against `plugins.v2/localtoolkit/dist/assets/remoteEntry.js`.
- `git status --short`

Evidence:
- 

Notes:
- 

Commit:
- 

### 7. Desktop And Mobile UI Evidence

Status: pending

Acceptance:
- Browser evidence is recorded for Config, Page, AppPage, and Dashboard at `390x844`, `768x1024`, and `1440x900`.
- Evidence proves no horizontal overflow, no offscreen buttons, no incoherent overlap, and correct mobile nav/table behavior.
- Evidence files are stored under `docs/plans/localtoolkit-ui-standard-evidence/`.
- Residual risk is documented.

Verify:
- Browser or Playwright audit command records screenshots and an `audit.json`.
- Audit JSON has zero horizontal overflow and zero offscreen buttons for all checked views.

Evidence:
- 

Notes:
- 

Commit:
- 

## Final Completion Criteria

- All checklist items are complete.
- Every completed item has evidence and a commit hash, except external-only evidence where a commit is not applicable.
- `git status --short --branch` has no uncommitted source or dist changes outside explicitly ignored evidence files.
- No push, merge, amend, or `main` release action has been performed.
