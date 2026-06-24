"""Long-running daemon that triggers the pipeline at a configured time."""
from __future__ import annotations

import time

import schedule

from src.config_loader import load_config
from src.logger_setup import setup_logger
from src.main import run_pipeline


def main() -> None:
    cfg = load_config()
    logger = setup_logger(
        log_dir=cfg["paths"]["log_folder"],
        file_name=cfg["logging"]["file_name"],
        level=cfg["logging"]["level"],
    )
    run_time = cfg["schedule"]["run_time"]
    mode = cfg["schedule"]["run_mode"]

    if mode == "once":
        logger.info("Running once and exiting.")
        run_pipeline()
        return

    logger.info("Scheduler started. Daily run at %s.", run_time)
    schedule.every().day.at(run_time).do(run_pipeline)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
