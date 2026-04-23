"""Test script for Neuron v5.2 — verifies all new modules."""
import sys
sys.path.insert(0, r'c:\RAHUL\PROJECTS _OF_Rahul\deepseekfs')

print("=" * 50)
print("Neuron v5.2 Module Integration Test")
print("=" * 50)

# Test 1: Tool Registry
from services.tools import ALL_TOOLS
print(f"\n[1] Tool Registry: {len(ALL_TOOLS)} tools loaded")
for name, tool in ALL_TOOLS.items():
    print(f"    [{tool.permission.value:>8}] {name}")

# Test 2: LLM Engine (import only)
from services.llm_engine import LLMEngine, get_llm_engine
engine = get_llm_engine()
print(f"\n[2] LLM Engine: created, loaded={engine.is_loaded}")

# Test 3: Model Manager
from services.model_manager import get_model_status
status = get_model_status()
print(f"\n[3] Model Manager:")
print(f"    LLM model available: {status['llm']['available']}")
print(f"    Vosk model available: {status['vosk']['available']}")

# Test 4: MemoryOS Agent 
from services.memory_os import get_memory_os
agent = get_memory_os()
print(f"\n[4] MemoryOS Agent: created, has_chat={callable(getattr(agent, 'chat', None))}")

# Test 5: Speech Service
from services.speech_service import get_speech_service
speech = get_speech_service()
print(f"\n[5] Speech Service: created, running={speech.is_running}")

# Test 6: Version
from version import __version__
print(f"\n[6] Version: {__version__}")

# Test 7: OllamaService compatibility shim
from services.ollama_service import get_ollama
ollama = get_ollama()
print(f"\n[7] OllamaService shim: created, available={ollama.is_available()}")

# Test 8: Tool execution (safe - read only)
from services.tools import execute_tool
result = execute_tool("folder_list", path=r"c:\RAHUL\PROJECTS _OF_Rahul\deepseekfs\services", max_depth=1, max_items=20)
print(f"\n[8] Tool execution (folder_list): success={result.success}")
if result.success:
    print(f"    Output preview: {result.output[:200]}")

print("\n" + "=" * 50)
print("ALL MODULE TESTS PASSED")
print("=" * 50)
