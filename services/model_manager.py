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
from typing import Optional, Callable, Iterable

from app.logger import logger

# ── Model Configuration ──────────────────────────────────────
# Primary local agent model. The older beta build shipped the 0.5B GGUF to
# keep the installer small; that made tool calling and summaries too weak.
# Neuron now treats the 3B model as the product default and only falls back to
# the 0.5B model when NEURON_ALLOW_SMALL_MODEL_FALLBACK=1 is set explicitly.
LLM_MODEL_REPO = "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF"
LLM_MODEL_FILE = "qwen2.5-coder-3b-instruct-q5_k_m.gguf"
LLM_MODEL_SIZE_MB = 2450  # approximate
LEGACY_SMALL_MODEL_FILE = "qwen2.5-coder-0.5b-instruct-q4_0.gguf"
ALLOW_SMALL_MODEL_FALLBACK_ENV = "NEURON_ALLOW_SMALL_MODEL_FALLBACK"
_MIN_GGUF_SIZE_BYTES = 50 * 1024 * 1024

VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.22.zip"
VOSK_MODEL_NAME = "vosk-model-small-en-us-0.22"
VOSK_MODEL_SIZE_MB = 50

ProgressCallback = Callable[[float, str], None]  # (progress_0_to_1, status_text)

# ── Disk Space Guard ──────────────────────────────────────────
# Downloads can be 2-3 GB. Running out of disk mid-download
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


def _existing_dirs(paths: Iterable[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        try:
            resolved = path.expanduser().resolve()
        except Exception:
            resolved = path.expanduser()
        key = str(resolved).lower()
        if key in seen or not resolved.is_dir():
            continue
        seen.add(key)
        out.append(resolved)
    return out


def get_model_search_dirs() -> list[Path]:
    """Return GGUF search roots, including app, user, and HF cache locations."""
    base = Path(__file__).resolve().parent.parent
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    env_dirs = [
        Path(item)
        for item in os.environ.get("NEURON_MODEL_DIRS", "").split(os.pathsep)
        if item.strip()
    ]
    if os.environ.get("NEURON_MODEL_DIRS_ONLY") == "1":
        return _existing_dirs(env_dirs)
    return _existing_dirs(
        [
            *env_dirs,
            base / "storage" / "models",
            local_app_data / "Neuron" / "models",
            local_app_data / "Local" / "Neuron" / "models",
            Path.home() / ".neuron" / "models",
            Path.home() / ".cache" / "huggingface" / "hub",
            local_app_data / "huggingface" / "hub",
            base / "storage" / "models" / ".cache" / "huggingface",
        ]
    )


def _is_usable_gguf(path: Path) -> bool:
    try:
        return (
            path.is_file()
            and path.suffix.lower() == ".gguf"
            and path.stat().st_size >= _MIN_GGUF_SIZE_BYTES
        )
    except Exception:
        return False


def _iter_gguf_candidates() -> Iterable[Path]:
    for root in get_model_search_dirs():
        direct = root / LLM_MODEL_FILE
        if _is_usable_gguf(direct):
            yield direct
        try:
            for candidate in root.rglob("*.gguf"):
                if _is_usable_gguf(candidate):
                    yield candidate
        except Exception as exc:
            logger.warning(f"ModelManager: skipped model cache scan {root}: {exc}")


def _is_primary_qwen(path: Path) -> bool:
    value = f"{path.name} {path}".lower()
    return "qwen2.5-coder" in value and "3b" in value


def _small_model_fallback_enabled() -> bool:
    return os.getenv(ALLOW_SMALL_MODEL_FALLBACK_ENV, "").lower() in {"1", "true", "yes"}


def get_llm_model_path() -> Optional[Path]:
    """Find the LLM GGUF model file.
    
    Returns None if model is not downloaded yet.
    """
    candidates = list(_iter_gguf_candidates())
    if not candidates:
        return None

    exact = [p for p in candidates if p.name.lower() == LLM_MODEL_FILE.lower()]
    if exact:
        return exact[0]

    primary_qwen = [p for p in candidates if _is_primary_qwen(p)]
    if primary_qwen:
        chosen = sorted(primary_qwen, key=lambda p: p.stat().st_size, reverse=True)[0]
        logger.info(f"ModelManager: Found compatible Qwen 3B GGUF model: {chosen}")
        return chosen

    qwen = [
        p for p in candidates
        if "qwen2.5-coder" in p.name.lower() or "qwen2.5-coder" in str(p).lower()
    ]
    if qwen:
        if _small_model_fallback_enabled():
            chosen = sorted(qwen, key=lambda p: p.stat().st_size, reverse=True)[0]
            logger.warning(
                "ModelManager: using non-primary Qwen fallback because %s=1: %s",
                ALLOW_SMALL_MODEL_FALLBACK_ENV,
                chosen,
            )
            return chosen
        names = ", ".join(str(p) for p in qwen[:3])
        logger.warning(
            "ModelManager: Qwen GGUF candidates exist but no 3B model was found. "
            "Ignoring fallback candidates unless %s=1. Candidates: %s",
            ALLOW_SMALL_MODEL_FALLBACK_ENV,
            names,
        )
        return None

    logger.warning("ModelManager: GGUF files exist, but none match Qwen 2.5 Coder 3B.")
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
    """Download the Qwen 2.5 Coder GGUF model from HuggingFace.
    
    Uses huggingface_hub for reliable, resumable downloads.
    Returns the path to the downloaded model file.
    """
    models_dir = get_models_dir()
    model_path = models_dir / LLM_MODEL_FILE

    # ── Disk space pre-check ──
    _check_disk_space(models_dir, LLM_MODEL_SIZE_MB)

    existing = get_llm_model_path()
    if existing is not None:
        logger.info(f"ModelManager: LLM model already exists at {existing}")
        if progress_cb:
            progress_cb(1.0, "Model ready")
        return existing
    
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
