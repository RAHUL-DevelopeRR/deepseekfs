"""
DeepSeekFS — Encyl Auto-Setup (Python)
=======================================
Called on first launch if Ollama is not detected.
Downloads Ollama, installs it, and pulls the model — all from within the app.
"""
import subprocess
import sys
import os
import json
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

from app.logger import logger


OLLAMA_DOWNLOAD_URL = "https://ollama.com/download/OllamaSetup.exe"
MODEL = "llama3.2:3b"
OLLAMA_API = "http://localhost:11434"


def is_ollama_installed() -> bool:
    """Check if ollama command is available."""
    try:
        r = subprocess.run(["ollama", "--version"], capture_output=True, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Check default installation path
        default_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if default_path.exists():
            os.environ["PATH"] += f";{default_path.parent}"
            return True
        return False


def is_ollama_running() -> bool:
    """Check if Ollama API is responding."""
    try:
        req = Request(f"{OLLAMA_API}/api/tags", method="GET")
        resp = urlopen(req, timeout=3)
        return resp.status == 200
    except Exception:
        return False


def is_model_installed(model: str = MODEL) -> bool:
    """Check if the model is already pulled."""
    try:
        req = Request(f"{OLLAMA_API}/api/tags", method="GET")
        resp = urlopen(req, timeout=3)
        data = json.loads(resp.read())
        return any(model in m.get("name", "") for m in data.get("models", []))
    except Exception:
        return False


def download_ollama(progress_callback=None) -> bool:
    """Download OllamaSetup.exe to temp directory."""
    installer_path = Path(os.environ["TEMP"]) / "OllamaSetup.exe"
    try:
        logger.info("Downloading Ollama installer...")
        if progress_callback:
            progress_callback("Downloading Ollama installer...")

        req = Request(OLLAMA_DOWNLOAD_URL)
        resp = urlopen(req, timeout=300)
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0

        with open(installer_path, "wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total > 0:
                    pct = int(downloaded / total * 100)
                    progress_callback(f"Downloading Ollama... {pct}%")

        logger.info(f"Ollama installer downloaded: {installer_path}")
        return True
    except Exception as e:
        logger.error(f"Ollama download failed: {e}")
        return False


def install_ollama(silent: bool = False) -> bool:
    """Run OllamaSetup.exe."""
    installer_path = Path(os.environ["TEMP"]) / "OllamaSetup.exe"
    if not installer_path.exists():
        return False
    try:
        logger.info("Installing Ollama...")
        args = [str(installer_path)]
        if silent:
            args.append("/S")
        subprocess.run(args, timeout=300)

        # Add to PATH
        ollama_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama"
        if ollama_dir.exists():
            os.environ["PATH"] += f";{ollama_dir}"

        # Clean up
        installer_path.unlink(missing_ok=True)

        return is_ollama_installed()
    except Exception as e:
        logger.error(f"Ollama install failed: {e}")
        return False


def start_ollama_server() -> bool:
    """Start Ollama serve in background."""
    if is_ollama_running():
        return True
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        # Wait for server
        for _ in range(15):
            time.sleep(1)
            if is_ollama_running():
                logger.info("Ollama server started")
                return True
        return False
    except Exception as e:
        logger.error(f"Failed to start Ollama: {e}")
        return False


def pull_model(model: str = MODEL, progress_callback=None) -> bool:
    """Pull the AI model."""
    if is_model_installed(model):
        logger.info(f"Model {model} already installed")
        return True
    try:
        if progress_callback:
            progress_callback(f"Pulling {model} (~2GB)...")
        logger.info(f"Pulling model: {model}")
        result = subprocess.run(
            ["ollama", "pull", model],
            capture_output=True,
            text=True,
            timeout=600,  # 10 min timeout for slow connections
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Model pull failed: {e}")
        return False


def full_setup(progress_callback=None, silent: bool = False) -> dict:
    """
    Complete Encyl setup: install Ollama + pull model.
    Returns status dict for UI integration.
    
    Usage from PyQt6:
        from scripts.setup_encyl import full_setup
        result = full_setup(progress_callback=status_label.setText)
    """
    status = {
        "ollama_installed": False,
        "server_running": False,
        "model_ready": False,
        "error": None,
    }

    try:
        # Step 1: Check/Install Ollama
        if is_ollama_installed():
            status["ollama_installed"] = True
            if progress_callback:
                progress_callback("Ollama found ✓")
        else:
            if progress_callback:
                progress_callback("Installing Ollama...")
            if download_ollama(progress_callback):
                if install_ollama(silent=silent):
                    status["ollama_installed"] = True
                else:
                    status["error"] = "Ollama installation failed"
                    return status
            else:
                status["error"] = "Ollama download failed"
                return status

        # Step 2: Start server
        if progress_callback:
            progress_callback("Starting Ollama server...")
        if start_ollama_server():
            status["server_running"] = True
        else:
            status["error"] = "Could not start Ollama server"
            return status

        # Step 3: Pull model
        if progress_callback:
            progress_callback(f"Downloading Encyl AI model ({MODEL})...")
        if pull_model(MODEL, progress_callback):
            status["model_ready"] = True
            if progress_callback:
                progress_callback("Encyl AI ready ✓")
        else:
            status["error"] = f"Model download failed: {MODEL}"

    except Exception as e:
        status["error"] = str(e)

    return status


if __name__ == "__main__":
    # Can be run standalone for testing
    def _print(msg): print(f"  {msg}")
    result = full_setup(progress_callback=_print)
    print(f"\nResult: {result}")
