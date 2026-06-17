"""Tests for optional internet retrieval safety controls."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_live_data_is_off_by_default(monkeypatch):
    from services import internet_search

    monkeypatch.setattr(
        internet_search.UserConfig,
        "load",
        classmethod(lambda cls: {"internet_enabled": False}),
    )

    assert internet_search.should_use_live_data("latest Python release") is False


def test_live_data_can_be_enabled_for_one_request(monkeypatch):
    from services import internet_search

    monkeypatch.setattr(
        internet_search.UserConfig,
        "load",
        classmethod(lambda cls: {"internet_enabled": False}),
    )

    with internet_search.internet_enabled_for_request(True):
        assert internet_search.should_use_live_data("latest Python release") is True

    assert internet_search.should_use_live_data("latest Python release") is False


def test_office_holder_questions_are_live_data(monkeypatch):
    from services import internet_search

    monkeypatch.setattr(
        internet_search.UserConfig,
        "load",
        classmethod(lambda cls: {"internet_enabled": False}),
    )

    assert internet_search.is_live_data_query("Who is the chief minister of Tamil Nadu?")
    assert internet_search.should_use_live_data("Who is the chief minister of Tamil Nadu?") is False

    with internet_search.internet_enabled_for_request(True):
        assert internet_search.should_use_live_data("Who is the chief minister of Tamil Nadu?") is True


def test_public_factual_questions_use_online_grounding_when_enabled(monkeypatch):
    from services import internet_search

    monkeypatch.setattr(
        internet_search.UserConfig,
        "load",
        classmethod(lambda cls: {"internet_enabled": False}),
    )

    assert internet_search.is_public_factual_query(
        "How is Pirates of the Caribbean related to James Cameron?"
    )
    assert internet_search.should_use_live_data(
        "How is Pirates of the Caribbean related to James Cameron?"
    ) is False

    with internet_search.internet_enabled_for_request(True):
        assert internet_search.should_use_live_data(
            "How is Pirates of the Caribbean related to James Cameron?"
        ) is True


def test_disabled_search_does_not_call_network(monkeypatch):
    from services import internet_search

    monkeypatch.setattr(
        internet_search.UserConfig,
        "load",
        classmethod(lambda cls: {"internet_enabled": False}),
    )

    def fail_get(*_args, **_kwargs):
        raise AssertionError("network should not be called when internet mode is off")

    monkeypatch.setattr(internet_search.requests, "get", fail_get)

    assert internet_search.search_public_web("latest Python release") == []


def test_ddg_empty_shell_falls_back_to_wikipedia(monkeypatch):
    from services import internet_search

    monkeypatch.setattr(
        internet_search.UserConfig,
        "load",
        classmethod(lambda cls: {"internet_enabled": True, "internet_max_results": 2}),
    )

    class FakeResponse:
        def __init__(self, status_code=200, text="", payload=None):
            self.status_code = status_code
            self.text = text
            self._payload = payload or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, params=None, **_kwargs):
        params = params or {}
        if "api.duckduckgo.com" in url:
            return FakeResponse(
                status_code=202,
                text='{"Abstract":"","RelatedTopics":[],"Results":[]}',
                payload={"AbstractText": "", "RelatedTopics": [], "Results": []},
            )
        if "duckduckgo.com" in url:
            return FakeResponse(
                status_code=202,
                text="<html><head><title>DuckDuckGo</title></head><body></body></html>",
            )
        if params.get("list") == "search":
            return FakeResponse(
                payload={
                    "query": {
                        "search": [
                            {
                                "title": "Pirates of the Caribbean: The Curse of the Black Pearl",
                                "snippet": "directed by <span>Gore Verbinski</span>",
                            }
                        ]
                    }
                }
            )
        if params.get("prop") == "extracts":
            return FakeResponse(
                payload={
                    "query": {
                        "pages": {
                            "1": {
                                "title": "Pirates of the Caribbean: The Curse of the Black Pearl",
                                "extract": (
                                    "Pirates of the Caribbean: The Curse of the Black Pearl "
                                    "is a 2003 film directed by Gore Verbinski."
                                )
                            }
                        }
                    }
                }
            )
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(internet_search.requests, "get", fake_get)

    results = internet_search.search_public_web(
        "How is Pirates of the Caribbean related to James Cameron?"
    )

    assert results
    assert results[0].title.startswith("Wikipedia:")
    assert "ANSWER_VALUE:" in results[0].snippet
    assert "Gore Verbinski" in results[0].snippet


def test_live_retrieval_failure_does_not_use_model_memory(monkeypatch):
    import services.memory_os as memory_os

    monkeypatch.setattr(
        memory_os,
        "_live_context_for_prompt",
        lambda _message: ("", 0, True),
    )

    agent = memory_os.MemoryOSAgent()
    monkeypatch.setattr(
        agent,
        "_get_engine",
        lambda: (_ for _ in ()).throw(AssertionError("model should not be called")),
    )

    response = agent._chat_mode("Who is the chief minister of Tamil Nadu?")

    assert "could not retrieve live internet results" in response.lower()


def test_tamil_nadu_cm_fact_marker_is_extracted():
    from services import internet_search

    fact = internet_search._extract_tamil_nadu_cm_fact(
        [
            internet_search.InternetResult(
                title="Tamil Nadu Legislative Assembly",
                url="https://www.assembly.tn.gov.in/",
                snippet=(
                    "Hon'ble Chief Minister Thiru C. Joseph Vijay "
                    "Hon'ble Ministers Members"
                ),
            )
        ]
    )

    assert fact is not None
    assert fact.title == "Tamil Nadu Legislative Assembly"
    assert "ANSWER_VALUE: Thiru C. Joseph Vijay." in fact.snippet


def test_verified_live_answer_normalizes_model_formatting():
    import services.memory_os as memory_os

    live_context = "\n".join(
        [
            "Live public web context (internet mode is opt-in):",
            (
                "1. Tamil Nadu Legislative Assembly "
                "(https://www.assembly.tn.gov.in/) - "
                "ANSWER_VALUE: Thiru C. Joseph Vijay. "
                "Public web source text identifies this person as "
                "Hon'ble Chief Minister of Tamil Nadu."
            ),
        ]
    )

    response = memory_os._normalize_verified_live_response(
        (
            "**Answer:** Thiru C. Joseph Vijay. Public web source text "
            "identifies this person as Hon'ble Chief Minister of Tamil Nadu."
        ),
        live_context,
    )

    assert response == (
        "**Answer:** Thiru C. Joseph Vijay\n\n"
        "**Source:** Tamil Nadu Legislative Assembly "
        "(https://www.assembly.tn.gov.in/)"
    )


def test_tamil_nadu_cm_news_wording_is_extracted():
    from services import internet_search

    fact = internet_search._extract_tamil_nadu_cm_fact(
        [
            internet_search.InternetResult(
                title="Hindustan Times: Tamil Nadu government formation",
                url="https://www.hindustantimes.com/example",
                snippet=(
                    "C Joseph Vijay takes oath as Tamil Nadu chief minister "
                    "as TVK forms government with 9 ministers."
                ),
            )
        ]
    )

    assert fact is not None
    assert fact.title == "Hindustan Times: Tamil Nadu government formation"
    assert "ANSWER_VALUE: Thiru C Joseph Vijay." in fact.snippet
