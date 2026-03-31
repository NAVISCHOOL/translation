"""Tests for symbol consistency validation (QA Check #8)."""
import pytest
import json
import os

from src.translate_pipeline import (
    load_symbol_map,
    _check_symbol_consistency,
    _suggest_symbol_fixes,
    validate_translations,
)


@pytest.fixture
def symbol_map():
    """Load the actual symbol_map.json config."""
    return load_symbol_map()


# ── 1. bracket_mismatch ──
def test_bracket_mismatch(symbol_map):
    """Detect when 「」 in original disappears from translated."""
    original = "彼は「ありがとう」と「さようなら」と「こんにちは」と言った。"
    translated = "그는 고마워 라고 안녕히 라고 안녕하세요 라고 말했다."
    issues = _check_symbol_consistency(original, translated, symbol_map)
    types = [i["type"] for i in issues]
    assert "bracket_mismatch" in types


# ── 2. correct_brackets_pass ──
def test_correct_brackets_pass(symbol_map):
    """No issues when brackets are preserved correctly."""
    original = "「ありがとう」と言った。"
    translated = "「고마워」라고 말했다."
    issues = _check_symbol_consistency(original, translated, symbol_map)
    bracket_issues = [i for i in issues if i["type"] == "bracket_mismatch"]
    assert len(bracket_issues) == 0


# ── 3. leaked_pagenum ──
def test_leaked_pagenum(symbol_map):
    """Detect standalone page number at end of translation."""
    original = "本文テキスト。"
    translated = "본문 텍스트.\n42"
    issues = _check_symbol_consistency(original, translated, symbol_map)
    types = [i["type"] for i in issues]
    assert "leaked_pagenum" in types


# ── 4. inline_numbers_ok ──
def test_inline_numbers_ok(symbol_map):
    """Numbers within sentences should not trigger leaked_pagenum."""
    original = "100人が来た。"
    translated = "100명이 왔다."
    issues = _check_symbol_consistency(original, translated, symbol_map)
    types = [i["type"] for i in issues]
    assert "leaked_pagenum" not in types


# ── 5. forbidden_smart_quotes ──
def test_forbidden_smart_quotes(symbol_map):
    """Detect forbidden \u201c\u201d smart quote substitution."""
    original = "「ありがとう」"
    translated = "\u201c고마워\u201d"
    issues = _check_symbol_consistency(original, translated, symbol_map)
    types = [i["type"] for i in issues]
    assert "forbidden_substitution" in types


# ── 6. auto_fix_quotes ──
def test_auto_fix_quotes(symbol_map):
    """Auto-fix replaces \u201c\u201d back to 「」."""
    original = "「ありがとう」"
    translated = "\u201c고마워\u201d"
    issues = _check_symbol_consistency(original, translated, symbol_map)
    fixed = _suggest_symbol_fixes(translated, issues)
    assert "「" in fixed
    assert "」" in fixed
    assert "\u201c" not in fixed
    assert "\u201d" not in fixed


# ── 7. auto_fix_pagenum ──
def test_auto_fix_pagenum(symbol_map):
    """Auto-fix removes leaked page number at end."""
    translated = "본문 텍스트.\n42"
    issues = [{"type": "leaked_pagenum", "detail": "standalone number '42' at end"}]
    fixed = _suggest_symbol_fixes(translated, issues)
    assert fixed.strip() == "본문 텍스트."
    assert "42" not in fixed


# ── 8. load_symbol_map ──
def test_load_symbol_map():
    """symbol_map.json loads with expected keys."""
    sm = load_symbol_map()
    assert "preserve" in sm
    assert "convert" in sm
    assert "forbidden_substitutions" in sm
    assert "page_number_pattern" in sm
    assert "「" in sm["preserve"]


# ── 9. validate_includes_symbol_check ──
def test_validate_includes_symbol_check():
    """validate_translations() includes 기호_일관성 in qa_summary."""
    pages = [
        {"page": 1, "original": "「テスト」", "translated": "\"테스트\""},
    ]
    result = validate_translations(pages)
    assert "기호_일관성" in result["qa_summary"]
    assert "symbol_fixes" in result
