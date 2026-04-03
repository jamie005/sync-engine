import logging

from sync_engine.client import SyncEngineClient
from sync_engine.common.logging_helpers import get_color_log_handler


def main() -> None:
    logger = logging.getLogger(__package__)
    logger.setLevel(logging.INFO)
    logger.addHandler(get_color_log_handler())

    client = SyncEngineClient(target_directory="tests")
    try:
        client.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.info(f"Shutting down. Exception occurred in Sync Engine Client: {e}")
    finally:
        logger.info("Sync Engine Client stopped.")


if __name__ == "__main__":
    main()
