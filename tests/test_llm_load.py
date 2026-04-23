"""Test: Monkey-patch Jinja2 to handle SmolLM3's custom {% generation %} tag."""
import sys, os, time
sys.path.insert(0, r'c:\RAHUL\PROJECTS _OF_Rahul\deepseekfs')

MODEL = r'c:\RAHUL\PROJECTS _OF_Rahul\deepseekfs\storage\models\HuggingFaceTB_SmolLM3-3B-Q4_K_M.gguf'
print(f"Model size: {os.path.getsize(MODEL)/(1024*1024):.0f}MB")

# ── Patch Jinja2 BEFORE importing llama_cpp ──
from jinja2 import nodes
from jinja2.ext import Extension

class GenerationExtension(Extension):
    """Registers {% generation %} / {% endgeneration %} as no-op block tags.
    SmolLM3's chat template uses these for marking generation regions.
    """
    tags = {"generation"}

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        # Parse until {% endgeneration %}
        body = parser.parse_statements(["name:endgeneration"], drop_needle=True)
        return nodes.CallBlock(
            self.call_method("_noop"), [], [], body
        ).set_lineno(lineno)

    def _noop(self, caller):
        return caller()

# Patch the Jinja2 Environment used by llama-cpp-python
import jinja2
_orig_init = jinja2.Environment.__init__
def _patched_init(self, *args, **kwargs):
    exts = list(kwargs.get("extensions", []))
    if GenerationExtension not in exts:
        exts.append(GenerationExtension)
    kwargs["extensions"] = exts
    _orig_init(self, *args, **kwargs)
jinja2.Environment.__init__ = _patched_init
# ── End patch ──

from llama_cpp import Llama

print("--- Loading with Jinja2 patch ---")
t0 = time.time()
model = Llama(
    model_path=MODEL,
    n_ctx=2048,
    n_batch=256,
    n_threads=max(1, (os.cpu_count() or 4)//2),
    n_gpu_layers=0,
    verbose=False,
    use_mmap=False,
    use_mlock=False,
)
print(f"LOADED in {time.time()-t0:.1f}s  (ctx={model.n_ctx()})")

print("\n--- Generation test ---")
t0 = time.time()
r = model.create_chat_completion(
    messages=[{"role": "user", "content": "Say hello in one sentence."}],
    max_tokens=50, temperature=0.3,
)
content = r['choices'][0]['message']['content']
print(f"  [{time.time()-t0:.1f}s] {content}")

print("\n--- Tool call test ---")
t0 = time.time()
SYSTEM = (
    "You have tools: folder_list(path). "
    'To use a tool: ```json\n{"tool":"folder_list","args":{"path":"..."}}\n```\n'
    "If no tool needed, respond directly."
)
r = model.create_chat_completion(
    messages=[
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "List files in C:/Users"},
    ],
    max_tokens=100, temperature=0.2,
)
content = r['choices'][0]['message']['content']
print(f"  [{time.time()-t0:.1f}s] {content}")

print("\nALL TESTS PASSED")
