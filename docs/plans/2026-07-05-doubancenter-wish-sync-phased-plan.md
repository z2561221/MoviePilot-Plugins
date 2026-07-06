# DoubanCenter Sync Wish Phased Plan

## Goal

Implement DoubanCenter "同步想看" as a child feature of "豆瓣时间".

The feature reads the current Douban account's wish list through the existing Douban cookie, initializes a baseline without subscribing historical entries, then on an independent default 30-minute schedule scans the latest wish page, detects new wish items, recognizes them through MoviePilot/TMDB, and creates MoviePilot subscriptions. It must remain independent from the existing ranking subscription runtime.

## Source Of Truth

- Latest user decisions in this thread:
  - Product ownership: "同步想看" belongs under "豆瓣时间".
  - UI: rename the current "同步设置" second-level tab to "同步观影"; add "同步想看"; order is "同步想看" first, "同步观影" second.
  - Runtime: Douban wish sync and ranking subscription are independent runtime chains.
  - Runtime period: Douban wish sync has an independent schedule, default 30 minutes.
  - Removed behavior: no per-run one-item limit and no 5-10 minute random cooldown.
  - Default scan pages: 1.
  - Overview: "运行总览" must add the Douban wish runtime logic chain.
  - Unified flow labels: "周期触发", "读取想看", "新增入队", "媒体识别", "创建订阅".
- Plugin rules: `D:\AIGC\MoviePilot\AGENTS.md`.
- Plugin maintenance rules: `D:\AIGC\MoviePilot\.agents\docs\moviepilot-plugin-maintenance-standard.md`.
- Existing plugin context: `plugins.v2/doubancenter/ai_spec/plugin_context.md`.

## Execution Rules

- Worktree: `D:\AIGC\MoviePilot\MoviePilot-Plugins`.
- Required branch: `worldlinefix/doubancenter`.
- Do not push, merge, amend, or publish.
- Before starting a work unit, run:
  - `git log --oneline -15`
  - Smoke check: `python -m compileall -q plugins.v2/doubancenter`
- Commit each verified work unit. Never commit if its required verification fails.
- Preserve unrelated user changes and unrelated untracked files.
- Progress file: `docs/plans/2026-07-05-doubancenter-wish-sync-progress.json`.
- The executing agent may only update status, evidence, commit, decision log, and turn log fields in the progress file.

## Implementation Surface

- Backend config and lifecycle:
  - `plugins.v2/doubancenter/__init__.py`
  - `plugins.v2/doubancenter/model/config.py`
  - `plugins.v2/doubancenter/service/scheduler.py`
- Douban account and wish access:
  - `plugins.v2/doubancenter/doubanapi.py`
  - `plugins.v2/doubancenter/folio.py`
- Persistence:
  - `plugins.v2/doubancenter/storage/records.py`
- Subscription reuse:
  - `plugins.v2/doubancenter/service/subscription.py`
- Overview and API:
  - `plugins.v2/doubancenter/service/dashboard_overview.py`
  - `plugins.v2/doubancenter/dashboard.py`
  - `plugins.v2/doubancenter/controller/api.py`
- Vue config UI:
  - `plugins.v2/doubancenter/src/components/Config.vue`
  - `plugins.v2/doubancenter/dist/assets/*` after build.
- Tests:
  - `plugins.v2/doubancenter/tests/test_runtime_contracts.py`
  - `plugins.v2/doubancenter/tests/test_config_frontend_contract.py`
  - New or updated tests for wish parsing, baseline state, scheduler contract, overview contract, and subscription behavior.

## Data Flow

```text
DoubanCenterWish scheduler
-> folio.run_wish_sync()
-> DoubanApi.get_wish_items()
-> storage folio_wish_state / seen / queue / failed
-> MoviePilot chain.recognize_media()
-> subscription_service.add_subscription()
-> subscribe_records with rank_key=douban_wish
```

## Phases

### Phase 1 - State, Config, And Independent Scheduler Contract

Visible result: the plugin exposes "同步想看" configuration and a separate scheduled service, but it does not yet perform network reads or subscriptions.

Surfaces:
- `__init__.py`
- `model/config.py`
- `storage/records.py`
- `service/scheduler.py`
- `tests/test_runtime_contracts.py`

