"""
Shared MongoDB access.

Jobs call :func:`get_database` inside their functions rather than binding a
module-level client, so importing a module never opens a connection and tests
can point at a different database.
"""

from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from nhl_helper.config import get_settings


@lru_cache(maxsize=1)
def get_database() -> Database:
    settings = get_settings()
    return MongoClient(settings.mongo_uri)[settings.mongo_database]
