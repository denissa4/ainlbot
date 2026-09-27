# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

NLSQL Analyzer: a Microsoft Bot Framework chatbot that answers natural-language questions about a customer's SQL database, plus a background job that emails anomaly-detection reports.

Crucially, **this repo does not do NL→SQL itself**. `api/nlsql/handler.py:api_post` POSTs the user's text to the external NLSQL SaaS (`ApiEndPoint`, auth `Token $ApiToken`) and gets back a directive: `{data_type, sql, message, indicator, system_buttons, addition_buttons, unaccounted}`. Everything in this repo is the execution half — run the returned SQL against the customer DB, format results, render charts, and shape a Bot Framework payload.

## Build & run

There is no local dev server setup and no test suite (`npm test` is a stub that exits 1; there are no Python tests). Everything runs through Docker.

```bash
# All-in-one image (api + bot + nginx + anomaly job under supervisord)
docker build -f Dockerfile -t nlsql-api-server .
docker run --rm -p 8080:80 --env-file .env nlsql-api-server

# Bot only
cd bot && docker build -t nodejs-bot . && docker-compose up

# Bot TypeScript (from bot/)
npm run build      # tsc --build -> lib/
npm run lint       # tslint -c tslint.json 'src/**/*.ts'
npm run watch      # nodemon rebuild+restart
```

Running a Python module directly (inside the container) is how the anomaly job is started:
`python /app/api/nlsql/anomaly_handler.py` — it loops forever, sleeping `86400 * Frequency` seconds.

## Runtime topology (one container, supervisord)

`supervisord.conf` starts four processes:

| process | command | port |
|---|---|---|
| `api` | `/venv/bin/gunicorn -t 300 -b 0.0.0.0:8000 api:app` | 8000 |
| `bot` | `node ./lib/index.js` in `/app/bot` (precompiled at build time) | 3978 (`bot_port`/`BOT_PORT`) |
| `nginx` | reverse proxy + static | 80 |
| `anomaly_handler` | `/venv/bin/python /app/api/nlsql/anomaly_handler.py` (logs to `/var/log/anomaly_handler*.log`) | — |

