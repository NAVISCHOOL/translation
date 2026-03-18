"""Tests for InDesign tag formatter."""
import pytest

from src.format_indesign import classify_line, format_tagged_line, format_indesign


# ── classify_line ──

def test_classify_chapter():
    """Detect chapter headings."""
    assert classify_line("제1장 밝고 즐거운 후아후아의 영혼의 소리") == "chapter"
    assert classify_line("서장") == "chapter"


def test_classify_part():
    """Detect part dividers."""
    assert classify_line("제1부 후아후아의 세계") == "part"


def test_classify_bullet():
    """Detect bullet list items."""
    assert classify_line("• 천국의 언어 8가지") == "bullet"
    assert classify_line("・항목입니다") == "bullet"


def test_classify_body():
    """Classify regular text as body."""
    assert classify_line("이것은 일반 본문 텍스트입니다. 긴 문장이라 소제목이 아닙니다.") == "body"


def test_classify_empty():
    """Classify empty lines."""
    assert classify_line("") == "empty"
    assert classify_line("   ") == "empty"


# ── format_tagged_line ──

def test_format_chapter_tag():
    """Apply chapter tag."""
    result = format_tagged_line("제1장 밝고 즐거운 후아후아", "chapter")
    assert result == "#제1장 밝고 즐거운 후아후아#"


def test_format_part_tag():
    """Apply part tag."""
    result = format_tagged_line("제1부 후아후아의 세계", "part")
    assert result == "@제1부 후아후아의 세계@"


def test_format_subheading_tag():
    """Apply subheading tag."""
    result = format_tagged_line("깃털보다 가벼운 것", "subheading")
    assert result == "##깃털보다 가벼운 것"


def test_format_epigraph_tag():
    """Apply epigraph tag."""
    result = format_tagged_line("「후아후아」 - 사이토 히토리", "epigraph")
    assert result == "$「후아후아」 - 사이토 히토리$"


def test_format_body_unchanged():
    """Body text should be unchanged."""
    text = "이것은 본문입니다."
    result = format_tagged_line(text, "body")
    assert result == text


# ── format_indesign (통합) ──

def test_format_indesign_basic():
    """End-to-end test with sample pages."""
    pages = [
        {"page": 1, "original": "test", "translated": "사이토 히토리 후아후아의 법칙"},
        {"page": 2, "original": "test", "translated": "제1장 밝고 즐거운 후아후아의 영혼의 소리\n\n이것은 본문입니다. 긴 문장이므로 본문으로 분류됩니다."},
    ]
    result = format_indesign(pages)
    assert "#제1장" in result
    assert "이것은 본문입니다" in result


def test_format_indesign_empty_skip():
    """Skip pages with empty translation."""
    pages = [
        {"page": 1, "original": "test", "translated": ""},
        {"page": 2, "original": "test", "translated": "본문입니다."},
    ]
    result = format_indesign(pages)
    assert "본문입니다" in result
    assert len(result.strip().splitlines()) == 1


def test_format_indesign_page_markers():
    """Include page markers when requested."""
    pages = [
        {"page": 1, "original": "test", "translated": "텍스트"},
    ]
    result = format_indesign(pages, include_page_markers=True)
    assert "<!-- page 1 -->" in result
