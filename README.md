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

Each job is installed as a command:

| Command | What it does | Source |
| --- | --- | --- |
| `nhl-scheduler` | Long-running daemon: daily leaders every 3 min, injuries hourly | — |
| `nhl-daily-leaders` | Fetch goals/assists/goalie lines for the day into `day_leaders` | NHL API (via proxy) |
| `nhl-injuries` | Write the current injury list to a JSON file for the frontend | cbssports.com |
| `nhl-active-players` | Sync the roster of active players into `players` | search.d3.nhle.com |
| `nhl-contracts` | Add age, cap hit and contract expiry to `players` | capwages.com |
| `nhl-cumulate-stats` | Rebuild season totals in `players` from `day_leaders` | local database |
| `nhl-update-pool-players` | Refresh the player info embedded in each pool | local database |

`nhl-daily-leaders` also backfills a date range:

```bash
nhl-daily-leaders --start 2026-03-01 --end 2026-03-12
```

`nhl-cumulate-stats` erases every player's stats before recomputing them from
`day_leaders`, so it needs a complete set of daily documents for the season.

## Collections

- `players` — one document per NHL player: identity, team, position, contract, season totals.
- `day_leaders` — one document per date: which players scored and which played.
- `pools` — the pools themselves, with an embedded copy of player info per pool.

## Development

```bash
uv run ruff check .   # lint
uv run mypy           # type check
uv run pytest         # tests
```

Tests cover the pure parsing and accumulation logic and need neither a network
connection nor a database.
