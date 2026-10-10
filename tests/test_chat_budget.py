import sys
from types import SimpleNamespace


def test_unicode_chat_budget_preserves_system_and_marks_truncation(monkeypatch):
    from services.llm_engine import LLMEngine
    formatter = SimpleNamespace(format_chatml=lambda messages: SimpleNamespace(prompt=''.join(m['content'] for m in messages)))
    monkeypatch.setitem(sys.modules, 'llama_cpp.llama_chat_format', formatter)
    engine = LLMEngine()
    engine._model = SimpleNamespace(n_ctx=lambda: 600, tokenize=lambda text, **kwargs: list(text))
    messages = [{'role': 'system', 'content': 'Use only evidence.'}, {'role': 'user', 'content': '資料' * 500}]
    fitted, output = engine._fit_chat_messages(messages, 100)
    assert fitted[0] == messages[0]
    assert 'Earlier input omitted' in fitted[-1]['content']
    assert len(''.join(m['content'] for m in fitted)) + output + 16 <= 600
    assert len(messages[-1]['content']) == 1000


def test_chat_budget_preserves_latest_request_at_end(monkeypatch):
    from services.llm_engine import LLMEngine
    formatter = SimpleNamespace(format_chatml=lambda messages: SimpleNamespace(prompt=''.join(m['content'] for m in messages)))
    monkeypatch.setitem(sys.modules, 'llama_cpp.llama_chat_format', formatter)
    engine = LLMEngine()
    engine._model = SimpleNamespace(n_ctx=lambda: 600, tokenize=lambda text, **kwargs: list(text))
    messages = [{'role': 'system', 'content': 'Tools here.'},
                {'role': 'user', 'content': 'old context ' * 200 + 'Latest request: list /tmp/files'}]
    fitted, _ = engine._fit_chat_messages(messages, 100)
    assert fitted[-1]['content'].startswith('[Earlier input omitted')
    assert fitted[-1]['content'].endswith('Latest request: list /tmp/files')
