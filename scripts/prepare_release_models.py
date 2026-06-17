"""Prepare bundled model assets for NeuCockpit release builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
MODELS_DIR = ROOT / "storage" / "models"
BGE_DIR = MODELS_DIR / "BAAI" / "bge-small-en-v1.5"
BGE_REPO = "BAAI/bge-small-en-v1.5"
BGE_FILES = [
    "config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "onnx/model.onnx",
]


def _download_bge() -> None:
    required = [BGE_DIR / item for item in BGE_FILES]
    if all(path.is_file() and path.stat().st_size > 0 for path in required):
        print(f"BGE model already prepared at {BGE_DIR}")
        return

    from huggingface_hub import hf_hub_download

    BGE_DIR.mkdir(parents=True, exist_ok=True)
    for filename in BGE_FILES:
        print(f"Downloading BGE asset: {filename}")
        hf_hub_download(
            repo_id=BGE_REPO,
            filename=filename,
            local_dir=str(BGE_DIR),
        )
    print(f"BGE model prepared at {BGE_DIR}")


def _download_qwen() -> None:
    if os.environ.get("NEURON_SKIP_QWEN_GGUF") == "1":
        print("Skipping Qwen GGUF bundle because NEURON_SKIP_QWEN_GGUF=1")
        return

    # services.model_manager chooses storage/models when it already exists.
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    from services.model_manager import download_llm_model

    model_path = download_llm_model()
    print(f"Qwen GGUF prepared at {model_path}")


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    _download_bge()
    _download_qwen()


if __name__ == "__main__":
    main()
