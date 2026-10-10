from pathlib import Path

from services.summary_presenter import (
    build_extractive_summary,
    format_summary_markdown,
    is_ai_unavailable_text,
)


def test_ai_unavailable_detection_accepts_cpu_backend_error():
    assert is_ai_unavailable_text(
        "AI unavailable: The bundled local AI runtime cannot run on this CPU (0xC000001D)."
    )


def test_file_summary_falls_back_to_structured_markdown(tmp_path: Path):
    target = tmp_path / "report.txt"
    target.write_text(
        "Neuron indexes local files for semantic search. "
        "The summary view should remain useful when the model backend is unavailable. "
        "Users need clear bullets, metadata, and a readable fallback.",
        encoding="utf-8",
    )

    payload = build_extractive_summary(str(target), ai_error="AI unavailable: 0xC000001D")
    rendered = format_summary_markdown(payload)

    assert "### Offline summary - report.txt" in rendered
    assert "**At a glance:**" in rendered
    assert "- " in rendered
    assert "extractive summarization" in rendered


def test_weak_pdf_summary_says_ocr_is_required(monkeypatch, tmp_path: Path):
    from services import summary_presenter
    from services.document_reader import ExtractedContent

    target = tmp_path / "scan.pdf"
    target.write_bytes(b"%PDF-weak")
    monkeypatch.setattr(
        summary_presenter,
        "extract_document_sample",
        lambda *_args, **_kwargs: ExtractedContent(
            text="[page 1] Only repeated header/footer text was extractable.",
            page_count=412,
            sampled_pages=[1, 2, 3, 104],
            chars_extracted=64,
            warnings=["Weak text layer detected; OCR is required."],
        ),
    )
    monkeypatch.setattr(summary_presenter, "ocr_available", lambda: False)

    payload = summary_presenter.build_extractive_summary(str(target), ai_error="model skipped")
    rendered = summary_presenter.format_summary_markdown(payload)

    assert "too weak for a trustworthy summary" in rendered
    assert "OCR is not installed" in rendered
    assert "OCR: required" in rendered
