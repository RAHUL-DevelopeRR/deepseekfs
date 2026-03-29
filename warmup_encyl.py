"""
Neuron — Ollama Model Warmup Script
====================================
Pre-loads the Ollama model into RAM so Encyl responses are fast.

Run this script once after Ollama is installed:
  python warmup_encyl.py

Or it runs automatically when Neuron starts.

Minimum Requirements:
  - RAM: 4GB+ (1GB for llama3.2:1b, 200MB for MiniLM, rest for OS)
  - Disk: 2GB+ (model files + index)
  - CPU: x64 (any modern CPU)
  - GPU: Optional (Ollama auto-detects CUDA/ROCm)
  - OS: Windows 10/11
  - Ollama: Must be installed (https://ollama.ai)
"""
import json
import sys
import time
from urllib.request import urlopen, Request
from urllib.error import URLError

OLLAMA_URL = "http://localhost:11434"
MODEL = "llama3.2:1b"

def check_ollama():
    """Check if Ollama is running."""
    try:
        req = Request(f"{OLLAMA_URL}/api/tags", method="GET")
        resp = urlopen(req, timeout=3)
        data = json.loads(resp.read())
        models = [m.get("name", "") for m in data.get("models", [])]
        print(f"  Ollama is running. Models: {models}")
        return any(MODEL in m for m in models)
    except Exception as e:
        print(f"  Ollama not reachable: {e}")
        return False

def pull_model():
    """Pull the model if not present."""
    print(f"  Pulling model {MODEL}...")
    try:
        payload = json.dumps({"name": MODEL, "stream": False}).encode()
        req = Request(
            f"{OLLAMA_URL}/api/pull",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        resp = urlopen(req, timeout=600)  # 10 min timeout for download
        print(f"  Model pulled successfully")
        return True
    except Exception as e:
        print(f"  Failed to pull model: {e}")
        return False

def warmup():
    """Send a small prompt to load model into RAM."""
    print(f"  Warming up {MODEL}...")
    t0 = time.time()
    try:
        payload = json.dumps({
            "model": MODEL,
            "prompt": "Say ready",
            "stream": False,
            "options": {"num_predict": 3}
        }).encode()
        req = Request(
            f"{OLLAMA_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        resp = urlopen(req, timeout=120)
        data = json.loads(resp.read())
        elapsed = time.time() - t0
        print(f"  Model loaded in {elapsed:.1f}s")
        print(f"  Response: {data.get('response', '').strip()}")
        return True
    except Exception as e:
        print(f"  Warmup failed: {e}")
        return False

def main():
    print("=" * 50)
    print("  Neuron — Encyl Model Warmup")
    print("=" * 50)
    print()

    print("[1/3] Checking Ollama...")
    has_model = check_ollama()

    if not has_model:
        print(f"\n[2/3] Model {MODEL} not found. Pulling...")
        if not pull_model():
            print("\nFailed. Make sure Ollama is running: ollama serve")
            sys.exit(1)
    else:
        print(f"\n[2/3] Model {MODEL} already available ✓")

    print(f"\n[3/3] Loading model into RAM...")
    if warmup():
        print("\n✅ Encyl is ready! Model is warm in RAM.")
        print("   Subsequent summaries will be fast (~3-5s).")
    else:
        print("\n⚠ Warmup failed. Encyl will cold-start on first use (~30s).")

    print()
    print("Minimum Requirements:")
    print("  RAM:  4 GB (recommended 8 GB)")
    print("  Disk: 2 GB (models + index)")
    print("  CPU:  Any modern x64 processor")
    print("  GPU:  Optional (CUDA for faster inference)")
    print("  OS:   Windows 10/11")

if __name__ == "__main__":
    main()
