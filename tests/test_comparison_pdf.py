"""Tests for styled comparison PDF rendering."""
import pytest
import os
from PIL import Image


def test_add_comparison_page_with_style(tmp_path):
    """Page with page_style renders without error."""
    from src.generate_comparison_pdf import ComparisonPDF

    pdf = ComparisonPDF()
    pdf.set_auto_page_break(auto=False)

    img_path = str(tmp_path / "test.png")
    Image.new("RGB", (400, 600), (255, 255, 255)).save(img_path)

    page_style = {
        "dominant": {"color_rgb": [70, 70, 70], "size_class": "medium", "bold": False},
        "special_blocks": [
            {"text_hint": "머리말", "color_rgb": [70, 70, 70], "size_class": "large", "bold": True, "position": "header"}
        ],
    }
    pdf.add_comparison_page(1, img_path, "머리말\n\n본문 텍스트입니다.", page_style)
    out = str(tmp_path / "test.pdf")
    pdf.output(out)
    assert os.path.exists(out)


def test_add_comparison_page_without_style(tmp_path):
    """Page without page_style uses defaults (backward compatible)."""
    from src.generate_comparison_pdf import ComparisonPDF

    pdf = ComparisonPDF()
    pdf.set_auto_page_break(auto=False)

    img_path = str(tmp_path / "test.png")
    Image.new("RGB", (400, 600), (255, 255, 255)).save(img_path)

    pdf.add_comparison_page(1, img_path, "기본 텍스트")
    out = str(tmp_path / "test.pdf")
    pdf.output(out)
    assert os.path.exists(out)


PDF_PATH = "data/pdf/후아후아_20251210-part-1-ocr.pdf"


@pytest.mark.skipif(not os.path.exists(PDF_PATH), reason="Test PDF not available")
def test_generate_comparison_pdf_with_styles(tmp_path):
    """Full generate_comparison_pdf with page_style in translations."""
    from src.generate_comparison_pdf import generate_comparison_pdf

    translations = [
        {
            "page": 1,
            "original": "test",
            "translated": "테스트",
            "page_style": {
                "dominant": {"color_rgb": [80, 80, 80], "size_class": "large", "bold": True},
                "special_blocks": [],
            },
        }
    ]
    out = str(tmp_path / "styled.pdf")
    generate_comparison_pdf(PDF_PATH, translations, out, (1, 1))
    assert os.path.exists(out)
