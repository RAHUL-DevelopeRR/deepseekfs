"""Manual smoke test for Qwen 2.5 Coder via llama.cpp."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.coder_engine import get_coder_engine

engine = get_coder_engine()
answer = engine.complete("Return a JSON object with one key named status and value ok.", max_tokens=80)
print(answer)
