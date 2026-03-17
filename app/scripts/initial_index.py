"""Initial full-directory index"""
import argparse
import sys
from pathlib import Path
import app.config as config
from app.logger import logger
from core.indexing.index_builder import IndexBuilder

def main():
    parser = argparse.ArgumentParser(description="Create initial index")
    parser.add_argument(
        "--path",
        type=str,
        help="Directory to index (default: sample_documents)"
    )
    parser.add_argument(
        "--recursive",
        type=bool,
        default=True,
        help="Index recursively"
    )
    
    args = parser.parse_args()
    index_path = args.path or str(Path(config.BASE_DIR) / "sample_documents")
    
    # Create sample directory if needed
    sample_dir = Path(index_path)
    sample_dir.mkdir(parents=True, exist_ok=True)
    
    # Create sample files
    if not list(sample_dir.glob("*")):
        logger.info("Creating sample documents...")
        (sample_dir / "sample1.txt").write_text("Invoice from last week for Q1 budget analysis")
        (sample_dir / "sample2.txt").write_text("Recent Python projects and machine learning notebooks")
        (sample_dir / "sample3.txt").write_text("Marketing strategy document with revenue forecasts")
    
    logger.info(f"Indexing directory: {index_path}")
    index_builder = IndexBuilder()
    count = index_builder.index_directory(index_path, args.recursive)
    index_builder.save()
    
    logger.info(f"✅ Initial index created. Total documents: {count}")

if __name__ == "__main__":
    main()