Tasks:

1.1 Add wish sync config/state defaults.
- Add config fields: `wish_enabled`, `wish_cron`, `wish_user`, `wish_notify`, `wish_max_pages`, plus internal attributes with default cron equivalent to 30 minutes and max pages 1.
- Ensure `__current_config()` round-trips new fields and legacy configs load without dropping existing fields.
- Add storage helpers for `folio_wish_state`, `folio_wish_seen`, `folio_wish_queue`, `folio_wish_processed`, and `folio_wish_failed`.

1.2 Add independent scheduler declaration.
- Extend scheduler service so ranking subscription and wish sync are separate jobs.
- Existing `DoubanCenter` job remains for ranking subscription.
- Add `DoubanCenterWish` job using `wish_cron`.
- Wish job must require plugin enabled, folio enabled, wish enabled, and a valid cron.

Acceptance:
- `python -m compileall -q plugins.v2/doubancenter` exits 0.
- `python -m unittest discover -s plugins.v2/doubancenter/tests -p "test_runtime_contracts.py"` exits 0.
- A test proves `DoubanCenterWish` is declared separately from `DoubanCenter`.
- A test proves default wish max scan pages is 1.
- Commit after acceptance.

### Phase 2 - Douban Wish Read, Baseline, And Queue Logic

Visible result: wish sync can read/parse Douban wish items and maintain baseline/queue state without creating subscriptions.

Surfaces:
- `doubanapi.py`
- `folio.py`
- `storage/records.py`
- New tests under `plugins.v2/doubancenter/tests/`.

Tasks:

2.1 Add Douban wish list access.
- Reuse existing cookie acquisition.
- Add a method that resolves the current account wish page from cookie when no user id is configured.
- Use optional user id only as fallback.
- Parse subject id, title, year, link, poster if available.
- Keep network calls behind existing MoviePilot HTTP utilities or injectable request functions so tests do not hit the real network.

2.2 Implement baseline and queue state machine.
- First enabled run reads up to `wish_max_pages` pages, records seen/baseline subject ids, and does not enqueue or subscribe historical items.
- Later runs read up to `wish_max_pages`, stop at known seen/processed ids, and add new items to `folio_wish_queue`.
- New ids are persisted to seen/queue without participating in rank histories or observation queues.

Acceptance:
- `python -m compileall -q plugins.v2/doubancenter` exits 0.
- New unit tests prove first run creates baseline without queued items.
- New unit tests prove later run adds only new wish items to queue.
- New unit tests prove default max pages 1 only requests the first page.
- Commit after acceptance.

### Phase 3 - Recognition And Subscription Execution

Visible result: queued wish items are recognized and subscribed through the existing MoviePilot subscription chain.

Surfaces:
- `folio.py`
- `service/subscription.py` if reusable metadata needs a small extension.
- `storage/records.py`
- New tests under `plugins.v2/doubancenter/tests/`.

Tasks:

3.1 Execute queued wish subscriptions.
- Process queued items in deterministic queue order.
- Recognize media with title/year/type candidates through MoviePilot/TMDB.
- Add subscriptions via existing `subscription_service.add_subscription()`.
- Write subscribe history with `rank_key="douban_wish"` and `rank_name="豆瓣想看"`.
- Mark processed, failed, and retry metadata in wish storage.

3.2 Error handling and status.
- Cookie invalid: preserve queue and seen state, write clear state error.
- Recognition failed: keep failure record with reason and retry count.
- Already subscribed: mark processed or existing without repeated retries.
- Subscription failed: write failed subscribe record and wish failed state.

Acceptance:
- `python -m compileall -q plugins.v2/doubancenter` exits 0.
- Unit tests prove success writes `rank_key=douban_wish`.
- Unit tests prove failed recognition is recorded and does not crash the scheduler.
- Unit tests prove existing subscription is not retried indefinitely.
- Commit after acceptance.

### Phase 4 - Overview And Config UI

Visible result: the existing Config UI looks like DoubanCenter's current style, with overview showing the wish runtime chain and the folio tabs reordered.

