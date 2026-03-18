"""Tests for style extraction from original PDF."""
import pytest
import os
import json
from PIL import Image


def test_sample_block_color_returns_median_rgb():
    """3x3 grid sampling with background filtering."""
    img = Image.new("RGB", (100, 50), (255, 255, 255))
    for x in range(20, 80):
        for y in range(10, 40):
            img.putpixel((x, y), (70, 70, 70))

    from src.translate_pipeline import sample_block_color
    bbox = (10, 5, 90, 45)
    r, g, b = sample_block_color(img, bbox)
    assert 50 <= r <= 90
    assert 50 <= g <= 90
    assert 50 <= b <= 90


def test_sample_block_color_all_background_returns_default():
    """If all sampled pixels are background, return default black."""
    img = Image.new("RGB", (100, 50), (255, 255, 255))
    from src.translate_pipeline import sample_block_color
    bbox = (0, 0, 100, 50)
    r, g, b = sample_block_color(img, bbox)
    assert (r, g, b) == (40, 40, 40)


# --- Classification tests ---

def test_classify_size_small():
    from src.translate_pipeline import classify_block_size
    assert classify_block_size(7.5) == "small"

def test_classify_size_medium():
    from src.translate_pipeline import classify_block_size
    assert classify_block_size(11.0) == "medium"

def test_classify_size_large():
    from src.translate_pipeline import classify_block_size
    assert classify_block_size(16.0) == "large"

def test_classify_size_xlarge():
    from src.translate_pipeline import classify_block_size
    assert classify_block_size(24.0) == "xlarge"


def test_classify_position_header():
    from src.translate_pipeline import classify_block_position
    assert classify_block_position(cy=50, cx=300, page_h=1000, page_w=600) == "header"

def test_classify_position_footer():
    from src.translate_pipeline import classify_block_position
    assert classify_block_position(cy=920, cx=300, page_h=1000, page_w=600) == "footer"

def test_classify_position_right():
    from src.translate_pipeline import classify_block_position
    assert classify_block_position(cy=500, cx=500, page_h=1000, page_w=600) == "right"

def test_classify_position_body():
    from src.translate_pipeline import classify_block_position
    assert classify_block_position(cy=500, cx=300, page_h=1000, page_w=600) == "body"


def test_detect_bold_from_flags():
    from src.translate_pipeline import detect_bold
    assert detect_bold(20) is True   # 16 + 4
    assert detect_bold(0) is False
    assert detect_bold(16) is True


# --- Integration tests ---

PDF_PATH = "data/pdf/후아후아_20251210-part-1-ocr.pdf"

@pytest.mark.skipif(not os.path.exists(PDF_PATH), reason="Test PDF not available")
def test_extract_page_styles_page8():
    """Integration: extract styles from real page 8."""
    from src.translate_pipeline import extract_page_styles

    translations = [
        {"page": 8, "original": "はじめに　みなさん", "translated": "머리말\n여러분"}
    ]
    result = extract_page_styles(PDF_PATH, (8, 8), translations)

    assert len(result) == 1
    entry = result[0]
    assert "page_style" in entry

    ps = entry["page_style"]
    assert "dominant" in ps
    assert "special_blocks" in ps

    r, g, b = ps["dominant"]["color_rgb"]
    assert r < 150 and g < 150 and b < 150
    assert ps["dominant"]["size_class"] in ("small", "medium", "large")


@pytest.mark.skipif(not os.path.exists(PDF_PATH), reason="Test PDF not available")
def test_extract_page_styles_backward_compatible():
    """Translations without page_style should still work."""
    from src.translate_pipeline import extract_page_styles

    translations = [
        {"page": 8, "original": "test", "translated": "테스트"}
    ]
    result = extract_page_styles(PDF_PATH, (8, 8), translations)
    assert isinstance(result, list)
    assert result[0]["page"] == 8
    assert result[0]["translated"] == "테스트"
