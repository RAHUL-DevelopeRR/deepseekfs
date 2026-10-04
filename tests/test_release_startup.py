import argparse
import json
import sqlite3
from types import SimpleNamespace


def test_status_does_not_load_or_rewrite_embeddings(monkeypatch, tmp_path, capsys):
    import app.config as config
    import core.embeddings.embedder as embeddings
    from neufs import _cmd_status

    database = tmp_path / 'files.db'
    with sqlite3.connect(database) as conn:
        conn.executescript("CREATE TABLE files (id INTEGER); INSERT INTO files VALUES (1);"
                           "CREATE TABLE index_settings (key TEXT, value TEXT);"
                           "INSERT INTO index_settings VALUES ('embedding', 'neural-existing');")
    before = database.read_bytes()
    monkeypatch.setattr(config, 'SQLITE_DB_PATH', str(database))
    monkeypatch.setattr(embeddings, 'get_embedder', lambda: (_ for _ in ()).throw(AssertionError('Must not load')))
    assert _cmd_status(argparse.Namespace(load_embeddings=False)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['index_count'] == 1
    assert payload['stored_embedding_backend'] == 'neural-existing'
    assert database.read_bytes() == before


def test_status_reports_lexical_degradation(monkeypatch, tmp_path, capsys):
    import app.config as config
    import core.embeddings.embedder as embeddings
    from neufs import _cmd_status

    monkeypatch.setattr(config, 'SQLITE_DB_PATH', str(tmp_path / 'missing.db'))
    monkeypatch.setattr(embeddings, 'get_embedder', lambda: SimpleNamespace(model=None, identity='lexical'))
    assert _cmd_status(argparse.Namespace(load_embeddings=True)) == 1
    assert json.loads(capsys.readouterr().out)['embedding_error']


def test_stream_end_is_emitted_before_ui_consumes_queued_tokens(monkeypatch):
    from ui.memoryos_panel import MemoryOSPanel
    import services.memory_os as memory_os

    events = []
    class Signal:
        def __init__(self, name):
            self.name = name
        def emit(self, *args):
            events.append((self.name, args))
    class Agent:
        on_token = None
        def chat(self, text, mode):
            self.on_token('hello')
            self.on_token(' world')
            return 'hello world'
    agent = Agent()
    monkeypatch.setattr(memory_os, 'get_memory_os', lambda: agent)
    monkeypatch.setenv('NEURON_UI_STREAMING', '1')
    panel = SimpleNamespace(_streaming=False, _confirm_tool_action=lambda *args: False,
                            **{name: Signal(name) for name in ['_sig_token', '_sig_stream_end', '_sig_response', '_sig_error']})
    MemoryOSPanel._run_agent(panel, 'hello', 'chat')
    assert [name for name, _ in events] == ['_sig_token', '_sig_token', '_sig_stream_end']
    assert agent.on_token is None
