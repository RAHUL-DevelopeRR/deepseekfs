from pathlib import Path

import pytest

from services.document_reader import extract_document_sample


fitz = pytest.importorskip("fitz")


def test_pdf_sampler_removes_repeated_boilerplate(tmp_path: Path):
    target = tmp_path / "sample.pdf"
    doc = fitz.open()
    for page_no in range(1, 8):
        page = doc.new_page()
        page.insert_text((72, 72), "RAAM TECHLINK\n26/2, Taylor's Estate, Chennai")
        page.insert_text((72, 140), f"Question {page_no}: What is Azure AI Search?")
        page.insert_text((72, 170), "Answer: A vector and keyword search service.")
    doc.save(str(target))
    doc.close()

    extracted = extract_document_sample(str(target), max_chars=4000)

    assert "Azure AI Search" in extracted.text
    assert extracted.text.count("RAAM TECHLINK") < 3
    assert extracted.page_count == 7
    assert extracted.sampled_pages == list(range(1, 8))


def test_pdf_sampler_reports_weak_text_layer(tmp_path: Path):
    target = tmp_path / "weak.pdf"
    doc = fitz.open()
    for _ in range(4):
        page = doc.new_page()
        page.insert_text((72, 72), "MCQs")
    doc.save(str(target))
    doc.close()

    extracted = extract_document_sample(str(target), max_chars=4000)

    assert extracted.is_weak_text
    assert "OCR is required" in " ".join(extracted.warnings)


def test_ocr_availability_is_boolean():
    from services.document_reader import ocr_available

    assert isinstance(ocr_available(), bool)
