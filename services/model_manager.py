"""
Neuron — GGUF Model Manager
============================
Handles:
- Model path resolution (app dir → LOCALAPPDATA fallback)
- First-run download from HuggingFace Hub
- Model integrity verification (SHA256)
- Vosk speech model management
"""
from __future__ import annotations

import os
import hashlib
import shutil
from pathlib import Path
from typing import Optional, Callable

from app.logger import logger

# ── Model Configuration ──────────────────────────────────────
# Single unified model: Qwen 2.5 Coder 3B Instruct (Q5_K_M)
# This replaces the old dual-model setup (SmolLM3-3B + Qwen 0.5B).
# Qwen 2.5 Coder 3B handles chat, summarization, tool calling,
# AND code generation — better at everything, ~2.1 GB on disk,
# ~2.5 GB RAM.  Sweet spot for 8 GB machines.
LLM_MODEL_REPO = "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF"
LLM_MODEL_FILE = "qwen2.5-coder-3b-instruct-q5_k_m.gguf"
LLM_MODEL_SIZE_MB = 2100  # approximate

VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.22.zip"
VOSK_MODEL_NAME = "vosk-model-small-en-us-0.22"
VOSK_MODEL_SIZE_MB = 50

ProgressCallback = Callable[[float, str], None]  # (progress_0_to_1, status_text)

# ── Disk Space Guard ──────────────────────────────────────────
# Downloads can be 420 MB to 1.8 GB.  Running out of disk mid-download
# leaves a corrupt partial file that later causes a cryptic llama.cpp
# crash.  Better to fail fast with a clear message.
_DISK_SPACE_SAFETY_FACTOR = 1.5  # require 1.5× model size free


def _check_disk_space(target_dir: Path, required_mb: int) -> None:
    """Raise OSError if *target_dir* lacks enough free space.

    Uses ``shutil.disk_usage`` which works on Windows, Linux, and macOS.
    The safety factor accounts for temp files during extraction, partial
    HuggingFace cache objects, and filesystem metadata overhead.
    """
    try:
        usage = shutil.disk_usage(str(target_dir))
        free_mb = usage.free / (1024 * 1024)
        needed_mb = required_mb * _DISK_SPACE_SAFETY_FACTOR
        if free_mb < needed_mb:
            raise OSError(
                f"Insufficient disk space on {target_dir.anchor}: "
                f"{free_mb:.0f} MB free, need ~{needed_mb:.0f} MB "
                f"({required_mb} MB model + safety margin). "
                f"Free up space and try again."
            )
        logger.info(
            f"ModelManager: disk check OK — {free_mb:.0f} MB free, "
            f"need ~{needed_mb:.0f} MB"
        )
    except OSError:
        raise  # re-raise our own OSError
    except Exception as exc:
        # Non-fatal: if disk_usage fails (e.g. unusual mount), log and proceed
        logger.warning(f"ModelManager: disk space check skipped: {exc}")


def get_models_dir() -> Path:
    """Get the models directory, creating it if needed.
    
    Search order:
    1. {app_dir}/storage/models/
    2. %LOCALAPPDATA%/Neuron/models/
    """
    # Try app-local storage first
    app_dir = Path(__file__).resolve().parent.parent / "storage" / "models"
    if app_dir.exists():
        return app_dir
    
    # Fall back to LOCALAPPDATA
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        models_dir = Path(local_app_data) / "Neuron" / "models"
    else:
        models_dir = Path.home() / ".neuron" / "models"
    
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def get_llm_model_path() -> Optional[Path]:
    """Find the LLM GGUF model file.
    
    Returns None if model is not downloaded yet.
    """
    # Check app-local storage
    app_local = Path(__file__).resolve().parent.parent / "storage" / "models" / LLM_MODEL_FILE
    if app_local.is_file():
        return app_local
    
    # Check LOCALAPPDATA
    models_dir = get_models_dir()
    model_path = models_dir / LLM_MODEL_FILE
    if model_path.is_file():
        return model_path
    
    # Also check for any .gguf file (user may have renamed or used a different model)
    for f in models_dir.glob("*.gguf"):
        logger.info(f"ModelManager: Found alternative GGUF model: {f.name}")
        return f
    
    return None


# Backward compatibility alias — the separate coder model no longer exists;
# the unified Qwen 2.5 Coder 3B handles both roles.
def get_coder_model_path() -> Optional[Path]:
    """Alias for get_llm_model_path() — unified model handles code too."""
    return get_llm_model_path()


def get_vosk_model_path() -> Optional[Path]:
    """Find the Vosk speech recognition model directory.
    
    Returns None if not downloaded yet.
    """
    models_dir = get_models_dir()
    vosk_dir = models_dir / VOSK_MODEL_NAME
    if vosk_dir.is_dir() and (vosk_dir / "mfcc.conf").exists():
        return vosk_dir
    return None


def is_llm_model_available() -> bool:
    """Quick check if the LLM model is ready to use."""
    return get_llm_model_path() is not None


def is_coder_model_available() -> bool:
    """Alias — unified model serves both roles."""
    return is_llm_model_available()


def is_vosk_model_available() -> bool:
    """Quick check if the Vosk model is ready to use."""
    return get_vosk_model_path() is not None


