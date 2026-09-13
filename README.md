# script-pool-nhl

Scrapers that feed the NHL hockey pool: they pull player, game, injury and
contract data from public sources and store it in a local MongoDB database
(`hockeypool`).

## Setup

```bash
uv sync --all-groups
```

Everything is configured through environment variables prefixed with
`NHL_HELPER_`, or a `.env` file in the working directory. See
[.env.example](.env.example) for the full list — copy it and adjust:

```bash
cp .env.example .env
```

## Jobs

Each job is installed as a command and is a one-shot process: it runs, does its
work, and exits non-zero if it fails. Nothing here is a daemon — see
[Scheduling](#scheduling).

| Command | What it does | Source |
| --- | --- | --- |
| `nhl-daily-leaders` | Fetch goals/assists/goalie lines for the day into `day_leaders` | NHL API (via proxy) |
| `nhl-injuries` | Write the current injury list to a JSON file for the frontend | cbssports.com |
| `nhl-active-players` | Sync the roster of active players into `players` | search.d3.nhle.com |
| `nhl-contracts` | Add age, cap hit and contract expiry to `players` | capwages.com |
| `nhl-cumulate-stats` | Rebuild season totals in `players` from `day_leaders` | local database |
| `nhl-update-pool-players` | Refresh the player info embedded in each pool | local database |

The season dates and the current season id are not configured here: the two
season-aware jobs read them from the rust backend's `GET /season-info`, so the
season rolls over without a change in this repo. Both jobs fail if that endpoint
is unreachable — see `NHL_HELPER_POOL_API_URL`.

`nhl-daily-leaders` also backfills a date range:

```bash
nhl-daily-leaders --start 2026-03-01 --end 2026-03-12
```

`nhl-cumulate-stats` erases every player's stats before recomputing them from
`day_leaders`, so it needs a complete set of daily documents for the season.

## Scheduling

Every job runs on a systemd timer on the host rather than from a scheduler
process inside the repo:

| When | What runs |
| --- | --- |
| every 3 min, 12:00–02:57 | `nhl-daily-leaders` |
| hourly | `nhl-injuries` |
| 05:00 | `nhl-active-players`, then `nhl-contracts`, then `nhl-cumulate-stats` |
| 05:30 | `nhl-update-pool-players` |

The three 05:00 jobs are one unit (`nhl-nightly.service`) run in sequence, not
three timers on the same minute. All three read a player document, edit it and
write it back, and the first two write the whole document, so overlapping runs
would quietly undo each other — a roster sync that read a player before
`nhl-cumulate-stats` erased its stats would put the stale numbers straight back.
The 05:30 job then copies those refreshed documents into each pool.

`nhl-daily-leaders` only runs during the hours a game can be in progress — noon
through 02:57 local, matinees to west-coast overtime. Outside that window the
schedule cannot change, so the nine idle hours were only costing container
starts. It also means the 05:00 chain never reads `day_leaders` while the poller
is writing it. The host runs on ET, which those bounds assume.

The units in [deploy/systemd](deploy/systemd) expect a `scraper` service in
`/srv/slapshot/docker-compose.yml` that carries the environment and the volume
for the injury JSON, but that service is never brought `up` — every run is a
fresh container:

```bash
sudo cp deploy/systemd/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nhl-daily-leaders.timer nhl-injuries.timer \
                          nhl-nightly.timer nhl-update-pool-players.timer
```

`nhl-job@.service` is a template whose instance name is the command, which is
also how a single job is run by hand:

```bash
sudo systemctl start nhl-job@nhl-contracts.service
systemctl list-timers 'nhl-*'          # when each one next fires
journalctl -u nhl-nightly -f           # what the last runs did
```

A run that overruns its interval does not stack up: systemd drops the trigger
while the instance is still active. `OnCalendar=` times are the host's local
time.

## Collections

- `players` — one document per NHL player: identity, team, position, contract, season totals.
- `day_leaders` — one document per date: which players scored and which played.
- `pools` — the pools themselves, with an embedded copy of player info per pool.

## Development

```bash
uv run ruff check .          # lint
uv run mypy                  # type check
uv run pytest                # tests
uv run pytest --cov          # tests with a coverage report
```

Tests cover the pure parsing and accumulation logic and need neither a network
connection nor a database.

Coverage is measured over `nhl_helper` with branch coverage on, minus the two
jobs that are only database and file wiring (`get_injury`,
`update_pool_players_info`). `fail_under` in [pyproject.toml](pyproject.toml) is
a floor that keeps a change from dropping what is already covered — raise it
when coverage genuinely rises. `--cov` is not on by default so that running a
single test file stays quick and cannot trip the threshold.

[CI](.github/workflows/ci.yml) runs those same commands on every pull request,
and separately builds the Docker image and smoke-tests it: a bare run exits 64,
every `nhl-*` command is on `PATH`, every job module imports, and the container
runs as `appuser`. That build is amd64 only — the release workflow is what
builds and publishes arm64 on a native runner.
