"""Initial index — kept for manual use only. App auto-indexes on startup."""
import argparse
import sys
from pathlib import Path
import app.config as config
from app.logger import logger
from core.indexing.index_builder import IndexBuilder


def main():
    parser = argparse.ArgumentParser(
        description="Manually index a directory (app auto-indexes on startup)"
    )
    parser.add_argument("--path", type=str, help="Directory to index")
    parser.add_argument("--recursive", type=bool, default=True)
    args = parser.parse_args()

    if args.path:
        paths = [args.path]
    else:
        paths = config.WATCH_PATHS
        logger.info(f"No --path given. Using auto-detected paths: {paths}")

    index_builder = IndexBuilder()
    total = 0
    for path in paths:
        count = index_builder.index_directory(path, args.recursive)
        total += count

    index_builder.save()
    logger.info(f"✅ Done. Total indexed: {total}")

    # Mark first run complete
    Path(config.FIRST_RUN_FLAG).touch()


if __name__ == "__main__":
    main()