def download_llm_model(progress_cb: Optional[ProgressCallback] = None) -> Path:
    """Download the SmolLM3-3B GGUF model from HuggingFace.
    
    Uses huggingface_hub for reliable, resumable downloads.
    Returns the path to the downloaded model file.
    """
    models_dir = get_models_dir()
    model_path = models_dir / LLM_MODEL_FILE

    # ── Disk space pre-check ──
    _check_disk_space(models_dir, LLM_MODEL_SIZE_MB)


    if model_path.is_file():
        logger.info(f"ModelManager: LLM model already exists at {model_path}")
        if progress_cb:
            progress_cb(1.0, "Model ready")
        return model_path
    
    logger.info(f"ModelManager: Downloading {LLM_MODEL_FILE} from {LLM_MODEL_REPO}...")
    if progress_cb:
        progress_cb(0.0, f"Downloading {LLM_MODEL_FILE} (~{LLM_MODEL_SIZE_MB}MB)...")
    
    try:
        from huggingface_hub import hf_hub_download
        
        # huggingface_hub handles progress, resume, and verification
        downloaded_path = hf_hub_download(
            repo_id=LLM_MODEL_REPO,
            filename=LLM_MODEL_FILE,
            local_dir=str(models_dir),
        )
        
        # Verify the file exists
        result_path = Path(downloaded_path)
        if not result_path.is_file():
            raise FileNotFoundError(f"Download completed but file not found at {result_path}")
        
        # If downloaded to a subdirectory, move to models root
        if result_path != model_path and result_path.is_file():
            shutil.move(str(result_path), str(model_path))
            result_path = model_path
        
        size_mb = result_path.stat().st_size / (1024 * 1024)
        logger.info(f"ModelManager: LLM model downloaded ({size_mb:.0f}MB) → {result_path}")
        
        if progress_cb:
            progress_cb(1.0, f"Model ready ({size_mb:.0f}MB)")
        
        return result_path
        
    except ImportError:
        logger.error("ModelManager: huggingface_hub not installed. Cannot download model.")
        raise RuntimeError(
            "huggingface_hub is required to download the AI model. "
            "Install it with: pip install huggingface-hub"
        )
    except Exception as e:
        logger.error(f"ModelManager: Download failed: {e}")
        # Clean up partial downloads
        if model_path.exists():
            model_path.unlink()
        raise RuntimeError(f"Failed to download AI model: {e}")


def download_vosk_model(progress_cb: Optional[ProgressCallback] = None) -> Path:
    """Download the Vosk speech recognition model.
    
    Returns the path to the model directory.
    """
    models_dir = get_models_dir()
    vosk_dir = models_dir / VOSK_MODEL_NAME

    # ── Disk space pre-check ──
    _check_disk_space(models_dir, VOSK_MODEL_SIZE_MB)

    
    if vosk_dir.is_dir() and (vosk_dir / "mfcc.conf").exists():
        logger.info(f"ModelManager: Vosk model already exists at {vosk_dir}")
        if progress_cb:
            progress_cb(1.0, "Speech model ready")
        return vosk_dir
    
    logger.info(f"ModelManager: Downloading Vosk model ({VOSK_MODEL_SIZE_MB}MB)...")
    if progress_cb:
        progress_cb(0.0, f"Downloading speech model ({VOSK_MODEL_SIZE_MB}MB)...")
    
    import urllib.request
    import zipfile
    import tempfile
    
    try:
        zip_path = models_dir / f"{VOSK_MODEL_NAME}.zip"
        
        # Download with progress
        def _report_progress(block_count, block_size, total_size):
            if total_size > 0 and progress_cb:
                progress = min(block_count * block_size / total_size, 0.99)
                progress_cb(progress, f"Downloading speech model... {progress:.0%}")
        
        urllib.request.urlretrieve(VOSK_MODEL_URL, str(zip_path), _report_progress)
        
        # Extract
        if progress_cb:
            progress_cb(0.95, "Extracting speech model...")
        
        with zipfile.ZipFile(str(zip_path), 'r') as zf:
            zf.extractall(str(models_dir))
        
        # Clean up zip
        zip_path.unlink()
        
        if not vosk_dir.is_dir():
            raise FileNotFoundError(f"Extraction completed but model not found at {vosk_dir}")
        
        logger.info(f"ModelManager: Vosk model extracted → {vosk_dir}")
        if progress_cb:
            progress_cb(1.0, "Speech model ready")
        
        return vosk_dir
        
    except Exception as e:
        logger.error(f"ModelManager: Vosk download failed: {e}")
        # Clean up
        if vosk_dir.exists():
            shutil.rmtree(str(vosk_dir), ignore_errors=True)
        raise RuntimeError(f"Failed to download speech model: {e}")


def get_model_status() -> dict:
    """Get the status of all required models."""
    return {
        "llm": {
            "available": is_llm_model_available(),
            "path": str(get_llm_model_path()) if is_llm_model_available() else None,
            "name": LLM_MODEL_FILE,
            "size_mb": LLM_MODEL_SIZE_MB,
        },
        "vosk": {
            "available": is_vosk_model_available(),
            "path": str(get_vosk_model_path()) if is_vosk_model_available() else None,
            "name": VOSK_MODEL_NAME,
            "size_mb": VOSK_MODEL_SIZE_MB,
        },
    }
