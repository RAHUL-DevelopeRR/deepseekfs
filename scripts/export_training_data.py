"""
Neuron — Export Training Data for LoRA Fine-Tuning
====================================================
Exports RLHF feedback data from SQLite → JSONL format.

Usage:
    python scripts/export_training_data.py [--positive-only] [--output path]

Output format (JSONL, one per line):
    {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
"""
import argparse
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def main():
    parser = argparse.ArgumentParser(
        description="Export RLHF feedback data for fine-tuning"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("storage/training_data.jsonl"),
        help="Output JSONL file path",
    )
    parser.add_argument(
        "--positive-only",
        action="store_true",
        help="Only export positive feedback",
    )
    parser.add_argument(
        "--corrections",
        type=Path,
        help="Also export intent corrections to this path",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print feedback statistics",
    )
    args = parser.parse_args()

    from services.feedback import get_feedback_store

    store = get_feedback_store()

    if args.stats:
        stats = store.get_stats()
        print(f"\n{'='*40}")
        print(f"  RLHF Feedback Statistics")
        print(f"{'='*40}")
        print(f"  Total entries:   {stats['total']}")
        print(f"  Positive (👍):   {stats['positive']}")
        print(f"  Negative (👎):   {stats['negative']}")
        print(f"  Positive rate:   {stats['positive_rate']}%")
        print(f"\n  Top failures:")
        for f in stats['top_failures']:
            print(f"    - \"{f['query'][:50]}\" ({f['count']}x)")
        print(f"{'='*40}\n")

    count = store.export_jsonl(args.output, positive_only=args.positive_only)
    print(f"Exported {count} entries to {args.output}")

    if args.corrections:
        n = store.export_intent_corrections(args.corrections)
        print(f"Exported {n} intent corrections to {args.corrections}")


if __name__ == "__main__":
    main()
