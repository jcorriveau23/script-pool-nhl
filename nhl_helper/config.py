"""
Central configuration for every nhl_helper job.

Every value can be overridden with an environment variable prefixed with
``NHL_HELPER_`` (or set in a local ``.env`` file), so nothing below needs a code
change to run against a different database, proxy or output directory.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NHL_HELPER_", env_file=".env", extra="ignore")

    # --- Storage -----------------------------------------------------------
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_database: str = "hockeypool"

    # --- Data sources ------------------------------------------------------
    # The daily-leaders job reads the NHL API through a local proxy rather than
    # hitting api-web.nhle.com directly.
    nhl_proxy_url: str = "http://localhost:3000/api"
    nhl_search_url: str = "https://search.d3.nhle.com/api/v1/search/player"
    cbs_injuries_url: str = "https://www.cbssports.com/nhl/injuries/"
    capwages_url: str = "https://capwages.com/players/active"

    # The rust backend, which owns the season constants (see nhl_helper.season).
    # Every route it serves lives under /api-rust, so the prefix belongs in the
    # base url; behind the reverse proxy this is http://host/api-rust as well.
    pool_api_url: str = "http://localhost:8000/api-rust"

    # Every outbound HTTP call uses this timeout; without one a hung connection
    # blocks the scheduler thread forever.
    request_timeout_seconds: float = 30.0

    # --- Outputs -----------------------------------------------------------
    injured_players_output: Path = Path("injured-players.json")
    non_matching_players_output: Path = Path("non-matching-players-cbs.json")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
