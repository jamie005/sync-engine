import logging
from multiprocessing import Queue
import time

from sync_engine.client.directory_monitoring.directory_monitor import DirectoryMonitor
from sync_engine.common.logging_helpers import get_color_log_handler


def main() -> None:
    logger = logging.getLogger(__package__)
    logger.setLevel(logging.INFO)
    logger.addHandler(get_color_log_handler())

    DirectoryMonitor("tests", Queue()).start()
    while True:
        time.sleep(100)


if __name__ == "__main__":
    main()
