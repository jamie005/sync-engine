import argparse
from pathlib import Path

from sync_engine.server import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Sync Engine REST server")
    parser.add_argument(
        "directory",
        type=Path,
        help="Directory where files can be created, deleted, and renamed",
    )
    args = parser.parse_args()

    base_directory: Path = args.directory.resolve()
    if not base_directory.exists() or not base_directory.is_dir():
        raise SystemExit(f"Directory does not exist or is not a directory: {base_directory}")

    app = create_app(base_directory)
    app.run(host="127.0.0.1", port=5000)


if __name__ == "__main__":
    main()
