import argparse
import logging
from pathlib import Path

from sync_engine.client import SyncEngineClient
from sync_engine.common.logging_helpers import get_color_log_handler


def main() -> None:
    logger = logging.getLogger(__package__)
    logger.setLevel(logging.INFO)
    logger.addHandler(get_color_log_handler())

    parser = argparse.ArgumentParser(description="Sync Engine Client")
    parser.add_argument("source_directory", type=Path, help="The directory to monitor for changes and synchronize.")
    args = parser.parse_args()

    client = SyncEngineClient(target_directory=args.source_directory)
    try:
        started = client.start()
        if started:
            client.wait_for_stop()
        else:
            logger.error("Sync Engine Client failed to start.")
    except Exception as e:
        logger.exception(f"Shutting down. Exception occurred in Sync Engine Client: {e}")
    finally:
        client.stop()


if __name__ == "__main__":
    main()
