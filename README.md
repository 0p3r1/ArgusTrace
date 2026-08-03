# ArgusTrace

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Managed with uv](https://img.shields.io/badge/managed%20with-uv-de5fe9)
![Tests: pytest](https://img.shields.io/badge/tests-pytest-0a9edc)
![Status: active](https://img.shields.io/badge/status-active-brightgreen)
![License: TBD](https://img.shields.io/badge/license-TBD-lightgrey)

A modular OSINT framework. One shared plugin registry (`TOOL_FAMILIES`)
drives both a CLI and a web app (FastAPI + React) against real OSINT tools,
each run in a hardened, single-use Docker container. Every result is a
**tri-state** `Finding` — `FOUND` / `NOT_FOUND` / `ERROR`, never a boolean,
never a guess. Still deliberately out of scope: a scheduler, correlation
engine, scoring, or graph — this stays focused on one thing, running a tool
against an entity and getting back an honest, structured result.

## Architecture

```mermaid
%%{init: {"flowchart": {"subGraphTitleMargin": {"top": 10, "bottom": 15}}}}%%
flowchart LR
    User(["You: \"check this username, email, or phone\""])
    CLI["ArgusTrace CLI"]
    Mock["Mock plugin<br/>(demo, no real check)"]
    ToolPlugin["Tool plugin<br/>(Sherlock, Holehe, Ignorant, ...)"]
    Findings["Findings:<br/>found / not found / error"]
    Output(["JSON result"])

    subgraph Container["Sandboxed Docker container<br/>(spun up, used once, destroyed)"]
        Tool["The actual OSINT tool"]
    end

    User --> CLI
    CLI --> Mock
    CLI --> ToolPlugin
    ToolPlugin -- "runs it in isolation,<br/>never touches your machine" --> Tool
    Tool -- "results come back" --> ToolPlugin
    Mock --> Findings
    ToolPlugin --> Findings
    Findings --> Output
```

Any failure inside the container (timeout, docker missing, bad output) is
caught by the plugin and turned into a `Finding(status=ERROR)` — it never
propagates as an exception.

## Core design

- **`Status` is tri-state, not a boolean.** `FOUND` / `NOT_FOUND` / `ERROR`.
  `NOT_FOUND` means "checked, doesn't exist." `ERROR` means "could not check"
  (timeout, rate-limit, crash). Never conflate the two — an `ERROR` reported
  as `NOT_FOUND` is a false negative.
- **`Plugin` is a `Protocol`**, not a base class: `name`, `supported_entities`,
  and `async def run(entity: str, options: dict | None = None) -> list[Finding]`.
  Any object with that shape works as a plugin, no inheritance required.
  `options` carries real, per-tool CLI flags (declared in `TOOL_FAMILIES`,
  see below) — a plugin with nothing meaningful to expose just ignores it.
- **Every plugin must catch its own failures.** `run()` should never raise —
  timeouts, missing binaries, bad output, etc. must come back as a
  `Finding(status=ERROR)` so one broken plugin can't take down a run.

## Project layout

```
argustrace/
├── core/
│   └── models.py       # Status, Finding
├── plugins/
│   ├── base.py          # Plugin protocol
│   ├── registry.py      # PLUGINS + TOOL_FAMILIES, shared by the CLI and the API
│   ├── _docker_runner.py  # shared hardened `docker run` helper
│   ├── mock_plugin.py   # hardcoded findings, no I/O — proves the pipeline
│   ├── sherlock_plugin.py  # runs Sherlock in a hardened Docker container
│   ├── maigret_plugin.py   # runs Maigret in a hardened Docker container
│   ├── holehe_plugin.py    # runs Holehe in a hardened Docker container
│   ├── ignorant_plugin.py  # runs Ignorant in a hardened Docker container
│   ├── crtsh_plugin.py     # queries crt.sh (Certificate Transparency) in a container
│   ├── theharvester_plugin.py  # runs theHarvester in a hardened Docker container
│   ├── ip_plugin.py        # RDAP + ip-api.com geolocation, in a container
│   └── recherche_entreprises_plugin.py  # France's open company registry, in a container
├── versioning.py         # on-demand PyPI/Docker Hub/GitHub release checks
├── cli.py                # `investigate` and `options` commands
└── api.py                # FastAPI app: /api/plugins, /api/investigate,
                           # /api/tools/{family}/version-check, /api/tools/{family}/report

docker/
├── holehe/
│   └── Dockerfile        # builds argustrace-holehe (no official image exists)
├── ignorant/
│   ├── Dockerfile        # builds argustrace-ignorant (no official image exists)
│   └── ignorant_json.py  # thin wrapper: calls ignorant's library directly, prints JSON
├── curl/
│   └── Dockerfile        # minimal alpine+curl image, generic — shared by every plugin
│                          # that just needs to fetch a JSON API (crt.sh, IP, French companies)
└── theharvester/
    └── Dockerfile        # clones the official repo at a pinned tag, CLI entrypoint

web/                      # React + Vite frontend, calls the FastAPI backend
```

## Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/); `uv.lock`
pins exact versions and hashes for every package.

```bash
uv sync
```

Docker Desktop (or another Docker engine) must be running for every
plugin except `mock`.

Sherlock and Maigret are pulled straight from pinned registry images.
Holehe, Ignorant, theHarvester, and the generic curl image (used by
crt.sh, IP Lookup, and Recherche d'entreprises — none of them need
anything beyond "fetch a JSON URL") have no official image, so each
must be built locally once:

```bash
docker build -t argustrace-holehe:1.61 -f docker/holehe/Dockerfile .
docker build -t argustrace-ignorant:1.2 -f docker/ignorant/Dockerfile .
docker build -t argustrace-curl:1.0 -f docker/curl/Dockerfile .
docker build -t argustrace-theharvester:4.11.1 -f docker/theharvester/Dockerfile .
docker build -t argustrace-exiftool:1.0 -f docker/exiftool/Dockerfile .
docker build -t argustrace-toutatis:1.0 -f docker/toutatis/Dockerfile .
```

The web frontend needs Node.js/npm; install its dependencies once:

```bash
cd web && npm install
```

## Usage

Every plugin runs the same way — swap the entity and `--plugin` key:

```bash
uv run python -m argustrace.cli investigate <entity> --plugin <key>
```

A table, not a paragraph per tool, on purpose: this list is meant to keep
growing, and prose doesn't scale past a handful of entries.

| Tool                    | Entity   | `--plugin` key          | Speed       | Notes                                                         |
| ----------------------- | -------- | ----------------------- | ----------- | ------------------------------------------------------------- |
| Demo                    | any      | `mock`                  | instant     | no network, proves the pipeline                               |
| Sherlock                | username | `sherlock`              | ~5s         | curated ~10-site list                                         |
| Sherlock (full)         | username | `sherlock-full`         | 1-3 min     | ~400+ sites                                                   |
| Maigret                 | username | `maigret`               | ~6s         | top ~15 sites                                                 |
| Maigret (full)          | username | `maigret-full`          | several min | 3000+ sites                                                   |
| Holehe                  | email    | `holehe`                | ~10s        | ~120 sites                                                    |
| Ignorant                | phone    | `ignorant`              | ~5s         | Amazon/Instagram/Snapchat, E164 format                        |
| crt.sh                  | domain   | `crtsh`                 | ~5s\*       | Certificate Transparency logs                                 |
| theHarvester            | domain   | `theharvester`          | ~10s        | 1 free passive-recon source                                   |
| theHarvester (broad)    | domain   | `theharvester-broad`    | ~30-60s     | 4 free sources combined                                       |
| IP Lookup               | ip       | `ip`                    | ~2-5s       | RDAP + geolocation, no API key                                |
| Recherche d'entreprises | company  | `recherche-entreprises` | ~2s         | France's open company registry                                |
| Image metadata (EXIF)   | image    | `exif`                  | ~2-15s      | any format exiftool reads, URL or upload                      |
| Toutatis                | username | `toutatis`              | ~2-5s       | Instagram profile info; optional session cookie for full data |
| Name analysis           | name     | `name`                  | ~1-2s       | gender/age/nationality prediction, no API key                 |
| Wayback Machine         | domain   | `wayback`               | ~5-20s      | archived hosts/subdomains, no API key                          |
| VATComply               | company  | `vatcomply`             | ~2s         | EU-wide VAT number validation, no API key                     |

Output is a JSON array of `Finding` objects. Run
`uv run python -m argustrace.cli options` with no argument for this same
list from the CLI itself (it reads `TOOL_FAMILIES`, so it can't drift from
the table above).

Every option exposed in the web UI is also available from the CLI via
repeatable `--option`/`-o name=value` flags — run
`uv run python -m argustrace.cli options <plugin>` to see what's available
for a given plugin:

```bash
uv run python -m argustrace.cli options maigret
uv run python -m argustrace.cli investigate <username> --plugin maigret -o timeout=45 -o enrich=true
```

## Web app

A FastAPI backend + React/Vite frontend expose the same `PLUGINS` /
`TOOL_FAMILIES` registry as the CLI, so there's exactly one place a plugin
is registered. Run both in separate terminals:

```bash
uv run uvicorn argustrace.api:app --port 8000    # backend: http://127.0.0.1:8000
cd web && npm run dev                             # frontend: http://localhost:5173
```

Requests block until the plugin finishes (same as the CLI; no background
job queue yet, so `sherlock-full` will hold the request open for 1-3
minutes). FastAPI's interactive docs are at `http://127.0.0.1:8000/docs`.

Built to stay usable well past today's 8 tools:

- **Catalog** (`ToolBrowser.jsx`): a wide card grid, text search over
  name/description, entity-type filter tags (colored by a fixed hue per
  type — username/email/phone/domain — the only iconography in the UI, no
  avatars or emoji), and a "has fast mode" toggle. A card shows a ⚡ fast
  badge only when a family actually has a fast/slow tradeoff — most don't.
- **Run drawer** (`RunDrawer.jsx`): clicking a card slides in a
  configuration panel — a "Fast mode" toggle (the _only_ variant selector;
  turning it off reveals the advanced-options form, no separate dropdown),
  the entity input, and submit. `AdvancedOptionsPanel.jsx` renders each
  family's `options` schema generically (int/str/bool/enum/enum_multi).
  Only real, safe CLI flags are exposed — nothing that needs an API key we
  don't provision, and nothing whose output format we can't parse.
- **Results** (`ResultsPanel.jsx` + `ResultsTray.jsx`): submitting closes
  the drawer and opens a near-fullscreen results modal. "Minimize" parks
  it as a small chip at the bottom of the screen instead of losing it, so
  you can start another investigation while a previous one stays reachable
  — several can be minimized at once; "×" on a chip discards it for good.
  Findings can be exported as CSV or JSON at any time. A finding's evidence
  beyond the diagnostic basics (source/status/URL) shows in a generic
  "Details" column — a coordinates field anywhere becomes a clickable map
  link — so a new plugin's data is visible by default, not just the
  fields a column happens to have been hand-built for.
- **Native reports** (`registry.py`'s `native_reports`, `PreviewModal.jsx`):
  several tools can natively produce their own report (Maigret's HTML,
  theHarvester's XML, ...) beyond what we parse into `Finding`s. Each
  family declares exactly what's available and, when it isn't, why — see
  "Native reports" below. Available ones get a download link _and_ an
  in-app preview (👁): HTML renders in a sandboxed iframe, everything else
  as formatted text, without leaving the page.
- **Version badges** (`VersionBadge.jsx`): green/orange/red/gray pill per
  tool, plus a "Check version" button. Checking is **on-demand, per tool**
  — there is no background refresh or scheduler; a server restart resets
  every badge to gray until re-checked by hand. See "Version checking"
  below.
- **Tool info pages** (`/tools/:family`, via `react-router-dom`):
  description, GitHub/docs links, variants, options, native report
  capabilities, example entities, and a "Use this tool" button that hands
  off to `/` with that family's run drawer already open.

## Version checking

Each tool family declares a `version_check` (`argustrace/versioning.py`):
`pypi` (package name), `dockerhub` (repository), `github_releases` (repo),
or `none` for things that aren't a versioned tool at all — crt.sh (a live
web service) and the mock demo. Checking is triggered per tool by a human
clicking "Check version" (`POST /api/tools/{family}/version-check`); there
is **no scheduler and no auto-refresh** — that was ruled out early in this
project, and a version check is no exception. Results are cached in
memory only (no persistence), so a restart resets every badge to gray.

Status is classified by _index_ in the real, fetched release list (newest
first), not semver arithmetic: pinned == latest → current; one behind →
behind; more than one behind → outdated; pinned not found in the fetched
list (renamed, yanked, or a partial fetch) → **unknown, never a guessed
"outdated"**. Any network/HTTP failure is caught at the checker boundary
and also becomes unknown — the same discipline this project already
applies to Docker failures (`ok=False` → `ERROR`, never an inferred
negative result), applied here to version staleness.

One real gap this surfaced: Sherlock and Maigret are pinned by Docker
image **digest**, not a version string, so each has a `pinned_version`
constant recorded separately in `registry.py` next to the digest — bumping
one must bump the other by hand. Maigret's own Docker tags turned out to
be git-commit SHAs (not semver), discovered by checking the real Docker
Hub API before wiring anything up — its version is checked via PyPI
instead, where the project does publish clean semver releases.

## Native reports

Several underlying tools can produce their own report format on top of
whatever we parse into `Finding`s — Maigret alone supports HTML, PDF,
XMind, Markdown, TXT, a graph, and a Neo4j script. Rather than silently
dropping that, each family in `TOOL_FAMILIES` declares a `native_reports`
list — one entry per format, each one honest about whether it's actually
wired up (`available: bool`) and why when it isn't:

- **Maigret**: HTML implemented (a genuinely richer narrative report —
  location/fullname/interests, per-site tags, archive.org links). PDF is
  listed but unavailable — it needs Maigret's optional `pdf` extra, which
  isn't installed in the pinned image; XMind/graph/Neo4j/Markdown/TXT are
  listed unavailable too (niche viewers, or strictly less info than the
  HTML report already gives).
- **theHarvester**: XML implemented for free — `-f` always writes it
  alongside the JSON we already parse, no extra flag needed.
- **Sherlock**: XLSX is listed but unavailable. Verified directly against
  the pinned image: Sherlock's `--xlsx` writes to a relative path outside
  `--folderoutput` (a quirk in Sherlock itself), which the sandboxed,
  read-only container can't retrieve.
- **crt.sh**: not a CLI tool, so its "native" format is its own live
  search page — exposed as a link, not a download.
- Where a format's data is already fully reflected in our own CSV/JSON
  export (e.g. every tool's raw CSV, Maigret's own JSON report), it's
  listed as such rather than offered as a redundant second download.

Generation is a separate, optional capability from the `Plugin` protocol —
a module may export `generate_report(entity, format) -> bytes`; `run()`
never changes. `GET /api/tools/{family}/report?entity=...&format=...`
calls it **on demand only**: every request re-runs the tool fresh, nothing
is cached or persisted.

## Plugin implementation notes

Per-tool detail (hardening specifics, status-mapping tables, quirks
discovered by testing against the real tool/API, why certain flags are or
aren't exposed) lives in its own file rather than here, so this file stays
scannable:

| Plugin                  | Notes                                                    |
| ----------------------- | --------------------------------------------------------- |
| Sherlock                | [docs/plugins/sherlock.md](docs/plugins/sherlock.md)       |
| Maigret                 | [docs/plugins/maigret.md](docs/plugins/maigret.md)         |
| Holehe                  | [docs/plugins/holehe.md](docs/plugins/holehe.md)           |
| Ignorant                | [docs/plugins/ignorant.md](docs/plugins/ignorant.md)       |
| crt.sh                  | [docs/plugins/crtsh.md](docs/plugins/crtsh.md)             |
| theHarvester            | [docs/plugins/theharvester.md](docs/plugins/theharvester.md) |
| IP Lookup               | [docs/plugins/ip.md](docs/plugins/ip.md)                   |
| Recherche d'entreprises | [docs/plugins/recherche-entreprises.md](docs/plugins/recherche-entreprises.md) |

## Testing

```bash
uv run pytest -v
```

Tests lock the `Status`/`Finding`/`Plugin` contracts using `MockPlugin`,
the entity validation, option-composition (default/custom/clamped), and
result-to-`Status` mapping logic of every real plugin, the version
classification rules in `test_versioning.py` (current/behind/outdated/
unknown-on-error/pinned-not-found, with `httpx.MockTransport` standing in
for PyPI/Docker Hub/GitHub), the CLI's option parsing/coercion and error
messages (`test_cli.py`, via `typer.testing.CliRunner`), and the native
report endpoint's status codes (`test_api.py`, via FastAPI's `TestClient`,
generators mocked) — none of it needs Docker or network access. Actually
running these tools, their native report generation, and live version
checks against real targets is exercised manually, not in the automated
suite.