nginx proxies `/api/messages` → `localhost:3978`, serves static files by extension from `/var/www/html` (generated charts/CSVs under `bot/static/`), and answers `/health` itself. (The README's claim that `/api/messages` proxies to port 8000 is stale — trust `nginx/nginx.conf`.)

Request flow: Teams/Slack → nginx `/api/messages` → `bot/src/index.ts` (CloudAdapter) → `bot/src/bot.ts` axios POST to `nlapiurl` (default `http://localhost:8000/nlsql-analyzer`) → Flask → NLSQL SaaS + customer DB → payload back → rendered as text / hero card / adaptive card.

`api/nlsql/metering.py:report_usage` (called once per request from `handler.py`) posts Google Cloud Marketplace usage to a ubbagent sidecar. It does nothing unless `UbbAgentEndpoint` is set, and it must never raise. The same image ships to Azure App Service, AWS Marketplace and GCP Marketplace.

## The API↔bot contract

`api/nlsql/nlsql_typing.py:NLSQLAnswer` and the `NLSQLAnswer` interface in `bot/src/bot.ts` are the same shape, duplicated by hand — **change both together**. `bot.ts` switches on `answer_type` (`text` | `hero_card` | `adaptive_card`) and throws `NotImplemented` on anything else, so a new answer type needs a matching case there.

Every return in `parsing_text` must supply all seven keys (`answer`, `answer_type`, `unaccounted`, `addition_buttons`, `buttons`, `images`, `card_data`), even as `None` — there are ~15 such return sites in `handler.py`.

## Key files

- `api/__init__.py` — the whole Flask app: one route, `POST /nlsql-analyzer`, body `{"channel_id", "text"}`.
- `api/nlsql/handler.py` — the dispatcher. A large branch on `data_type` (`message`, `report`, `buttons`, `arg_buttons`/`column_name_buttons`, and the chart types `graph`/`map`/`bar`/`bubble`/`pie`/`bar-stacked`/`bar-grouped`/`scatter` plus their `-complex` variants). Also builds the button payloads whose `value` strings encode NLSQL's own markers — `[{[key:word]}]`, `[[[key:word]]]`, `[%[key:word]%]`, `[([...])]`, `[{[all_arg:...]}]` — which get echoed back as the next user message. Don't reformat those strings casually.
- `api/nlsql/connectors/connectors.py` — per-DB connect + query. `DatabaseType` ∈ mysql, mssql, snowflake, redshift, postgresql, bigquery. Note the async/sync split: snowflake, redshift and bigquery use blocking clients; the rest are aio* drivers. Closing differs too — `mssql`/`postgresql` use `await conn.close()`, everything else `conn.close()`.
- `api/nlsql/graph.py` — plotly/matplotlib renderers. Each `build_html_*` writes a random-named `pio_XXXXXXXXXX.html` + `.jpg` into `/var/www/html/bot/static/` and returns the two filenames; the caller turns them into URLs with `StaticEndPoint`.
- `api/nlsql/anomaly_handler.py` — standalone scheduled job (see below).

## Anomaly detection

Independent of the chat path. It pulls the customer's data sources / tables / KPIs / filters from `https://api.nlsql.com/v1/data-source/`, then for each KPI synthesizes English prompts (`"{kpi} in {year} by month"`) and sends them through the same NLSQL API to get SQL for the *trusted* years (`FromYear`..`ToYear`) and for the current year.

Two corridor modes via `CorridorsMode`:
- `1` (standard): flat `mean ± BoundarySensitivity × std` over monthly averages; needs ≥1 year of data.
- `2` (seasonal, default): per-month rolling mean/std (`WindowSize`, clamped to 3–9), December/January wrap-padding, then `UnivariateSpline` smoothing of both bounds; needs ≥2 years.

Points outside the corridor become anomalies → OpenAI (legacy `openai==0.28.0` `ChatCompletion.acreate` with Azure `engine=OpenAiName`) writes the explanation → plotly graph → one HTML email via `smtplib.SMTP_SSL('smtp.gmail.com', 465)`. **The SMTP host is hardcoded to Gmail** despite the docs mentioning Outlook. The job no-ops unless `EmailAddress` is set.

## Environment variables

All config is env vars, read via `os.getenv` at call time (no settings module). `.env` at the repo root is the local template; the main `Dockerfile` re-declares most of them as `ARG`/`ENV`. The README lists them all. Groups: DB connection, `ApiEndPoint`/`ApiToken`/`StaticEndPoint`, Bot Framework (`AppId`/`AppPassword`/`AuthTenantID`, `index.ts` reads `MicrosoftAppId`/`MicrosoftAppPassword`/`MicrosoftAppTenantId` first and falls back to those short names, plus `MicrosoftAppType`. Under `UserAssignedMSI` both password names are ignored, because the SDK asserts that MSI gets no password.), Marketplace metering (`UbbAgentEndpoint`, `UsageMetric`), anomaly tuning, email, OpenAI.

Naming is inconsistent and partly misspelled — the Dockerfile declares `BoundrySensetivity` while the code reads `BoundarySensitivity`, and `anomaly_handler.py` has a `os.getenv('BoundarySensetivity' '2.0')` string-concat typo in the GPT prompt. Verify the exact spelling in the file you're touching before adding a new one. Debug flags differ per component too: Python checks `DEBUG == '1'`, `bot.ts` checks `DEBUG === 'true'`.

## Constraints to respect

- **Python 3.13** from Debian trixie's system package, with deps in a venv at `/venv` (PEP 668). Everything in `api/requirements.txt` is pinned and was tested as one set, so don't bump pins casually; the comments at the top of that file explain the pins that matter. `kaleido==0.2.1` is held because 1.x needs Chrome in the image, which forces `plotly` to stay on 6.x. `openai==0.28.0` is held because the code uses the pre-1.0 API. Pyarrow/snowflake upgrades have been reverted before.
- **Node 20** in the main image (`nodesource setup_20.x`). `bot/Dockerfile` still uses `node:16-alpine`. TypeScript 5.4 targets `es2016`/commonjs.
- **The image must pass Marketplace vulnerability scans** (AWS/GCP). The Dockerfile deliberately keeps `apt-get upgrade` *below* `COPY . /app/` so the layer is never served from cache. It also purges the build toolchain and strips npm and pip from the final image, so there's no `npm`/`pip` at runtime. Keep that ordering and those removals, and don't add packages that bring in a lot of CVE exposure (e.g. Chrome).
- `index.ts` must never log `process.env` or its values, because they include `DbPassword`, `ApiToken` and `AppPassword`. It logs key names only.
- `handler.py` keeps **module-level mutable globals** (`list_of_elements`, `previous_add_btn`) for paginating "complex" graph results. They are shared across all users and requests — treat any change there as affecting concurrency behaviour.
- The image carries Google Cloud Marketplace `LABEL`s at the bottom of the Dockerfile; keep them when editing.
- The codebase uses hand-rolled async generators (`words`, `words_for_check`, `async_range`, `_words`) to iterate lists. They're pointless but pervasive; match surrounding style rather than half-converting.
