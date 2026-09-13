"""
Season dates, read from the rust backend.

The backend owns the season constants and exposes them on ``GET /season-info``,
the same endpoint the frontend reads. Keeping a second copy here meant editing
this repo every September, and a stale copy silently gives the cumulator a date
range that no longer matches the pools it feeds.
"""

from datetime import date
from functools import lru_cache
from typing import Any

import requests
from pydantic import BaseModel, field_validator

from nhl_helper.config import get_settings


def parse_season_date(value: str) -> date:
    """
    Parse a date from the season-info payload.

    The backend hardcodes these as strings and does not always zero-pad them, so
    ``2025-10-7`` has to parse as well as ``2025-10-07``; ``date.fromisoformat``
    rejects the former.
    """
    year, month, day = (int(part) for part in value.split("-"))
    return date(year, month, day)


class SeasonInfo(BaseModel):
    """The ``GET /season-info`` payload, with the dates parsed."""

    start_season_date: date
    end_season_date: date
    season: int
    trade_deadline_date: date

    @field_validator("start_season_date", "end_season_date", "trade_deadline_date", mode="before")
    @classmethod
    def _parse_dates(cls, value: Any) -> Any:
        return parse_season_date(value) if isinstance(value, str) else value


@lru_cache(maxsize=1)
def get_season_info() -> SeasonInfo:
    """
    Fetch the current season info, once per process.

    Raises if the backend is unreachable: every caller needs the real season to
    write correct data, and guessing would corrupt the collections it updates.
    """
    settings = get_settings()

    response = requests.get(f"{settings.pool_api_url}/season-info", timeout=settings.request_timeout_seconds)
    response.raise_for_status()

    return SeasonInfo(**response.json())
