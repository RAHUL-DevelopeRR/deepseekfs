import importlib


def test_get_llm_engine_uses_worker_when_requested(monkeypatch):
    import services.llm_engine as llm_engine

    monkeypatch.setenv("NEURON_LLM_BACKEND", "worker")
    monkeypatch.delenv("NEURON_LLM_WORKER_PROCESS", raising=False)
    llm_engine._engine = None

    engine = llm_engine.get_llm_engine()

    assert engine.__class__.__name__ == "LLMWorkerClient"
    llm_engine._engine = None


def test_get_llm_engine_worker_process_uses_inprocess(monkeypatch):
    import services.llm_engine as llm_engine

    monkeypatch.setenv("NEURON_LLM_BACKEND", "worker")
    monkeypatch.setenv("NEURON_LLM_WORKER_PROCESS", "1")
    llm_engine._engine = None

    engine = llm_engine.get_llm_engine()

    assert engine.__class__.__name__ == "LLMEngine"
    llm_engine._engine = None


def test_llm_worker_module_imports_without_starting_model():
    mod = importlib.import_module("services.llm_worker")

    assert callable(mod.main)


def test_worker_client_chat_stream_uses_worker_stream(monkeypatch):
    from services.llm_client import LLMWorkerClient

    seen = {}

    def fake_stream(self, command, payload):
        seen["command"] = command
        seen["payload"] = payload
        yield "hel"
        yield "lo"

    monkeypatch.setattr(LLMWorkerClient, "_stream_request", fake_stream)

    client = LLMWorkerClient(command=["fake"])
    output = "".join(
        client.chat_stream(
            [{"role": "user", "content": "say hello"}],
            max_tokens=9,
            temperature=0.1,
        )
    )

    assert output == "hello"
    assert seen["command"] == "chat_stream"
    assert seen["payload"]["max_tokens"] == 9
