# LocalToolkit Plugin Context

## Purpose

`LocalToolkit` is the MoviePilot local maintenance plugin named `工具中心`.
It combines three local tool modules:

- `library_cleanup`: keeps the periodic library cleanup flow.
- `check_missing`: runs missing-episode scans only on demand.
- `tmdb_cache`: checks and clears TMDB Redis cache only on demand.

This context reflects the refactored source layout in
`plugins.v2/localtoolkit` and the Vue federation runtime in `dist/assets`.
It does not claim that MP runtime reload or install verification is complete;
that belongs to the later MP local runtime phase.

## Entry Points

- `plugins.v2/localtoolkit/__init__.py`
  - Owns `_PluginBase` metadata, `plugin_version`, render mode, and thin
    delegation methods only.
  - `get_render_mode()` must return `("vue", "dist/assets")`.
  - `get_api()`, `api_status()`, `api_run()`, `api_history()`,
    `api_options()`, and `api_invalidate_cache()` delegate to
    `controller/api.py`.
  - `init_plugin()`, `get_service()`, and `stop_service()` delegate to
    `service/lifecycle.py`.
- `plugins.v2/localtoolkit/plugin.json`
  - Mirrors the plugin metadata used by MoviePilot.
- `package.v2.json`
  - Contains the `LocalToolkit` market entry and current version history.

## Backend Structure

- `controller/api.py`
  - Declares plugin routes and shapes API responses.
  - Routes are under `plugin/LocalToolkit/local_toolkit/*` when called from the
    frontend helper.
  - All declared API routes use `auth: "bear"`.
- `model/config.py`
  - Owns default config and merge behavior.
  - Protects removed one-shot module cron fields from being reintroduced.
- `service/lifecycle.py`
  - Builds module instances.
  - Migrates legacy plugin config from `ClearTmdbCache`, `CheckMissing`, and
    `LibraryCleanup`.
  - Registers only the library cleanup scheduler when enabled.
- `service/base.py`
  - Shared module helpers such as history recording and config storage.
- `service/library_cleanup.py`
  - Library cleanup behavior, options cache, media-server option loading, and
    delegated legacy cleanup execution.
- `service/check_missing.py`
  - On-demand missing scan behavior.
- `service/tmdb_cache.py`
  - On-demand Redis/TMDB cache status and cleanup behavior.
- `modules/*.py`
  - Compatibility shims only. Do not move orchestration or external boundaries
    back into `modules/`.

There is currently no `adapter/` directory. If a future external boundary grows
large enough to need one, add it deliberately and update this file and tests.

## API Routes

Declared in `controller/api.py`:

- `GET /local_toolkit/status`
- `POST /local_toolkit/run/{module}`
- `GET /local_toolkit/history`
- `GET /local_toolkit/options`
- `POST /local_toolkit/invalidate_cache`

Supported module keys:

- `library_cleanup`
- `check_missing`
- `tmdb_cache`

`api_history` accepts `page` and `page_size`, clamps invalid values, returns
`total`, `page`, `page_size`, `total_pages`, and `items`, and tolerates corrupt
history storage by returning an empty list.

## Scheduler Behavior

Only `library_cleanup` may register a MoviePilot background service. The plugin
must return no service entries when the plugin is disabled. `check_missing` and
`tmdb_cache` are on-demand modules and must not regain cron scheduling.

## Persistent Keys

The plugin config prefix is `localtoolkit_`.

Important persistent fields:

- `enabled`
- `migration_done`
- `tmdb_cache.notify`
- `tmdb_cache.auto_clear`
- `tmdb_cache.threshold_mb`
- `check_missing.notify`
- `check_missing.scan_paths`
- `check_missing.skip_empty`
- `library_cleanup.enabled`
- `library_cleanup.cron`
- `library_cleanup.notify`
- `library_cleanup.selected_server`
- `library_cleanup.selected_library`
- `library_cleanup.selected_user`
- `library_cleanup.filter_played`
- `library_cleanup.filter_favorite`
- `library_cleanup.auto_delete`
- `library_cleanup.auto_delete_delay`
- `library_cleanup.dry_run`
- `library_cleanup.auto_delete_max_count`

Runtime history is stored with `get_data` / `save_data` key `tool_history`.

## Frontend

Vue federation source lives in `frontend/src/components`:

- `AppPage.vue`: full page/detail entry and module run actions.
- `Config.vue`: Vue config dialog.
- `Page.vue`: detail/history page.
- `Dashboard.vue`: dashboard card.
- `api.js`: injected MoviePilot API helper with fallback fetch.

Vite exposes:

- `./Page`
- `./Config`
- `./Dashboard`
- `./AppPage`

Built assets live in `dist/assets`. `remoteEntry.js` and every referenced hash
asset must exist together. Mobile verification currently requires 390px,
768px, and 1440px checks. Below 600px, `AppPage.vue` and `Page.vue` render
history as cards instead of a wide table so summaries remain readable.

## Validation Commands

Run from `D:/AIGC/MoviePilot/MoviePilot-Plugins` unless noted.

```powershell
& 'C:/Users/ZhaoYu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m compileall -q plugins.v2/localtoolkit
& 'C:/Users/ZhaoYu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m pytest --confcutdir=tests/static tests/static/test_localtoolkit_standard_completion.py -q
& 'C:/Users/ZhaoYu/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -m unittest discover -s plugins.v2/localtoolkit/tests -p test_stability.py
```

Frontend build, from `plugins.v2/localtoolkit/frontend`:

```powershell
$env:PATH = 'C:\Users\ZhaoYu\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin;C:\Users\ZhaoYu\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin;' + $env:PATH
& 'C:\Users\ZhaoYu\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd' install
& 'C:\Users\ZhaoYu\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd' run build
```

After frontend build, remove temporary install artifacts unless the project
explicitly decides to track them:

```powershell
Remove-Item -LiteralPath 'plugins.v2/localtoolkit/frontend/node_modules' -Recurse -Force
Remove-Item -LiteralPath 'plugins.v2/localtoolkit/frontend/pnpm-lock.yaml' -Force
```

## Forbidden Edit Areas

- Do not push, merge, publish, or release from this plugin refactor cycle.
- Do not change `main` or trigger release workflows.
- Do not move business logic back into `modules/`; keep those files as shims.
- Do not reintroduce cron config or scheduler registration for `check_missing`
  or `tmdb_cache`.
- Do not hardcode browser-side API tokens in frontend code.
- Do not change visible UI wording or layout beyond a verified defect without
  recording browser evidence.
- Do not update version numbers for release unless a later explicit release
  request starts the release-preparation phase.
