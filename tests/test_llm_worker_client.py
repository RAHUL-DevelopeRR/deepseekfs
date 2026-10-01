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


def test_worker_timeout_terminates_stalled_process_and_recovers():
    import sys
    import time
    from services.llm_client import LLMWorkerClient
    stalled = "import json,time,sys; print(json.dumps({'event':'ready','ok':True}),flush=True); sys.stdin.readline(); time.sleep(30)"
    client = LLMWorkerClient(command=[sys.executable, '-u', '-c', stalled])
    client.request_timeout = 0.2
    started = time.monotonic()
    try:
        assert client._request('chat') is None
        assert time.monotonic() - started < 5
        assert 'timed out' in client.load_error.lower()
        assert client._process is None
        healthy = "import json,sys; print(json.dumps({'event':'ready','ok':True}),flush=True); r=json.loads(sys.stdin.readline()); print(json.dumps({'id':r['id'],'ok':True,'result':'recovered'}),flush=True)"
        client._command = [sys.executable, '-u', '-c', healthy]
        client.request_timeout = 3
        assert client._request('chat') == 'recovered'
    finally:
        client.cancel()


def test_worker_unload_does_not_wait_for_inference_lock():
    import threading
    from services.llm_client import LLMWorkerClient
    client = LLMWorkerClient()
    entered, release = threading.Event(), threading.Event()
    def hold():
        with client._lock:
            entered.set()
            release.wait(3)
    worker = threading.Thread(target=hold)
    worker.start()
    try:
        assert entered.wait(1)
        client.unload()
        assert not release.is_set()
    finally:
        release.set()
        worker.join(3)
