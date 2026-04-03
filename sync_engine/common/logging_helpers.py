from colorlog import ColoredFormatter, StreamHandler


_LOGGER_FORMAT = "%(light_black)s%(asctime)s%(reset)s %(log_color)s%(levelname)-8s%(reset)s %(blue)s%(module)s%(reset)s %(message)s"


def get_color_log_handler() -> StreamHandler:
    """Create and return a colored stream handler for logging."""
    handler = StreamHandler()
    handler.setFormatter(ColoredFormatter(_LOGGER_FORMAT))
    return handler