Surfaces:
- `service/dashboard_overview.py`
- `service/dashboard_config.py` if overview/config API needs extra state.
- `src/components/Config.vue`
- `tests/test_dashboard_overview_service.py`
- `tests/test_config_frontend_contract.py`
- `dist/assets/*` after build.

Tasks:

4.1 Update backend overview/config response.
- Add flow: label `同步想看`, steps `周期触发`, `读取想看`, `新增入队`, `媒体识别`, `创建订阅`.
- Add wish status summary to overview cards or folio status where appropriate, without mixing it into ranking subscription status.

4.2 Update Vue config UI.
- In "豆瓣时间", change old second-level tab title from `同步设置` to `同步观影`.
- Add `同步想看` as the first second-level tab, before `同步观影`.
- Use existing `dc-` style: compact controls, existing pane/card language, no large whiteboard layout.
- Show controls: enable wish sync, wish schedule default 30 minutes, optional user id, cookie source note, notify switch, max scan pages default 1, baseline warning, state/actions.
- Do not display the full runtime flow inside the wish config pane; the runtime flow belongs in overview.

Acceptance:
- `python -m unittest discover -s plugins.v2/doubancenter/tests -p "test_dashboard_overview_service.py"` exits 0.
- `python -m unittest discover -s plugins.v2/doubancenter/tests -p "test_config_frontend_contract.py"` exits 0.
- `npm run build` from `plugins.v2/doubancenter` exits 0 and updates `dist/assets/remoteEntry.js`.
- Static tests prove tab order is `同步想看` then `同步观影`.
- Static tests prove flow labels use the unified text exactly.
- Commit after acceptance.

### Phase 5 - Full Regression And Runtime Validation

Visible result: all plugin tests, frontend build, and local MoviePilot reload validation pass.

Surfaces:
- All touched files.
- Runtime install/reload path if available in this environment.
- Optional validation doc under `plugins.v2/doubancenter/docs/`.

Tasks:

5.1 Full local verification.
- Run all plugin unit tests.
- Run static tests named in this plan.
- Run frontend build.
- Re-read changed files for version/config consistency.

5.2 MoviePilot local close-loop validation where available.
- Sync/install/reload into MP local plugin repo if configured and reachable.
- Read `/api/v1/plugin/history/DoubanCenter` or equivalent installed/plugin API.
- Verify plugin can load config and overview without server traceback.
- If runtime is unavailable, record the exact unavailable dependency and keep automated local verification as evidence.

Acceptance:
- `python -m compileall -q plugins.v2/doubancenter` exits 0.
- `python -m unittest discover -s plugins.v2/doubancenter/tests -p "test_*.py"` exits 0.
- `python -m pytest tests/static/test_doubancenter_native_subscribe.py tests/static/test_doubancenter_observation_order.py` exits 0.
- `npm run build` from `plugins.v2/doubancenter` exits 0.
- MP runtime validation is recorded, or unavailability is recorded with exact blocker.
- Commit after acceptance.

## Not In Scope

- Publishing, pushing, merging to `main`, or creating a release.
- Changing global MoviePilot host behavior.
- Making a new top-level plugin module for wish sync.
- Reusing rank observation period or rank filtering for wish sync.
- Subscribing historical wish items on first enable.

## Failure Modes And Recovery

- Cookie expired: wish state records an error; queue is preserved; user sees cookie status.
- Douban HTML changes: parser returns an empty/error state; no subscriptions are created.
- TMDB recognition mismatch: failure is recorded; item is not silently subscribed.
- Large historical wish list: default max scan pages 1 and first-run baseline prevent old entries from being subscribed.
- Scheduler overlap: use the plugin's sync lock or a wish-specific lock so concurrent runs do not duplicate work.

## Decision Log

- Product ownership: "同步想看" belongs under "豆瓣时间" because it uses Douban account cookie and account state.
- Runtime boundary: wish sync is independent from ranking subscription to avoid rank safety gates and observation logic leaking into account-state sync.
- Default scan pages: 1 to avoid historical sweep and reduce Douban access volume.
- Flow label choice: use "媒体识别" instead of "TMDB识别" in UI to keep step text lengths aligned while implementation still uses MoviePilot/TMDB recognition.
