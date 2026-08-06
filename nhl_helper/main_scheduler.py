import logging
import time
from collections.abc import Callable

import schedule

from nhl_helper.nhl.get_daily_points_leaders import fetch_pointers_day
from nhl_helper.nhl.get_injury import fetch_injured_players_cbs


def guard(job: Callable[[], None]) -> Callable[[], None]:
    """
    Keep one failing job from taking the whole scheduler down.

    The jobs themselves raise on failure so that running them from the CLI exits
    non-zero; only the long-running scheduler swallows the error, and it logs the
    full traceback rather than just the message.
    """

    def wrapper() -> None:
        try:
            job()
        except Exception:
            logging.exception(f"Scheduled job '{job.__name__}' failed")

    wrapper.__name__ = job.__name__
    return wrapper


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Task scheduling
    # After every 3mins get_live_day_points_leaders() is called.
    schedule.every(3).minutes.do(guard(fetch_pointers_day))
    schedule.every(1).hours.do(guard(fetch_injured_players_cbs))

    logging.info("start the scheduling!")
    while True:
        # Checks whether a scheduled task
        # is pending to run or not
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
